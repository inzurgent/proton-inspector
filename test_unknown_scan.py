import ctypes
import gc
import os
import threading
import unittest
from unittest.mock import patch
from memory import Memory, ALL_NUMERIC, pack
from scan_results import SnapshotStore

class UnknownScanTests(unittest.TestCase):
    def setUp(self):
        self.values=(ctypes.c_int32*8)(10,20,30,40,50,60,70,80)
        self.base=ctypes.addressof(self.values)
        self.mem=Memory(os.getpid()); self.stop=threading.Event()
        self.regions=[(self.base,self.base+ctypes.sizeof(self.values))]
    def capture(self, kind='int32'):
        return self.mem.scan_unknown(kind,self.stop,lambda *_:None,self.regions)[0]
    def test_blank_baseline_and_all_refinements(self):
        baseline=self.capture()
        self.assertEqual(len(baseline),8)
        self.values[2]=35; self.values[5]=55
        for mode,indices in [('changed',[2,5]),('increased',[2]),('decreased',[5]),('unchanged',[0,1,3,4,6,7]),('exact',[2])]:
            results,_=self.mem.refine_typed(baseline,mode,'35' if mode=='exact' else '',self.stop)
            self.assertEqual(set(results),{(self.base+i*4,'int32') for i in indices})
        changed,_=self.mem.refine_typed(baseline,'changed','',self.stop)
        self.values[2]=36
        again,_=self.mem.refine_typed(changed,'changed','',self.stop)
        self.assertEqual(dict(again.items()),{(self.base+8,'int32'):pack('int32','36')})
        self.assertEqual(baseline[(self.base+8,'int32')],pack('int32','30'))
    def test_shared_disk_baseline_and_cleanup(self):
        result=self.capture(ALL_NUMERIC)
        self.assertEqual(len(result),32)
        refs=[b.baseline for b in result.blocks]
        self.assertTrue(all(r is refs[0] for r in refs))
        file=refs[0].store.file
        del refs,result; gc.collect()
        self.assertTrue(file.closed)
    def test_cancellation_and_disk_budget(self):
        self.stop.set()
        with self.assertRaises(RuntimeError): self.capture()
        self.stop.clear()
        with patch.object(SnapshotStore,'LIMIT',1):
            with self.assertRaisesRegex(RuntimeError,'temporary-file budget'): self.capture()
    def test_unaligned_short_region(self):
        results,_=self.mem.scan_unknown('int32',self.stop,lambda *_:None,[(self.base+1,self.base+11)])
        self.assertEqual(dict(results.items()),{(self.base+4,'int32'):pack('int32','20')})

if __name__=='__main__': unittest.main()
