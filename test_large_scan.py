import ctypes
import os
import threading
import unittest
from unittest.mock import patch
from memory import Memory, ALL_NUMERIC, pack
from scan_results import ScanResults

class LargeScanTests(unittest.TestCase):
    def setUp(self):
        self.data = (ctypes.c_uint64 * (4*1024*1024//8))()
        self.base = ctypes.addressof(self.data)
        self.memory = Memory(os.getpid())
        self.stop = threading.Event()
        self.regions = [(self.base,self.base+ctypes.sizeof(self.data))]
    def scan(self):
        return self.memory.scan_typed(ALL_NUMERIC,'0',self.stop,lambda *_:None,self.regions)[0]
    def test_millions_of_matches_and_batched_refinement(self):
        result = self.scan()
        self.assertIsInstance(result,ScanResults)
        self.assertEqual(len(result),4*1024*1024)
        self.assertLess(result.storage_bytes,600000)
        self.assertIs(result.copy(),result)
        self.data[1234]=7
        with patch.object(self.memory,'read',wraps=self.memory.read) as reader:
            narrowed,_=self.memory.refine_typed(result,'exact','7',self.stop)
            self.assertEqual(reader.call_count,4)
        address=self.base+1234*8
        self.assertEqual(dict(narrowed.items()),{(address,k):pack(k,'7') for k in ('int32','uint32','int64')})
        # Old snapshots remain intact for cancellation/error recovery.
        self.assertEqual(result[(address,'int32')],pack('int32','0'))
        changed,_=self.memory.refine_typed(result,'changed','',self.stop)
        self.assertTrue(changed)
        self.data[1234]=9
        increased,_=self.memory.refine_typed(changed,'increased','',self.stop)
        self.assertEqual(increased[(address,'int32')],pack('int32','9'))
        stable,_=self.memory.refine_typed(increased,'unchanged','',self.stop)
        self.assertEqual(dict(stable.items()),dict(increased.items()))
    def test_cancel_and_invalid_value_retain_snapshot(self):
        result=self.scan()
        with self.assertRaises(ValueError): self.memory.refine_typed(result,'exact','nope',self.stop)
        self.stop.set()
        with self.assertRaises(RuntimeError): self.memory.refine_typed(result,'changed','',self.stop)
        self.assertEqual(len(result),4*1024*1024)

if __name__=='__main__': unittest.main()
