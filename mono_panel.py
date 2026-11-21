"""Unity/Mono assembly browser with an optional, reversible game-specific patch."""
from pathlib import Path
from PySide6.QtCore import QSettings, QUrl
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QPlainTextEdit, QSplitter, QFileDialog, QMessageBox, QSpinBox)
from mono_inspector import Assembly, apply_budget, restore_budget, backup_paths


class MonoPanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.assembly = None
        layout = QVBoxLayout(self)
        note = QLabel('Assembly inspection: browse Unity/Mono classes, fields and method IL. '
                      'This reads game files; it does not inspect live objects or invoke methods. IL2CPP is not supported.')
        note.setWordWrap(True); layout.addWidget(note)
        self.settings = QSettings('ProtonInspector', 'ProtonInspector')
        row = QHBoxLayout()
        self.path_edit = QLineEdit(str(self.settings.value('mono/lastAssembly', '')))
        self.path_edit.setPlaceholderText('Paste the full path to Assembly-CSharp.dll, then press Enter')
        self.path_edit.setClearButtonEnabled(True)
        self.open_button = QPushButton('Open DLL')
        self.browse_button = QPushButton('Browse…')
        row.addWidget(self.path_edit,1); row.addWidget(self.open_button); row.addWidget(self.browse_button)
        layout.addLayout(row)
        self.path_label = QLabel('No assembly loaded.')
        self.path_label.setWordWrap(True); layout.addWidget(self.path_label)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search classes, field names or method names…')
        layout.addWidget(self.search)
        splitter = QSplitter(); self.classes = QListWidget(); self.details = QPlainTextEdit()
        self.details.setReadOnly(True); splitter.addWidget(self.classes); splitter.addWidget(self.details)
        splitter.setStretchFactor(1,3); layout.addWidget(splitter)
        row = QHBoxLayout(); row.addWidget(QLabel('Probably Stolen starting budget:'))
        self.budget = QSpinBox(); self.budget.setRange(3,8); self.budget.setValue(8)
        row.addWidget(self.budget)
        self.apply = QPushButton('Apply perk-budget patch…'); self.restore = QPushButton('Restore original…')
        self.apply.setEnabled(False); self.restore.setEnabled(False)
        row.addWidget(self.apply); row.addWidget(self.restore); layout.addLayout(row)
        self.info = QLabel('Patch requires closing the game. Changes the total budget (3–8), not the perk-slot limit. '
                           'A verified original backup is saved beside the DLL. Game updates may replace the patch.')
        self.info.setWordWrap(True); layout.addWidget(self.info)
        self.open_button.clicked.connect(self.open_path)
        self.path_edit.returnPressed.connect(self.open_path)
        self.browse_button.clicked.connect(self.choose)
        self.search.textChanged.connect(self.filter)
        self.classes.currentRowChanged.connect(self.show_class)
        self.apply.clicked.connect(self.apply_patch); self.restore.clicked.connect(self.restore_patch)
        self.visible_classes = []

    def entered_path(self):
        text = self.path_edit.text().strip()
        if len(text)>1 and text[0] == text[-1] and text[0] in ('"', "'"):
            text = text[1:-1]
        if text.startswith('file:'):
            url = QUrl(text)
            if not url.isLocalFile() or url.host() not in ('', 'localhost'):
                raise ValueError('Use a local file path.')
            text = url.toLocalFile()
        if not text: raise ValueError('Paste the full path to a managed DLL first.')
        return str(Path(text).expanduser())

    def open_path(self):
        try: path = self.entered_path()
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot open assembly', str(error)); return
        self.load(path)

    def choose(self):
        try: initial = self.entered_path()
        except ValueError: initial = str(Path.home())
        if not self.path_edit.text().strip() and self.window.memory:
            try:
                for line in Path(f'/proc/{self.window.memory.pid}/maps').read_text().splitlines():
                    parts = line.split(maxsplit=5)
                    if len(parts)==6 and parts[5].endswith('/UnityPlayer.dll'):
                        candidates = list(Path(parts[5]).parent.glob('*_Data/Managed/Assembly-CSharp.dll'))
                        if candidates: initial=str(candidates[0]); break
            except OSError: pass
        path,_ = QFileDialog.getOpenFileName(self,'Open Unity/Mono assembly',initial,'Managed assemblies (*.dll *.exe)')
        if path: self.load(path)

    def load(self,path):
        try:
            assembly=Assembly(path)
        except Exception as error:
            QMessageBox.warning(self,'Cannot open assembly',str(error)); return
        self.assembly=assembly
        self.path_edit.setText(str(assembly.path))
        self.settings.setValue('mono/lastAssembly', str(assembly.path))
        self.path_label.setText('Loaded: '+str(assembly.path)); self.filter()
        try:
            assembly.budget_sites(); self.apply.setEnabled(True)
            self.info.setText('Supported Probably Stolen perk screen found. Close the game before patching. '
                              'Budget 3–8; both the displayed balance and Continue validation are updated. Perk slots remain unchanged.')
        except Exception as error:
            self.apply.setEnabled(False); self.info.setText(str(error))
        backup,record=backup_paths(assembly.path)
        self.restore.setEnabled(backup.exists() and record.exists())

    def filter(self):
        self.classes.clear(); self.visible_classes=[]
        if not self.assembly: return
        terms=self.search.text().casefold().split()
        for item in self.assembly.classes:
            name=self.assembly.name(item)
            haystack=' '.join([name,*[str(x.row.Name) for x in item.FieldList],*[str(x.row.Name) for x in item.MethodList]]).casefold()
            if all(t in haystack for t in terms):
                self.visible_classes.append(item); self.classes.addItem(name)
        if self.visible_classes: self.classes.setCurrentRow(0)
        else: self.details.clear()

    def show_class(self,index):
        if self.assembly and 0<=index<len(self.visible_classes):
            self.details.setPlainText(self.assembly.describe(self.visible_classes[index]))

    def apply_patch(self):
        if not self.assembly: return
        text=(f'Set the total starting perk budget to {self.budget.value()}?\n\n'
              f'File: {self.assembly.path}\n\nClose the game first. The original is backed up beside this file. '
              'Use Restore original to undo. The perk-slot limit is unchanged.')
        if QMessageBox.question(self,'Apply reversible game patch',text)!=QMessageBox.StandardButton.Yes: return
        try:
            apply_budget(self.assembly.path,self.budget.value()); self.load(self.assembly.path)
            self.info.setText('Patch applied. Launch the game to use the new budget. Restore original is available below.')
        except Exception as error: QMessageBox.warning(self,'Patch not applied',str(error))

    def restore_patch(self):
        if not self.assembly: return
        if QMessageBox.question(self,'Restore original','Restore the verified original game DLL? Close the game first.')!=QMessageBox.StandardButton.Yes: return
        try:
            restore_budget(self.assembly.path); self.load(self.assembly.path)
            self.info.setText('Original restored. Launch the game to use its original starting budget.')
        except Exception as error: QMessageBox.warning(self,'Restore failed',str(error))
