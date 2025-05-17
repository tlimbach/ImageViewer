from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QLabel

from core.common import THUMBNAIL_DELAY


class VideoThumbnailWidget(QLabel):
    def __init__(self, frames, interval=THUMBNAIL_DELAY):
        super().__init__()
        self.frames = frames
        self.index = 0
        self.setPixmap(self.frames[0])
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self.timer.start(interval)

    def next_frame(self):
        self.index = (self.index + 1) % len(self.frames)
        self.setPixmap(self.frames[self.index])