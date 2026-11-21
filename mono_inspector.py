"""Offline Mono metadata inspection and a narrowly validated reversible patch."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import dnfile
from dncil.cil.body.reader import read_method_body_from_bytes


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Assembly:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.data = self.path.read_bytes()
        self.pe = dnfile.dnPE(data=self.data)
        if not self.pe.net or not self.pe.net.mdtables:
            raise ValueError('Choose a managed .NET DLL. IL2CPP native games are not supported.')
        self.classes = list(self.pe.net.mdtables.TypeDef)
        self.owners = {m.row_index: str(t.TypeName) for t in self.classes for m in t.MethodList}

    def name(self, item):
        return '.'.join(x for x in [str(item.TypeNamespace), str(item.TypeName)] if x)

    def resolve(self, operand):
        if not hasattr(operand, 'value'):
            return '' if operand is None else str(operand)
        value = operand.value
        table, index = value >> 24, (value & 0xffffff)
        tables = {4:self.pe.net.mdtables.Field, 6:self.pe.net.mdtables.MethodDef,
                  10:self.pe.net.mdtables.MemberRef, 2:self.pe.net.mdtables.TypeDef,
                  1:self.pe.net.mdtables.TypeRef}
        try:
            if table == 0x70: return repr(str(self.pe.net.user_strings.get(index)))
            if table in tables:
                row = tables[table][index-1]
                name = str(row.TypeName if table in (1,2) else row.Name)
                return self.owners.get(index, '')+'.'+name if table == 6 else name
        except (IndexError, AttributeError): pass
        return str(operand)

    def body(self, method):
        if not method.Rva: raise ValueError('This method has no managed IL body.')
        return read_method_body_from_bytes(self.pe.get_data(method.Rva))

    def describe(self, item):
        lines = [self.name(item), '', 'Fields (metadata; not live object addresses):']
        primitive = {2:'bool',3:'char',4:'int8',5:'uint8',6:'int16',7:'uint16',8:'int32',9:'uint32',10:'int64',11:'uint64',12:'float32',13:'float64',14:'string'}
        for ref in item.FieldList:
            f = ref.row; sig = f.Signature.value
            kind = primitive.get(sig[1], 'signature '+sig.hex()) if len(sig)>1 else '?'
            lines.append(f'  {f.Name}: {kind}')
        lines += ['', 'Methods / IL (RVA is a file-relative virtual address, not a live pointer):']
        for ref in item.MethodList:
            m = ref.row
            lines.append(f'\n{m.Name}  [token 0x06000000 + {ref.row_index}; RVA {m.Rva:#x}]')
            try:
                for ins in self.body(m).instructions:
                    lines.append(f'  IL_{ins.offset:04x}: {ins.opcode.name} {self.resolve(ins.operand)}')
            except Exception as error: lines.append('  No readable IL: '+str(error))
        return '\n'.join(lines)

    def budget_sites(self):
        types = [t for t in self.classes if str(t.TypeName)=='NewGamePerksUI']
        if len(types)!=1: raise ValueError('This assembly does not contain the supported Probably Stolen perk screen.')
        methods = {str(m.row.Name):m.row for m in types[0].MethodList}
        sites = []
        # Validate both the displayed balance and the start-game check. Change only
        # one-byte ldc.i4 constants, preserving every branch offset and method size.
        for name, pattern, position in [('CanStart',['call','ldc.i4.3','bgt.s'],1),
                                        ('RefreshCounters',['call','stloc.0','ldc.i4.3','ldloc.0','sub','stloc.1'],2)]:
            if name not in methods: raise ValueError('Unsupported game version: missing '+name)
            method = methods[name]; instructions = self.body(method).instructions
            if [i.opcode.name for i in instructions[:len(pattern)]] != pattern or self.resolve(instructions[0].operand)!='NewGamePerksUI.UsedPoints':
                raise ValueError('Unsupported or modified game version: '+name+' does not match the expected original code.')
            sites.append(self.pe.get_offset_from_rva(method.Rva)+instructions[position].offset)
        if len(set(sites)) != 2: raise ValueError('Invalid patch locations.')
        return sites


def patch_bytes(assembly, budget):
    if isinstance(budget, bool) or not isinstance(budget, int) or not 3 <= budget <= 8:
        raise ValueError('This patch supports a total starting budget from 3 to 8.')
    data = bytearray(assembly.data)
    for offset in assembly.budget_sites(): data[offset] = 0x16 + budget
    return bytes(data)


def game_running(path):
    # Refuse writes while this assembly is mapped, or the target game is running.
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit(): continue
        try:
            cmd = (proc/'cmdline').read_bytes().split(b'\0')[0].replace(b'\\',b'/').lower()
            if cmd.endswith(b'/probably stolen.exe') or cmd == b'probably stolen.exe': return True
            if str(path.resolve()) in (proc/'maps').read_text(): return True
        except (OSError, UnicodeError): pass
    return False


def atomic_write(path, data):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.proton-inspector-', dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o600)
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def backup_paths(path):
    return Path(str(path)+'.proton-inspector-original'), Path(str(path)+'.proton-inspector-patch.json')


def apply_budget(path, budget):
    path = Path(path).resolve()
    if game_running(path): raise ValueError('Close Probably Stolen before applying or restoring its patch.')
    backup, record = backup_paths(path)
    if backup.exists() or record.exists(): raise ValueError('A backup already exists. Restore the original before applying another budget.')
    assembly = Assembly(path)
    patched = patch_bytes(assembly,budget)
    if patched == assembly.data: raise ValueError('3 is already the original budget; no patch is needed.')
    # Exclusive backup creation; never overwrite an earlier original.
    with backup.open('xb') as f:
        f.write(assembly.data); f.flush(); os.fsync(f.fileno())
    atomic_write(record,json.dumps({'original':digest(assembly.data),'patched':digest(patched),'budget':budget},indent=2).encode())
    if path.read_bytes()!=assembly.data: raise ValueError('Game file changed during preparation; patch was not applied.')
    atomic_write(path,patched)


def restore_budget(path):
    path = Path(path).resolve()
    if game_running(path): raise ValueError('Close Probably Stolen before applying or restoring its patch.')
    backup, record = backup_paths(path)
    meta = json.loads(record.read_text()); original = backup.read_bytes()
    if digest(original)!=meta['original']: raise ValueError('Backup checksum mismatch; refusing to restore.')
    if digest(path.read_bytes()) not in (meta['original'],meta['patched']):
        raise ValueError('Game file changed, possibly after an update. Refusing to overwrite it with an old backup.')
    atomic_write(path,original)
    record.unlink(); backup.unlink()
