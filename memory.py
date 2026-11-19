"""Linux memory access. No privilege or system configuration changes."""
import ctypes as C
import errno
import os
import struct
from pathlib import Path

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
        needle = pack(kind, value)
        size = len(needle)
        matches = {}
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
                    continue
                offset = data.find(needle)
                while offset >= 0:
                    if (address+offset) % size == 0:
                        matches[address+offset] = needle
                        if len(matches) > 250000:
                            raise RuntimeError('More than 250,000 matches. Choose a less common initial value.')
                    offset = data.find(needle, offset+1)
                done += length
                progress(done, total)
        return matches, skipped

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
