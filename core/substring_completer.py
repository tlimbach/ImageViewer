# substring_completer.py
from PyQt5.QtWidgets import QCompleter
from PyQt5.QtCore import Qt

class SubstringCompleter(QCompleter):
    def __init__(self, items, parent=None):
        super().__init__(items, parent)
        self.setCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterMode(Qt.MatchContains)