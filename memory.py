"""Linux memory access. No privilege or system configuration changes."""
import ctypes as C
import errno
import os
import struct
import zlib
import numpy as np
from scan_results import Block, ScanResults
from pathlib import Path

ALL_NUMERIC = 'All numeric types'
TYPES = {'int32': '<i', 'uint32': '<I', 'int64': '<q', 'float32': '<f', 'float64': '<d'}
class IOVec(C.Structure):
    _fields_ = [('base', C.c_void_p), ('length', C.c_size_t)]
libc = C.CDLL(None, use_errno=True)
for name in ('process_vm_readv', 'process_vm_writev'):
    fn = getattr(libc, name)
    fn.argtypes = [C.c_int, C.POINTER(IOVec), C.c_ulong, C.POINTER(IOVec), C.c_ulong, C.c_ulong]
    fn.restype = C.c_ssize_t

def identity(pid):
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]

def processes():
    result = []
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            try:
                if path.stat().st_uid != os.getuid():
                    continue
                cmd = (path/'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
                if cmd:
                    result.append((int(path.name), cmd[:240]))
            except OSError:
                pass
    return sorted(result)

def pack(kind, text):
    return struct.pack(TYPES[kind], float(text) if kind.startswith('float') else int(text, 0))

def unpack(kind, data):
    return struct.unpack(TYPES[kind], data)[0]

class Memory:
    def __init__(self, pid):
        self.pid = pid
        self.birth = identity(pid)

    def check(self):
        if identity(self.pid) != self.birth:
            raise RuntimeError('Target process changed. Attach again.')

    def transfer(self, address, size, data=None):
        self.check()
        buffer = C.create_string_buffer(size)
        if data is not None:
            C.memmove(buffer, data, size)
        local = IOVec(C.cast(buffer, C.c_void_p), size)
        remote = IOVec(address, size)
        fn = libc.process_vm_readv if data is None else libc.process_vm_writev
        count = fn(self.pid, C.byref(local), 1, C.byref(remote), 1, 0)
        if count < 0:
            code = C.get_errno()
            if code == errno.EPERM:
                raise PermissionError('Linux denied access to this process. See README permission options.')
            raise OSError(code, os.strerror(code))
        if count != size:
            raise OSError('Partial memory transfer; the mapping may have changed.')
        return buffer.raw

    def read(self, address, size):
        return self.transfer(address, size)

    def write(self, address, data):
        self.transfer(address, len(data), data)

    def regions(self):
        self.check()
        result = []
        for line in Path(f'/proc/{self.pid}/maps').read_text().splitlines():
            fields = line.split()
            if fields[1].startswith('rw'):
                low, high = (int(x, 16) for x in fields[0].split('-'))
                result.append((low, high))
        return result

    def scan(self, kind, value, stop, progress, regions=None):
        matches, skipped = self.scan_typed(kind, value, stop, progress, regions)
        return {address: data for (address, _), data in matches.items()}, skipped

    def scan_typed(self, kind, value, stop, progress, regions=None):
        needles = {}
        for candidate in TYPES if kind == ALL_NUMERIC else [kind]:
            try:
                needles[candidate] = pack(candidate, value)
            except (ValueError, OverflowError, struct.error):
                if kind != ALL_NUMERIC:
                    raise
        if not needles:
            raise ValueError('Enter a number representable by at least one supported type.')
        blocks = []
        storage = 0
        skipped = 0
        areas = self.regions() if regions is None else regions
        total = sum(b-a for a,b in areas)
        done = 0
        for low, high in areas:
            for address in range(low, high, 1024*1024):
                if stop.is_set():
                    raise RuntimeError('Scan cancelled; previous results retained.')
                length = min(1024*1024, high-address)
                try:
                    data = self.read(address, length)
                except PermissionError:
                    raise
                except OSError:
                    skipped += length
                    done += length
                    progress(done, total)
                    continue
                for candidate, needle in needles.items():
                    size = len(needle)
                    offset = (-address) % size
                    n = max(0, (length-offset)//size)
                    if not n: continue
                    # Compare bit patterns, preserving exact float-search semantics.
                    values = np.frombuffer(data, dtype=f'<u{size}', count=n, offset=offset)
                    mask = values == int.from_bytes(needle, 'little')
                    count = int(np.count_nonzero(mask))
                    if count:
                        bits = np.packbits(mask).tobytes()
                        blocks.append(Block(address, length, candidate, offset, size, bits, count, needle))
                        storage += len(bits)+len(needle)
                        if storage > 256*1024*1024:
                            raise RuntimeError('Scan snapshot exceeds 256 MiB. Select one numeric type and scan again; previous results retained.')
                done += length
                progress(done, total)
        return ScanResults(blocks), skipped

    def refine(self, kind, previous, mode, value, stop):
        target = pack(kind, value) if mode == 'exact' else None
        result = {}
        for address, old in previous.items():
            if stop.is_set():
                raise RuntimeError('Scan cancelled; previous results retained.')
            try:
                new = self.read(address, len(old))
            except PermissionError:
                raise
            except OSError:
                continue
            a, b = unpack(kind, new), unpack(kind, old)
            keep = {'exact': new == target, 'changed': new != old, 'unchanged': new == old,
                    'increased': a > b, 'decreased': a < b}[mode]
            if keep:
                result[address] = new
        return result, 0

    def refine_typed(self, previous, mode, value, stop, progress=lambda *_: None):
        if isinstance(previous, ScanResults):
            return self.refine_compact(previous, mode, value, stop, progress)
        result = {}
        representable = False
        for kind in TYPES:
            group = {address: data for (address, candidate), data in previous.items() if candidate == kind}
            if not group:
                continue
            if mode == 'exact':
                try:
                    pack(kind, value)
                except (ValueError, OverflowError, struct.error):
                    continue
            representable = True
            refined, _ = self.refine(kind, group, mode, value, stop)
            result.update({(address, kind): data for address, data in refined.items()})
        if mode == 'exact' and previous and not representable:
            raise ValueError('Value cannot be represented by the remaining result types.')
        return result, 0

    def refine_compact(self, previous, mode, value, stop, progress):
        targets = {}
        if mode == 'exact':
            for kind in {b.kind for b in previous.blocks}:
                try: targets[kind] = pack(kind, value)
                except (ValueError, OverflowError, struct.error): pass
            if previous and not targets:
                raise ValueError('Value cannot be represented by the remaining result types.')
        blocks = []
        storage = 0
        skipped = 0
        last_key = None
        current = None
        for number, block in enumerate(previous.blocks):
            if stop.is_set():
                raise RuntimeError('Scan cancelled; previous results retained.')
            if mode == 'exact' and block.kind not in targets: continue
            key = (block.address, block.length)
            if key != last_key:
                try: current = self.read(*key)
                except PermissionError: raise
                except OSError:
                    current = None
                    skipped += block.length
                last_key = key
            if current is None: continue
            n = (block.length-block.offset)//block.size
            def array(data, dtype):
                return np.frombuffer(data, dtype=dtype, count=n, offset=block.offset)
            raw_type = f'<u{block.size}'
            new_bits = array(current, raw_type)
            if mode == 'exact':
                keep = new_bits == int.from_bytes(targets[block.kind], 'little')
            else:
                old_data = block.data()
                if mode in ('changed', 'unchanged'):
                    old = int.from_bytes(old_data, 'little') if block.uniform else array(old_data, raw_type)
                    keep = new_bits != old if mode == 'changed' else new_bits == old
                else:
                    dtype = np.dtype(TYPES[block.kind])
                    new = array(current, dtype)
                    old = unpack(block.kind, old_data) if block.uniform else array(old_data, dtype)
                    if mode == 'increased': keep = new > old
                    elif mode == 'decreased': keep = new < old
                    else: raise ValueError('Unknown refinement mode.')
            keep &= block.mask()
            count = int(np.count_nonzero(keep))
            if count:
                bits = np.packbits(keep).tobytes()
                uniform = mode == 'exact'
                baseline = targets[block.kind] if uniform else zlib.compress(current, 1)
                blocks.append(Block(block.address,block.length,block.kind,block.offset,block.size,bits,count,baseline,uniform))
                storage += len(bits)+len(baseline)
                if storage > 256*1024*1024:
                    raise RuntimeError('Scan snapshot exceeds 256 MiB. Narrow by an exact value or select one numeric type; previous results retained.')
            progress(number+1, len(previous.blocks))
        return ScanResults(blocks), skipped
