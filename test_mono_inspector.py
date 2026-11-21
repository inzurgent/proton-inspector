import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mono_inspector import Assembly, apply_budget, restore_budget, patch_bytes, backup_paths, digest

class FakeAssembly:
    def __init__(self,path): self.data=Path(path).read_bytes()
    def budget_sites(self): return [1,3]
    def slot_site(self): return 5

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


class SlotPatchTests(unittest.TestCase):
    def test_slots_only_and_combined_roundtrip(self):
        for budget in (3,8):
            with tempfile.TemporaryDirectory() as d, patch('mono_inspector.game_running',return_value=False), patch('mono_inspector.Assembly',FakeAssembly):
                p=Path(d)/'game.dll'; original=bytes([0,0x19,0,0x19,0,0x1a]); p.write_bytes(original)
                apply_budget(p,budget,8)
                self.assertEqual(p.read_bytes(),bytes([0,0x16+budget,0,0x16+budget,0,0x1e]))
                self.assertEqual(json.loads(backup_paths(p)[1].read_text())['slots'],8)
                restore_budget(p); self.assertEqual(p.read_bytes(),original)

    def test_invalid_slots(self):
        for slots in (3,9,True,4.5):
            with self.assertRaisesRegex(ValueError,'base perk slots'): patch_bytes(None,3,slots)

    def test_legacy_backup_restore(self):
        with tempfile.TemporaryDirectory() as d, patch('mono_inspector.game_running',return_value=False), patch('mono_inspector.Assembly',FakeAssembly):
            p=Path(d)/'game.dll';original=bytes([0,0x19,0,0x19]);p.write_bytes(original)
            apply_budget(p,8)
            _,record=backup_paths(p);meta=json.loads(record.read_text());meta.pop('slots');record.write_text(json.dumps(meta))
            restore_budget(p);self.assertEqual(p.read_bytes(),original)
