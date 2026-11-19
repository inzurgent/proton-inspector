import tempfile
import unittest
from pathlib import Path
from address_book import load_book, save_book, validate

class AddressBookTests(unittest.TestCase):
    def test_round_trip_and_failed_save_preserves_file(self):
        entries = [{'name': 'Money', 'address': '0x123456789', 'type': 'int32'},
                   {'name': 'Speed', 'address': '0x4567', 'type': 'float32'}]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'addresses.json'
            save_book(path, entries)
            self.assertEqual(load_book(path), entries)
            with self.assertRaises(ValueError):
                save_book(path, [{'name': 'Broken', 'address': '0x0', 'type': 'int32'}])
            self.assertEqual(load_book(path), entries)
    def test_invalid_documents(self):
        for document in [[], {'version': 2, 'addresses': []}, {'version': 1, 'addresses': [{}]},
                         {'version': 1, 'addresses': [{'name': 'Bad', 'address': '-1', 'type': 'int32'}]}]:
            with self.assertRaises(ValueError): validate(document)

if __name__ == '__main__': unittest.main()
