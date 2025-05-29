from PyQt5.QtCore import QUrl, Qt, QTimer, QTime
from PyQt5.QtGui import QKeySequence, QPixmap, QColor, QPainter
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import QWidget, QLabel, QSizePolicy, QStackedLayout, QVBoxLayout, QShortcut, QApplication

import random


class LeftBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self.start_time = None
        self.duration = 5000  # 5 Sekunden
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.hide()

    def start(self):
        if self.duration>0:
            self.raise_()
            self.start_time = QTime.currentTime()
            self.timer.start(30)
            self.setGeometry(0, 0, 10, self.parent().height())
            self.show()

    def stop(self):
        self.timer.stop()
        self.hide()

    def paintEvent(self, event):

        if not self.start_time:
            return

        if self.duration == 0:
            return


        elapsed = self.start_time.msecsTo(QTime.currentTime())
        fraction = min(1.0, elapsed / self.duration)
        height = self.height() * (1.0 - fraction)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(255, 105, 180, 180)  # halbtransparent rosa
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, self.width(), int(height))

        if fraction >= 1.0:
            self.stop()


class DisplayWindow(QWidget):
    def __init__(self, media_folder):
        super().__init__()

        self.setWindowTitle("Anzeige")
        self.resize(800, 600)
        self.fullscreen = False
        self.media_folder = media_folder
        self.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("background-color: black; margin: 0px; padding: 0px; border: 0px;")

        self.supported_images = ('.jpg', '.jpeg', '.png')
        self.supported_videos = ('.mp4', '.mov', '.avi', '.mkv')
        self.media_files = []
        self.current_media_path = None

        self.image_label = QLabel("Kein Bild geladen")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: black; margin: 0px; padding: 0px; border: 0px;")
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setScaledContents(False)

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: black; margin: 0px; padding: 0px; border: 0px;")
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_widget.setMinimumSize(1, 1)

        self.media_player = QMediaPlayer()
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.error.connect(self.handle_player_error)

        self.media_player.setVolume(100)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status)

        self.stacked_layout = QStackedLayout()
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_layout.setSpacing(0)
        self.stacked_layout.addWidget(self.image_label)
        self.stacked_layout.addWidget(self.video_widget)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(self.stacked_layout)
        self.setLayout(layout)

        self.left_bar = LeftBar(self)
        self.left_bar.setGeometry(0, 0, 10, self.height())
        self.left_bar.raise_()

        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.left_bar.setGeometry(0, 0, 10, self.height())
        self.left_bar.raise_()

    def handle_player_error(self, error):
        print("QMediaPlayer Fehler:", error)
        print("Fehlermeldung:", self.media_player.errorString())

    def closeEvent(self, event):
        QApplication.quit()

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.showFullScreen() if self.fullscreen else self.showNormal()

    def show_random_media(self):
        if not self.media_files:
            self.image_label.setText("Kein Medium gefunden.")
            return

        media_path = self.current_media_path
        while len(self.media_files) > 1 and media_path == self.current_media_path:
            media_path = random.choice(self.media_files)

        self.show_specific_media(media_path, 0)

    def show_specific_media(self, media_path, seconds):

        print(f"is diashow ? {seconds}")
        self.current_media_path = media_path

        if media_path.lower().endswith(self.supported_images):
            self.media_player.stop()
            pixmap = QPixmap(media_path)
            scaled_pixmap = pixmap.scaled(
                self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
            self.stacked_layout.setCurrentIndex(0)

            self.left_bar.duration = seconds * 1000
            self.left_bar.start()

        else:
            self.image_label.clear()
            media = QMediaContent(QUrl.fromLocalFile(media_path))
            self.media_player.setMedia(media)
            self.media_player.setPosition(0)
            bounds = getattr(self, "video_ranges", {}).get(media_path)
            if bounds and "start" in bounds:
                self.media_player.setPosition(int(bounds["start"] * 1000))
            self.media_player.play()
            self.stacked_layout.setCurrentIndex(1)

            self.left_bar.duration= seconds * 1000
            self.left_bar.start()

    def handle_media_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.media_player.setPosition(0)
            self.media_player.play()

    def toggle_play_pause(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()