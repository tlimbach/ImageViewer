import os

from PyQt5.QtCore import QObject, pyqtSignal, QRunnable

THUMBNAIL_DELAY=111
FLUEND=True
FLUEND_STEPS=1
FRAMES_PER_THUMBNAIL = FLUEND_STEPS*155
THUMBNAIL_LOAD_THREAD_COUNT=2

class ThumbnailSignal(QObject):
    finished = pyqtSignal(str, list)

class CachedThumbnailLoaderImage(QRunnable):
    def __init__(self, path, cache_files, signal):
        super().__init__()
        self.path = path
        self.cache_files = cache_files
        self.signal = signal

    def run(self):
        from PyQt5.QtGui import QImage
        try:
            images = [QImage(f) for f in self.cache_files if os.path.exists(f)]
            if images and all(not img.isNull() for img in images):
                self.signal.finished.emit(self.path, images)
        except Exception as e:
            print(f"Fehler beim Laden gecachter Thumbnails: {e}")
