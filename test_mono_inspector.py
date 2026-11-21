import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mono_inspector import Assembly, apply_budget, restore_budget, patch_bytes, backup_paths, digest

class FakeAssembly:
    def __init__(self,path): self.data=Path(path).read_bytes()
    def budget_sites(self): return [1,3]

class PatchTests(unittest.TestCase):
    def test_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d, patch('mono_inspector.game_running',return_value=False), patch('mono_inspector.Assembly',FakeAssembly):
            p=Path(d)/'game.dll'; original=b'\x00\x19\x00\x19'; p.write_bytes(original)
            apply_budget(p,8)
            self.assertEqual(p.read_bytes(),b'\x00\x1e\x00\x1e')
            backup,record=backup_paths(p)
            self.assertEqual(backup.read_bytes(),original)
            with self.assertRaisesRegex(ValueError,'backup already'): apply_budget(p,7)
            restore_budget(p); self.assertEqual(p.read_bytes(),original)
            self.assertFalse(backup.exists()); self.assertFalse(record.exists())

    def test_updated_game_is_preserved(self):
        with tempfile.TemporaryDirectory() as d, patch('mono_inspector.game_running',return_value=False), patch('mono_inspector.Assembly',FakeAssembly):
            p=Path(d)/'game.dll'; p.write_bytes(b'\x00\x19\x00\x19'); apply_budget(p,8)
            p.write_bytes(b'updated game')
            with self.assertRaisesRegex(ValueError,'Game file changed'): restore_budget(p)
            self.assertEqual(p.read_bytes(),b'updated game')

    def test_corrupt_backup_is_rejected(self):
        with tempfile.TemporaryDirectory() as d, patch('mono_inspector.game_running',return_value=False), patch('mono_inspector.Assembly',FakeAssembly):
            p=Path(d)/'game.dll'; p.write_bytes(b'\x00\x19\x00\x19'); apply_budget(p,8)
            backup,_=backup_paths(p); backup.write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'Backup checksum'): restore_budget(p)

    def test_running_game_refused(self):
        with patch('mono_inspector.game_running',return_value=True):
            with self.assertRaisesRegex(ValueError,'Close Probably'): apply_budget('unused.dll',8)
            with self.assertRaisesRegex(ValueError,'Close Probably'): restore_budget('unused.dll')

    def test_invalid_budget_and_native_file(self):
        for value in [2,9,True,4.5]:
            with self.assertRaises(ValueError): patch_bytes(None,value)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'native.dll'; p.write_bytes(b'not a managed DLL')
            with self.assertRaises(Exception): Assembly(p)
