"""Compact immutable scan snapshots: one candidate bit per aligned value."""
from collections.abc import Mapping
from dataclasses import dataclass
import zlib
import numpy as np

@dataclass(frozen=True)
class Block:
    address: int
    length: int
    kind: str
    offset: int
    size: int
    bits: bytes
    count: int
    baseline: bytes
    uniform: bool = True

    def mask(self):
        n = (self.length-self.offset)//self.size
        return np.unpackbits(np.frombuffer(self.bits, dtype=np.uint8), count=n).astype(bool)

    def data(self):
        return self.baseline if self.uniform else zlib.decompress(self.baseline)

class ScanResults(Mapping):
    def __init__(self, blocks):
        self.blocks = tuple(blocks)
        self.count = sum(b.count for b in self.blocks)
        self.storage_bytes = sum(len(b.bits)+len(b.baseline) for b in self.blocks)

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
