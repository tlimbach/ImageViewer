import cv2
from PyQt5.QtCore import QRunnable, Qt
from PyQt5.QtGui import QImage, QPixmap

from core.common import FRAMES_PER_THUMBNAIL, FLUEND, FLUEND_STEPS


class VideoThumbnailLoader(QRunnable):
    def __init__(self, path, thumb_size, signal, video_ranges):
        super().__init__()
        self.path = path
        self.thumb_size = thumb_size
        self.signal = signal
        self.video_ranges = video_ranges

    def run(self):
        try:
            cap = cv2.VideoCapture(self.path)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = frame_count / fps if fps else 0
            if frame_count <= 0 or duration <= 0:
                return

            bounds = self.video_ranges.get(self.path)
            start_sec = bounds.get("start", 0) if bounds else 0
            end_sec = bounds.get("end", duration) if bounds else duration
            start_frame = int(start_sec * fps)
            end_frame = int(end_sec * fps)
            step = max((end_frame - start_frame) // FRAMES_PER_THUMBNAIL, 1)

            if (FLUEND):
                step =FLUEND_STEPS
                end_frame=start_frame+FRAMES_PER_THUMBNAIL


            frames = []
            for i in range(start_frame, end_frame, step):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                success, frame = cap.read()
                if not success or frame is None:
                    continue
                height, width, _ = frame.shape
                bytes_per_line = 3 * width
                qimage = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
                pixmap = QPixmap.fromImage(qimage)
                scaled = pixmap.scaledToWidth(self.thumb_size, Qt.SmoothTransformation)
                frames.append(scaled)
            cap.release()
            if frames:
                self.signal.finished.emit(self.path, frames)
        except Exception as e:
            print(f"Fehler bei Video-Vorschauloop: {e}")