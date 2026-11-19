"""Exercise the actual bundled runtime and child-process memory access."""
import tempfile
import threading
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from app import Window
from address_book import save_book, load_book
from memory import ALL_NUMERIC, pack, unpack
root = Path(__file__).resolve().parents[1]
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(root)))
if not result.wasSuccessful(): raise SystemExit(1)
app = QApplication([])
w = Window()
try:
    w.show(); app.processEvents(); w.start_demo()
    address = w.demo_address
    low = address & ~4095
    results, skipped = w.memory.scan_typed(ALL_NUMERIC, '123456789', threading.Event(), lambda *_: None, [(low,low+4096)])
    assert (address,'int32') in results and skipped == 0
    w.scanned(({(address,'int32'):results[(address,'int32')]}, 0))
    w.table.selectRow(0); w.keep_selected(); w.saved_table.selectRow(0)
    w.edit.setText('77'); w.change(True)
    w.memory.write(address, pack('int32','12')); w.tick()
    assert unpack('int32',w.memory.read(address,4)) == 77
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/'addresses.json'
        save_book(path,w.addresses)
        assert load_book(path)==w.addresses
    w.clear_freezes()
    print('AppImage GUI, demo, multi-type scan, saved addresses, writes and freezing: PASS', flush=True)
finally:
    w.close(); app.processEvents()
