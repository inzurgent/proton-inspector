import json
from itertools import islice
import struct
import subprocess
import sys
import threading
from pathlib import Path
from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLineEdit, QLabel, QTableWidget, QTableWidgetItem, QMessageBox, QTabWidget, QFileDialog, QInputDialog)
from mono_panel import MonoPanel
from memory import Memory, processes, pack, unpack, TYPES, ALL_NUMERIC
from address_book import load_book, save_book, LIMIT

class Worker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str)
    done = Signal()
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
    def run(self):
        try:
            self.finished.emit(self.fn(self.progress))
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.fn = None  # Release previous snapshot references after the job.
            self.done.emit()

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Proton Inspector • Linux prototype')
        self.resize(980, 650)
        self.memory = None
        self.results = {}
        self.addresses = []
        self.frozen = {}
        self.demo = None
        self.thread = None
        self.stop = threading.Event()
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        title = QLabel('PROTON INSPECTOR')
        title.setStyleSheet('font-size: 24px; font-weight: bold; color: #75d9ce; padding: 12px')
        layout.addWidget(title)
        layout.addWidget(QLabel('Select a game process, scan a known value, then narrow the results as it changes.'))
        self.process_search = QLineEdit()
        self.process_search.setPlaceholderText('Search processes by name, command, or PID…')
        self.process_search.setClearButtonEnabled(True)
        self.process_count = QLabel()
        self.process_list = []
        self.row(layout, self.process_search, self.process_count)
        self.targets = QComboBox()
        self.targets.setMinimumWidth(500)
        self.refresh_button = QPushButton('Refresh')
        self.attach_button = QPushButton('Attach')
        self.demo_button = QPushButton('Start demo')
        self.row(layout, self.targets, self.refresh_button, self.attach_button, self.demo_button)
        self.initial = QComboBox(); self.initial.addItems(['Known value', 'Unknown initial value'])
        self.row(layout, QLabel('New scan mode:'), self.initial)
        self.initial.setToolTip('Unknown initial value captures every aligned numeric value without requiring a number.')
        self.initial.currentTextChanged.connect(self.initial_changed)
        self.kind = QComboBox(); self.kind.addItems([ALL_NUMERIC, *TYPES])
        self.value = QLineEdit('123456789'); self.value.setPlaceholderText('Value for exact searches only')
        self.mode = QComboBox(); self.mode.addItems(['exact', 'changed', 'unchanged', 'increased', 'decreased'])
        self.first = QPushButton('New scan'); self.next = QPushButton('Next scan')
        self.cancel = QPushButton('Cancel'); self.cancel.setEnabled(False)
        self.row(layout, self.kind, self.value, QLabel('Next scan:'), self.mode, self.first, self.next, self.cancel)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Address', 'Type', 'Last scanned value', 'Frozen'])
        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 220)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabs = QTabWidget()
        scan_page = QWidget(); scan_layout = QVBoxLayout(scan_page)
        scan_layout.addWidget(self.table)
        self.keep = QPushButton('Add selected to saved addresses')
        scan_layout.addWidget(self.keep)
        self.tabs.addTab(scan_page, 'Scan results')
        saved_page = QWidget(); saved_layout = QVBoxLayout(saved_page)
        note = QLabel('Saved addresses are absolute. They may change after restarting the game. Loading never writes values.')
        note.setWordWrap(True); saved_layout.addWidget(note)
        self.saved_table = QTableWidget(0, 5)
        self.saved_table.setHorizontalHeaderLabels(['Name', 'Address', 'Type', 'Current value', 'Frozen'])
        self.saved_table.setColumnWidth(0, 180); self.saved_table.setColumnWidth(1, 180)
        self.saved_table.horizontalHeader().setStretchLastSection(True)
        self.saved_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.saved_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        saved_layout.addWidget(self.saved_table)
        self.rename_saved = QPushButton('Rename')
        self.remove_saved = QPushButton('Remove selected')
        self.refresh_saved = QPushButton('Refresh values')
        self.save_list = QPushButton('Save list…')
        self.load_list = QPushButton('Load list…')
        self.row(saved_layout, self.rename_saved, self.remove_saved, self.refresh_saved, self.save_list, self.load_list)
        self.tabs.addTab(saved_page, 'Saved addresses (0)')
        self.mono_panel = MonoPanel(self)
        self.tabs.addTab(self.mono_panel, 'Unity / Mono')
        layout.addWidget(self.tabs)
        self.edit = QLineEdit(); self.edit.setPlaceholderText('New value for selected address')
        self.write = QPushButton('Write value'); self.freeze = QPushButton('Freeze value'); self.unfreeze = QPushButton('Unfreeze all')
        self.row(layout, self.edit, self.write, self.freeze, self.unfreeze)
        self.status = QLabel('Not attached. Start demo to try scanning without changing system permissions.')
        self.status.setWordWrap(True); layout.addWidget(self.status)
        self.keep.clicked.connect(self.keep_selected)
        self.table.cellDoubleClicked.connect(lambda *_: self.keep_selected())
        self.rename_saved.clicked.connect(self.rename_entry)
        self.remove_saved.clicked.connect(self.remove_entries)
        self.refresh_saved.clicked.connect(self.render_saved)
        self.save_list.clicked.connect(self.save_addresses)
        self.load_list.clicked.connect(self.load_addresses)
        self.tabs.currentChanged.connect(lambda *_: self.render_saved())
        self.refresh_button.clicked.connect(self.refresh)
        self.process_search.textChanged.connect(self.filter_processes)
        self.attach_button.clicked.connect(self.attach)
        self.demo_button.clicked.connect(self.start_demo)
        self.first.clicked.connect(lambda: self.scan(True))
        self.next.clicked.connect(lambda: self.scan(False))
        self.cancel.clicked.connect(self.stop.set)
        self.write.clicked.connect(lambda: self.change(False))
        self.freeze.clicked.connect(lambda: self.change(True))
        self.unfreeze.clicked.connect(self.clear_freezes)
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(150)
        self.refresh()

    def row(self, layout, *widgets):
        row = QHBoxLayout()
        for widget in widgets: row.addWidget(widget)
        layout.addLayout(row)

    def error(self, message):
        self.status.setText(message)
        QMessageBox.warning(self, 'Proton Inspector', message)

    def refresh(self):
        self.process_list = processes()
        self.filter_processes()

    def filter_processes(self):
        selected = self.targets.currentData()
        terms = self.process_search.text().casefold().split()
        self.targets.clear()
        for pid, cmd in self.process_list:
            label = f'{pid}  {cmd}'
            if all(term in label.casefold() for term in terms):
                self.targets.addItem(label, pid)
        index = self.targets.findData(selected)
        if index >= 0:
            self.targets.setCurrentIndex(index)
        count = self.targets.count()
        self.process_count.setText(f'{count} / {len(self.process_list)} processes' if count else 'No matching processes')
        self.attach_button.setEnabled(count > 0)

    def attach(self):
        try:
            pid = self.targets.currentData()
            if pid is None: raise ValueError('Select a process first.')
            self.memory = Memory(pid)
            self.results = {}; self.frozen = {}; self.kind.setEnabled(True)
            self.render(); self.render_saved()
            self.status.setText(f'Attached to PID {pid}. Memory access is checked on scan.')
        except Exception as error: self.error(str(error))

    def start_demo(self):
        if self.demo is None or self.demo.poll() is not None:
            self.demo = subprocess.Popen([sys.executable, str(Path(__file__).with_name('demo.py'))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            info = json.loads(self.demo.stdout.readline())
            self.demo_address = info['address']
        self.process_search.clear()
        self.refresh()
        self.targets.setCurrentIndex(self.targets.findData(self.demo.pid))
        self.attach()
        self.kind.setCurrentText('int32'); self.value.setText('123456789')
        self.status.setText(f'Demo PID {self.demo.pid}: int32 value 123456789 at {self.demo_address:#x}. Scan, then edit this address.')

    def initial_changed(self):
        unknown = self.initial.currentText() == 'Unknown initial value'
        self.first.setText('Capture baseline' if unknown else 'New scan')
        if unknown: self.mode.setCurrentText('changed')

    def scan(self, first):
        if self.memory is None:
            self.error('Attach to a process first.'); return
        if not first and not self.results:
            self.error('Run a new scan first.'); return
        self.stop.clear()
        memory, kind, value, mode = self.memory, self.kind.currentText(), self.value.text(), self.mode.currentText()
        unknown = first and self.initial.currentText() == 'Unknown initial value'
        if first and not unknown and not value.strip():
            self.error('Enter a value, or select Unknown initial value to capture a baseline.'); return
        self.capturing_unknown = unknown
        previous = self.results.copy()
        def execute(progress):
            if unknown:
                return memory.scan_unknown(kind, self.stop, lambda n,t: progress.emit(f'Capturing baseline: {n//1048576} / {t//1048576} MiB'))
            if first:
                return memory.scan_typed(kind, value, self.stop, lambda n,t: progress.emit(f'Scanning {n//1048576} / {t//1048576} MiB'))
            return memory.refine_typed(previous, mode, value, self.stop, lambda n,t: progress.emit(f'Refining blocks: {n:,} / {t:,}'))
        self.busy(True)
        self.thread = QThread(self)
        self.worker = Worker(execute); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.status.setText)
        self.worker.finished.connect(self.scanned)
        self.worker.failed.connect(self.error)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(lambda: self.busy(False))
        self.thread.start()

    def busy(self, busy):
        for widget in (self.initial, self.process_search, self.targets, self.refresh_button, self.attach_button, self.demo_button,
                       self.first, self.next, self.write, self.freeze, self.keep, self.load_list): widget.setEnabled(not busy)
        self.kind.setEnabled(not busy)
        self.cancel.setEnabled(busy)
        self.attach_button.setEnabled(not busy and self.targets.count() > 0)

    def scanned(self, result):
        self.results, skipped = result
        self.frozen.clear()
        self.render(); self.render_saved()
        prefix = 'Baseline captured. Change something in the game, then use Next scan. ' if getattr(self, 'capturing_unknown', False) else ''
        self.status.setText(prefix + f'{len(self.results):,} matches. Showing first 2,000. {skipped:,} bytes skipped due to unreadable/changing mappings.')

    def render(self):
        rows = list(islice(self.results.items(), 2000))
        self.table.setRowCount(len(rows))
        for row, ((address, kind), data) in enumerate(rows):
            for col, text in enumerate((hex(address), kind, str(unpack(kind, data)), 'Yes' if address in self.frozen else '')):
                self.table.setItem(row, col, QTableWidgetItem(text))

    def keep_selected(self):
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        if not rows:
            self.error('Select one or more scan results first.'); return
        entries = list(self.addresses)
        for row in rows:
            address = self.table.item(row, 0).text()
            kind = self.table.item(row, 1).text()
            if not any(e['address'] == address and e['type'] == kind for e in entries):
                entries.append({'name': f'Address {address}', 'address': address, 'type': kind})
        if len(entries) > LIMIT:
            self.error(f'Keep at most {LIMIT} saved addresses.'); return
        self.addresses = entries
        self.render_saved()
        self.tabs.setCurrentIndex(1)
        self.status.setText('Addresses added. Rename them, then Save list to keep them on disk.')

    def render_saved(self):
        selected = self.saved_table.currentRow()
        self.saved_table.setRowCount(len(self.addresses))
        for row, entry in enumerate(self.addresses):
            address, kind = int(entry['address'], 16), entry['type']
            value = 'Not attached'
            if self.memory is not None:
                try:
                    value = str(unpack(kind, self.memory.read(address, struct.calcsize(TYPES[kind]))))
                except (OSError, RuntimeError): value = 'Unavailable'
            for col, text in enumerate((entry['name'], entry['address'], kind, value, 'Yes' if address in self.frozen else '')):
                self.saved_table.setItem(row, col, QTableWidgetItem(text))
        if 0 <= selected < len(self.addresses): self.saved_table.selectRow(selected)
        self.tabs.setTabText(1, f'Saved addresses ({len(self.addresses)})')

    def rename_entry(self):
        row = self.saved_table.currentRow()
        if row < 0: return
        name, accepted = QInputDialog.getText(self, 'Name address', 'Name (up to 256 characters):', text=self.addresses[row]['name'])
        if accepted:
            self.addresses[row]['name'] = name[:256]
            self.render_saved()

    def remove_entries(self):
        rows = sorted({index.row() for index in self.saved_table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            self.frozen.pop(int(self.addresses[row]['address'], 16), None)
            del self.addresses[row]
        self.render(); self.render_saved()

    def save_addresses(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save addresses', 'addresses.json', 'Address lists (*.json)')
        if not path: return
        try:
            save_book(path, self.addresses)
            self.status.setText(f'Saved {len(self.addresses)} addresses to {path}')
        except (OSError, ValueError, TypeError) as error: self.error(str(error))

    def load_addresses(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Load addresses', '', 'Address lists (*.json)')
        if not path: return
        try:
            entries = load_book(path)
            if self.addresses:
                answer = QMessageBox.question(self, 'Replace saved addresses?', 'Loading replaces the current address list. Save it first if you want to keep it.', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes: return
            self.addresses = entries
            self.frozen.clear()
            self.render(); self.render_saved()
            self.tabs.setCurrentIndex(1)
            self.status.setText(f'Loaded {len(entries)} addresses. Freezes are off. Verify addresses if the game has restarted.')
        except (OSError, ValueError, TypeError) as error: self.error(str(error))

    def change(self, freeze):
        try:
            if self.memory is None: raise ValueError('Attach to a process first.')
            table = self.saved_table if self.tabs.currentIndex() == 1 else self.table
            row = table.currentRow()
            if row < 0: raise ValueError('Select an address first.')
            if table is self.saved_table:
                entry = self.addresses[row]
                address, kind = int(entry['address'], 16), entry['type']
            else:
                address, kind = int(table.item(row, 0).text(), 16), table.item(row, 1).text()
            data = pack(kind, self.edit.text())
            self.memory.write(address, data)
            if freeze: self.frozen[address] = data
            else: self.frozen.pop(address, None)
            self.render(); self.render_saved()
            self.status.setText(f'{"Freezing" if freeze else "Wrote"} {self.edit.text()} at {address:#x}. Scan values remain the comparison baseline.')
        except Exception as error: self.error(str(error))

    def clear_freezes(self):
        self.frozen.clear(); self.render(); self.render_saved()

    def tick(self):
        try:
            for address, data in list(self.frozen.items()): self.memory.write(address, data)
        except Exception as error:
            self.frozen.clear(); self.render(); self.render_saved(); self.status.setText(f'Freezing stopped: {error}')

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            self.stop.set(); self.status.setText('Cancelling scan. Close again when it stops.'); event.ignore(); return
        if self.demo and self.demo.poll() is None:
            self.demo.terminate(); self.demo.wait(timeout=3)
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet('QWidget { background: #17212b; color: #e5edf3; } QLineEdit,QComboBox,QTableWidget { background: #202f3c; padding: 6px; } QPushButton { background: #315565; padding: 8px; border-radius: 4px; } QPushButton:disabled { color: #70818b; }')
    window = Window(); window.show()
    sys.exit(app.exec())
