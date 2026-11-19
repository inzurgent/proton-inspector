import json
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from memory import Memory, pack, unpack

class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.child = subprocess.Popen([sys.executable, str(Path(__file__).with_name('demo.py'))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.info = json.loads(self.child.stdout.readline())
        self.mem = Memory(self.info['pid'])
        self.address = self.info['address']
    def tearDown(self):
        self.child.terminate(); self.child.wait()
        self.child.stdin.close(); self.child.stdout.close()
    def test_scan_write_refine(self):
        stop = threading.Event()
        results, skipped = self.mem.scan('int32', '123456789', stop, lambda *_: None,
            [(self.address & ~4095, (self.address & ~4095)+4096)])
        self.assertIn(self.address, results)
        self.assertEqual(skipped, 0)
        self.mem.write(self.address, pack('int32', '42'))
        self.child.stdin.write('get\n'); self.child.stdin.flush()
        self.assertEqual(self.child.stdout.readline().strip(), '42')
        for mode in ('changed', 'decreased', 'exact'):
            updated, _ = self.mem.refine('int32', results, mode, '42', stop)
            self.assertIn(self.address, updated)
        unchanged, _ = self.mem.refine('int32', results, 'unchanged', '', stop)
        self.assertNotIn(self.address, unchanged)
        stop.set()
        with self.assertRaises(RuntimeError):
            self.mem.scan('int32', '42', stop, lambda *_: None)
    def test_identity_and_types(self):
        for kind, value in [('int32','-12'), ('uint32','4294967295'), ('int64','1099511627776'), ('float32','1.5'), ('float64','2.25')]:
            self.assertEqual(unpack(kind, pack(kind, value)), float(value))
        self.mem.birth = 'invalid'
        with self.assertRaises(RuntimeError): self.mem.read(self.address, 4)

if __name__ == '__main__': unittest.main()
