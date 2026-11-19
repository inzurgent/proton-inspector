import ctypes
import os
import threading
import unittest
from unittest.mock import patch
from memory import Memory, ALL_NUMERIC, TYPES, pack

class Values(ctypes.Structure):
    _fields_ = [('signed', ctypes.c_int32), ('unsigned', ctypes.c_uint32),
                ('large', ctypes.c_int64), ('single', ctypes.c_float), ('double', ctypes.c_double)]

class MultiTypeTests(unittest.TestCase):
    def setUp(self):
        self.values = Values(42, 42, 42, 42.0, 42.0)
        self.base = ctypes.addressof(self.values)
        self.memory = Memory(os.getpid())
        self.stop = threading.Event()
        self.regions = [(self.base, self.base+ctypes.sizeof(self.values))]
    def scan(self, value='42', kind=ALL_NUMERIC):
        return self.memory.scan_typed(kind, value, self.stop, lambda *_: None, self.regions)[0]
    def test_all_types_one_read_and_independent_refinement(self):
        with patch.object(self.memory, 'read', wraps=self.memory.read) as read:
            results = self.scan()
            self.assertEqual(read.call_count, 1)
        for field, kind in zip(('signed','unsigned','large','single','double'), TYPES):
            self.assertIn((self.base+getattr(Values, field).offset, kind), results)
        self.values.single = 43.5
        expected = {(self.base+Values.single.offset, 'float32'): pack('float32','43.5')}
        for mode in ('changed','increased','exact'):
            refined, _ = self.memory.refine_typed(results, mode, '43.5', self.stop)
            self.assertEqual(refined, expected)
    def test_fraction_and_single_type(self):
        self.values.double = 1.5
        result = self.scan('1.5')
        self.assertIn((self.base+Values.double.offset,'float64'),result)
        self.assertTrue(all(kind.startswith('float') for _,kind in result))
        result = self.scan(kind='int32')
        self.assertTrue(result)
        self.assertTrue(all(kind=='int32' for _,kind in result))
        with self.assertRaises(ValueError): self.scan('not a number')
    def test_same_address_retains_distinct_interpretations(self):
        results = self.scan()
        self.assertIn((self.base,'int32'),results)
        self.assertIn((self.base,'uint32'),results)
        self.stop.set()
        with self.assertRaises(RuntimeError): self.scan()

if __name__ == '__main__': unittest.main()
