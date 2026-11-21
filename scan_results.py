"""Compact immutable scan snapshots: one candidate bit per aligned value."""
from collections.abc import Mapping
from dataclasses import dataclass
import zlib
import os
import tempfile
from pathlib import Path
import numpy as np

class SnapshotStore:
    """Private temporary disk storage, deleted when the last snapshot is released."""
    LIMIT = 4*1024*1024*1024

    def __init__(self):
        cache = Path(os.environ.get('XDG_CACHE_HOME') or Path.home()/'.cache')/'proton-inspector'/'scans'
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.file = tempfile.TemporaryFile(prefix='baseline-', dir=cache)
        self.size = 0

    def __del__(self):
        if hasattr(self, "file"): self.file.close()

    def append(self, data):
        encoded = zlib.compress(data, 1)
        if self.size+len(encoded) > self.LIMIT:
            raise RuntimeError('Snapshot exceeds the 4 GiB temporary-file budget; previous results retained.')
        offset = self.size
        self.file.write(encoded)
        self.file.flush()
        self.size += len(encoded)
        return SnapshotData(self, offset, len(encoded))

@dataclass(frozen=True)
class SnapshotData:
    store: SnapshotStore
    offset: int
    length: int

    def read(self):
        encoded = os.pread(self.store.file.fileno(), self.length, self.offset)
        if len(encoded) != self.length:
            raise OSError('Could not read the complete scan baseline.')
        return zlib.decompress(encoded)

@dataclass(frozen=True)
class Block:
    address: int
    length: int
    kind: str
    offset: int
    size: int
    bits: bytes
    count: int
    baseline: bytes | SnapshotData
    uniform: bool = True

    def mask(self):
        n = (self.length-self.offset)//self.size
        return np.unpackbits(np.frombuffer(self.bits, dtype=np.uint8), count=n).astype(bool)

    def data(self):
        if isinstance(self.baseline, SnapshotData): return self.baseline.read()
        return self.baseline if self.uniform else zlib.decompress(self.baseline)

class ScanResults(Mapping):
    def __init__(self, blocks):
        self.blocks = tuple(blocks)
        self.count = sum(b.count for b in self.blocks)
        self.storage_bytes = sum(len(b.bits)+(len(b.baseline) if isinstance(b.baseline, bytes) else 0) for b in self.blocks)

    def __len__(self): return self.count

    def copy(self): return self # Blocks and byte buffers are immutable.

    def items(self):
        for block in self.blocks:
            data = block.data()
            # Iterate bounded windows so rendering the first rows never expands
            # millions of candidate indices at once.
            for byte_start in range(0, len(block.bits), 4096):
                indices = np.flatnonzero(np.unpackbits(np.frombuffer(block.bits[byte_start:byte_start+4096],dtype=np.uint8)))
                for local in indices:
                    index = byte_start*8+int(local)
                    offset = block.offset+index*block.size
                    value = data if block.uniform else data[offset:offset+block.size]
                    yield (block.address+offset, block.kind), value

    def __iter__(self):
        for key, _ in self.items(): yield key

    def __getitem__(self, key):
        address, kind = key
        for block in self.blocks:
            relative = address-block.address-block.offset
            if block.kind != kind or relative < 0 or relative % block.size: continue
            index = relative//block.size
            if index >= (block.length-block.offset)//block.size: continue
            if block.bits[index//8] & (128 >> (index%8)):
                data=block.data()
                offset=block.offset+relative
                return data if block.uniform else data[offset:offset+block.size]
        raise KeyError(key)
