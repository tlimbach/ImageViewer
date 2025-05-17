import os

from PyQt5.QtCore import QRunnable
from PyQt5.QtGui import QPixmap


class CachedThumbnailLoader(QRunnable):
    def __init__(self, path, cache_files, signal):
        super().__init__()
        self.path = path
        self.cache_files = cache_files
        self.signal = signal

    def run(self):
        try:
            frames = [QPixmap(f) for f in self.cache_files if os.path.exists(f)]
            if frames:
                self.signal.finished.emit(self.path, frames)
        except Exception as e:
            print(f"Fehler beim Laden gecachter Thumbnails: {e}")