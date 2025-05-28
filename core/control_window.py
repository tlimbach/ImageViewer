import hashlib
import json
import os
import random

from PyQt5.QtCore import QTimer, Qt, QThreadPool
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QHBoxLayout, QSplitter, QFileDialog, QScrollArea, QWidget, QSlider, QGridLayout, QLineEdit, \
    QLabel, QProgressBar, QPushButton, QCheckBox, QGroupBox, QVBoxLayout, QSizePolicy, QApplication, QMessageBox

from core.common import ThumbnailSignal, CachedThumbnailLoaderImage, FRAMES_PER_THUMBNAIL, THUMBNAIL_DELAY, \
    THUMBNAIL_LOAD_THREAD_COUNT
from ui.video_thumbnail_loader import VideoThumbnailLoader
from ui.video_thumbnail_widget import VideoThumbnailWidget


class ControlWindow(QWidget):
    def __init__(self, display_window):
        super().__init__()
        self.settings_path = "settings.json"
        self.display_window = display_window

        # Letztes Verzeichnis laden
        last_folder = self.load_last_folder()
        if last_folder and os.path.isdir(last_folder):
            self.display_window.media_folder = last_folder
        self.is_closing = False
        self.volume_settings = self.load_volume_settings()
        self.thumbnail_cache_folder = os.path.join(os.getcwd(), ".thumbcache")
        os.makedirs(self.thumbnail_cache_folder, exist_ok=True)

        self.thumbnail_cache = {}  # Pfad → Liste von QPixmaps
        self.active_thumbnail_paths = set()
        self.setWindowTitle("Steuerung")
        self.display_window = display_window
        self.thumbnail_size = 400
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(THUMBNAIL_LOAD_THREAD_COUNT)
        self.thumbnail_signals = []
        self.path_to_label = {}

        self.video_ranges = self.load_video_ranges()
        self.display_window.video_ranges = self.video_ranges

        self.choose_folder_button = QPushButton("Verzeichnis wählen")
        self.choose_folder_button.clicked.connect(self.choose_media_folder)

        self.next_button = QPushButton("Zufälliges Medium")
        self.next_button.clicked.connect(self.display_window.show_random_media)

        self.playpause_button = QPushButton("Play / Pause")
        self.playpause_button.clicked.connect(self.display_window.toggle_play_pause)

        self.fullscreen_button = QPushButton("Vollbild umschalten")
        self.fullscreen_button.clicked.connect(self.display_window.toggle_fullscreen)

        self.thumb_width_input = QLineEdit()
        self.thumb_width_input.setPlaceholderText("Breite Vorschau z. B. 120")
        self.thumb_width_input.returnPressed.connect(self.update_thumbnails_from_input)

        self.delete_button = QPushButton("Ausgewähltes Medium löschen")
        self.delete_button.clicked.connect(self.delete_selected_media)

        self.cleanup_button = QPushButton("Titel bereinigen")
        self.cleanup_button.clicked.connect(self.cleanup_duplicates)

        self.tag_checkbox_group = QGroupBox("Verfügbare Schlagwörter")
        self.tag_checkbox_layout = QVBoxLayout()
        self.tag_checkbox_group.setLayout(self.tag_checkbox_layout)

        self.tag_checkbox_scroll = QScrollArea()
        self.tag_checkbox_scroll.setWidgetResizable(True)
        self.tag_checkbox_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tag_checkbox_scroll.setWidget(self.tag_checkbox_group)

        self.thumbnail_progress_label = QLabel("Thumbnails geladen: 0 / 0")


        self.start_input = QLineEdit()
        self.start_input.setPlaceholderText("Startsekunde")

        self.end_input = QLineEdit()
        self.end_input.setPlaceholderText("Endsekunde")

        self.range_button = QPushButton("Bereich übernehmen")
        self.range_button.clicked.connect(self.set_video_range)

        self.ignore_range_checkbox = QCheckBox("Zeitbereich ignorieren")
        self.ignore_range_checkbox.setChecked(False)

        self.tag_save_button = QPushButton("Schlagwörter übernehmen")
        self.tag_save_button.clicked.connect(self.set_tags_for_current_media)

        from PyQt5.QtWidgets import QComboBox

        self.tag_input = QLineEdit()

        self.tag_combobox = QComboBox()
        self.tag_combobox.setEditable(True)
        self.tag_combobox.setInsertPolicy(QComboBox.NoInsert)
        self.tag_combobox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.tag_combobox.setPlaceholderText("Tag auswählen oder neu eingeben…")
        self.tag_combobox.lineEdit().returnPressed.connect(self.add_tag_from_combobox)
        self.tag_combobox.activated.connect(lambda _: self.add_tag_from_combobox())

        self.tag_container_widget = QWidget()
        self.tag_container_layout = QVBoxLayout()
        self.tag_container_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_container_widget.setLayout(self.tag_container_layout)
        self.tag_container_layout.addWidget(self.tag_input)
        self.tag_container_layout.addWidget(self.tag_combobox)


        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)

        self.video_time_label = QLabel("0.0 s")

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.preview_container = QWidget()
        self.preview_layout = QGridLayout()
        self.preview_container.setLayout(self.preview_layout)
        self.scroll_area.setWidget(self.preview_container)

        self.video_slider = QSlider(Qt.Horizontal)
        self.video_slider.setRange(0, 1000)  # Dummy-Wert, wird bei jedem Video gesetzt
        self.video_slider.sliderPressed.connect(self.slider_pressed)
        self.video_slider.sliderReleased.connect(self.slider_released)
        self.video_slider.sliderMoved.connect(self.slider_moved)
        self.slider_was_moved = False

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.valueChanged.connect(self.change_volume)

        self.slideshow_timer = QTimer()
        self.slideshow_timer.timeout.connect(self.show_next_random_media)
        self.slideshow_running = False

        self.slideshow_duration_input = QLineEdit()
        self.slideshow_duration_input.setPlaceholderText("Sekunden pro Medium")
        self.slideshow_duration_input.setFixedWidth(100)

        self.start_slideshow_button = QPushButton("Diashow starten")
        self.start_slideshow_button.clicked.connect(self.start_slideshow)

        self.stop_slideshow_button = QPushButton("Diashow stoppen")
        self.stop_slideshow_button.clicked.connect(self.stop_slideshow)

        slideshow_controls = QHBoxLayout()
        slideshow_controls.addWidget(self.slideshow_duration_input)
        slideshow_controls.addWidget(self.start_slideshow_button)
        slideshow_controls.addWidget(self.stop_slideshow_button)



        # Definition und Aufbau von button_layout
        button_layout = QVBoxLayout()
        button_layout.insertWidget(0, self.choose_folder_button)
        button_layout.addLayout(slideshow_controls)
        # button_layout.addWidget(self.next_button)
        button_layout.addWidget(self.playpause_button)
        button_layout.addWidget(self.fullscreen_button)
        button_layout.addWidget(self.thumb_width_input)
        button_layout.addWidget(self.delete_button)
        time_range_layout = QHBoxLayout()
        time_range_layout.addWidget(self.start_input)
        time_range_layout.addWidget(self.end_input)
        time_range_layout.addWidget(self.ignore_range_checkbox)
        button_layout.addLayout(time_range_layout)
        button_layout.addWidget(self.range_button)
        button_layout.addWidget(self.progress_bar)
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(self.video_slider)
        slider_layout.addWidget(self.video_time_label)
        button_layout.addLayout(slider_layout)
        button_layout.addWidget(QLabel("Lautstärke"))
        button_layout.addWidget(self.volume_slider)
        button_layout.addWidget(self.ignore_range_checkbox)
        button_layout.addWidget(QLabel("Tags für Datei"))
        button_layout.addWidget(self.tag_container_widget)
        button_layout.addWidget(self.tag_save_button)
        button_layout.addWidget(self.cleanup_button)
        button_layout.addWidget(self.tag_checkbox_scroll)
        button_layout.addWidget(self.thumbnail_progress_label)

        button_widget = QWidget()
        button_widget.setLayout(button_layout)
        MAX_WIDTH = 280
        button_widget.setMinimumWidth(MAX_WIDTH)
        button_widget.setMaximumWidth(MAX_WIDTH)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(button_widget)
        splitter.addWidget(self.scroll_area)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 9)

        layout = QHBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

        QTimer.singleShot(100, self.load_media_files)

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_video_range)
        self.timer.start(300)
    # Entfernte Methoden: add_tag_from_input, refresh_tag_chips, remove_tag, show_tag_suggestions, insert_tag_to_input

    def load_and_update_tags(self):
        self.media_tags = self.load_media_tags()
        self.update_tag_checkboxes()


    def choose_media_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Verzeichnis auswählen")
        if folder:
            self.display_window.media_folder = folder
            self.save_last_folder(folder)
            self.load_media_files()

    def save_last_folder(self, folder_path):
        try:
            with open(self.settings_path, "w") as f:
                json.dump({"last_folder": folder_path}, f)
        except Exception as e:
            print(f"Fehler beim Speichern des letzten Ordners: {e}")

    def load_last_folder(self):
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r") as f:
                    data = json.load(f)
                    return data.get("last_folder")
            except Exception as e:
                print(f"Fehler beim Laden des letzten Ordners: {e}")
        return None

    def start_slideshow(self):
        if self.slideshow_running:
            return
        try:
            seconds = float(self.slideshow_duration_input.text())
            if seconds <= 0:
                raise ValueError()
            self.slideshow_duration = seconds
            self.slideshow_running = True

            # Nur gefilterte Liste verwenden
            self.slideshow_media_files = list(getattr(self, 'filtered_files', self.display_window.media_files))
            self.show_next_random_media()
        except ValueError:
            print("Ungültige Eingabe für Diashow-Dauer")

    def stop_slideshow(self):
        self.slideshow_running = False
        self.slideshow_timer.stop()

    def show_next_random_media(self):
        if not self.slideshow_running:
            return

        if not hasattr(self, 'slideshow_media_files') or not self.slideshow_media_files:
            return

        # Kandidaten filtern, sodass das aktuelle Medium ausgeschlossen wird
        current_path = self.display_window.current_media_path
        candidates = [p for p in self.slideshow_media_files if p != current_path]
        if not candidates:
            candidates = self.slideshow_media_files  # Fallback, wenn nur ein Element vorhanden

        path = random.choice(candidates)
        self.display_window.show_specific_media(path)

        bounds = self.video_ranges.get(path, {})
        start_sec = bounds.get("start", 0)
        end_sec = bounds.get("end", 0)

        if path.lower().endswith(self.display_window.supported_videos):
            if end_sec <= start_sec:
                start_sec = 0
                end_sec = self.display_window.media_player.duration() / 1000 if self.display_window.media_player.duration() > 0 else self.slideshow_duration

            duration = end_sec - start_sec
            if duration <= 0:
                duration = self.slideshow_duration

            self.display_window.media_player.setPosition(int(start_sec * 1000))
            self.display_window.media_player.play()

            if self.slideshow_duration < duration:
                QTimer.singleShot(int(self.slideshow_duration * 1000), self.display_window.media_player.pause)
            else:
                repeat_interval = int(duration * 1000)
                repeat_times = int(self.slideshow_duration * 1000 // repeat_interval)
                for i in range(1, repeat_times):
                    QTimer.singleShot(i * repeat_interval,
                                      lambda: self.display_window.media_player.setPosition(int(start_sec * 1000)))

            total_duration_ms = int(self.slideshow_duration * 1000)
        else:
            total_duration_ms = int(self.slideshow_duration * 1000)

        self.slideshow_timer.start(total_duration_ms)

    def closeEvent(self, event):
        self.is_closing = True
        self.thread_pool.waitForDone(2000)  # Warte max. 2 Sekunden auf alle Thumbnail-Threads
        self.display_window.close()  # Wichtig: auch Display-Fenster schließen
        QApplication.quit()

    def update_volume_slider(self, path):
        volume = self.volume_settings.get(path, 50)
        self.volume_slider.blockSignals(True)  # verhindert triggern von save beim Setzen
        self.volume_slider.setValue(volume)
        self.volume_slider.blockSignals(False)
        self.display_window.media_player.setVolume(volume)

    def change_volume(self, value):
        path = self.display_window.current_media_path
        if path:
            self.volume_settings[path] = value
            self.display_window.media_player.setVolume(value)
            self.save_volume_settings()

    def load_volume_settings(self):
        if os.path.exists("volume_settings.json"):
            try:
                with open("volume_settings.json", "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_volume_settings(self):
        with open("volume_settings.json", "w") as f:
            json.dump(self.volume_settings, f, indent=2)

    def get_cache_file_paths(self, path):
        base = hashlib.sha256(path.encode('utf-8')).hexdigest()
        files = [os.path.join(self.thumbnail_cache_folder, f"{base}_{i}.jpg") for i in range(FRAMES_PER_THUMBNAIL)]
        return files

    def update_tag_checkboxes(self):
        from collections import Counter

        # Aktuelle Mediendateien
        current_files = set(self.display_window.media_files)

        # Filtere Tags nur für aktuelle Dateien, aber behalte alle Tags dauerhaft
        full_tags = self.media_tags
        filtered_tags = {path: tags for path, tags in full_tags.items() if path in current_files}
        self.filtered_media_tags = filtered_tags
        self.media_tags = full_tags  # alle Tags bleiben erhalten
        self.save_media_tags()  # Optional: speichert sofort die bereinigte Datei

        # Alte Checkboxen entfernen
        for i in reversed(range(self.tag_checkbox_layout.count())):
            widget = self.tag_checkbox_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Neue Checkboxen basierend auf vorhandenen Tags der aktuellen Dateien
        tag_counter = Counter()
        for tags_str in self.filtered_media_tags.values():
            tag_list = tags_str.strip().lower().split()
            tag_counter.update(tag_list)

        self.tag_checkboxes = {}
        for tag, count in sorted(tag_counter.items()):
            checkbox = QCheckBox(f"{tag} ({count})")
            checkbox.stateChanged.connect(self.apply_tag_filter)
            self.tag_checkbox_layout.addWidget(checkbox)
            self.tag_checkboxes[tag] = checkbox
        if hasattr(self, 'tag_combobox'):
            self.tag_combobox.clear()
            self.tag_combobox.addItems(sorted(tag_counter.keys()))

    def apply_tag_filter(self):
        selected_tags = [tag for tag, cb in self.tag_checkboxes.items() if cb.isChecked()]
        if not selected_tags:
            self.filtered_files = self.display_window.media_files
        else:
            filtered_files = []
            for path in self.display_window.media_files:
                tags_str = self.media_tags.get(path, "")
                tags_set = set(tags_str.lower().split())
                if tags_set & set(selected_tags):  # mindestens ein Tag passt
                    filtered_files.append(path)
            self.filtered_files = filtered_files

        self.populate_thumbnails(self.filtered_files)

    def load_media_tags(self):
        if os.path.exists("media_tags.json"):
            try:
                with open("media_tags.json", "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_media_tags(self):
        import tempfile
        import shutil

        temp_path = "media_tags.json.tmp"
        try:
            with open(temp_path, "w") as f:
                json.dump(self.media_tags, f, indent=2)
            shutil.move(temp_path, "media_tags.json")
        except Exception as e:
            print(f"Fehler beim sicheren Speichern der Tags: {e}")

    def set_tags_for_current_media(self):
        path = self.display_window.current_media_path
        if not path:
            return
        tags = self.tag_input.text().strip()
        self.media_tags[path] = tags
        self.save_media_tags()
        print(f"Tags für {os.path.basename(path)} gesetzt: {tags}")

    def cleanup_duplicates(self):
        from PyQt5.QtWidgets import QMessageBox
        folder = self.display_window.media_folder
        supported = self.display_window.supported_images + self.display_window.supported_videos
        seen = {}
        removed = 0
        for filename in os.listdir(folder):
            if filename.lower().endswith(supported):
                filepath = os.path.join(folder, filename)
                try:
                    filesize = os.path.getsize(filepath)
                    filehash = self.compute_hash(filepath)
                    if filehash is None:
                        continue
                    if filesize in seen:
                        if seen[filesize] == filehash:
                            os.remove(filepath)
                            removed += 1
                            if filepath in self.display_window.media_files:
                                self.display_window.media_files.remove(filepath)
                        else:
                            continue  # andere Datei mit gleicher Größe
                    else:
                        seen[filesize] = filehash
                except Exception as e:
                    print(f"Fehler bei Datei {filename}: {e}")

        self.display_window.show_random_media()
        self.populate_thumbnails()
        QMessageBox.information(self, "Bereinigt", f"{removed} Duplikate entfernt.")

    def compute_hash(self, filepath):
        import hashlib
        hash_sha256 = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except OSError:
            return None

    def load_video_ranges(self):
        if os.path.exists("video_ranges.json"):
            try:
                with open("video_ranges.json", "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_video_ranges(self):
        with open("video_ranges.json", "w") as f:
            json.dump(self.video_ranges, f, indent=2)

    def set_video_range(self):
        path = self.display_window.current_media_path
        if not path:
            return
        try:
            start = float(self.start_input.text())
            end = float(self.end_input.text())
            if end <= start:
                raise ValueError("Ende muss größer als Start sein")
        except ValueError:
            print("Ungültige Eingabe für Zeitbereich")
            return

        # Zeitbereich speichern
        self.video_ranges[path] = {"start": start, "end": end}
        self.save_video_ranges()
        print(f"Bereich für {os.path.basename(path)} gesetzt: {start}-{end}s")

        # Cache löschen
        for f in self.get_cache_file_paths(path):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"Fehler beim Löschen von Cache-Datei {f}: {e}")

        # Neuen Vorschaulader starten nur für dieses eine Video
        signal = ThumbnailSignal()
        self.thumbnail_signals.append(signal)
        signal.finished.connect(self.replace_thumbnail)
        self.active_thumbnail_paths.add(path)

        if all(os.path.exists(f) for f in self.get_cache_file_paths(path)):
            worker = CachedThumbnailLoaderImage(path, self.get_cache_file_paths(path), signal)
        else:
            worker = VideoThumbnailLoader(path, self.thumbnail_size, signal, self.video_ranges)

        self.thread_pool.start(worker)

    def check_video_range(self):
        path = self.display_window.current_media_path
        if not path or not path.lower().endswith(self.display_window.supported_videos):
            return

        # Position und Zeit anzeigen
        pos_ms = self.display_window.media_player.position()
        dur_ms = self.display_window.media_player.duration()
        if dur_ms > 0:
            self.video_time_label.setText(f"{pos_ms / 1000:.1f} s")
            if not self.slider_was_moved:
                self.video_slider.setValue(int(pos_ms / dur_ms * 1000))

        # Nur springen, wenn Zeitbereich aktiv und nicht ignoriert
        if self.ignore_range_checkbox.isChecked():
            return

        bounds = self.video_ranges.get(path)
        if not bounds:
            return

        current = pos_ms / 1000
        if current >= bounds["end"]:
            self.display_window.media_player.setPosition(int(bounds["start"] * 1000))

    def load_media_files(self):
        folder = self.display_window.media_folder
        files = os.listdir(folder)
        media_files = []
        total = len(files)
        self.progress_bar.setVisible(True)

        for i, f in enumerate(files):
            if f.lower().endswith(self.display_window.supported_images + self.display_window.supported_videos):
                media_files.append(os.path.join(folder, f))
            self.progress_bar.setValue(int((i + 1) / total * 100))
            QApplication.processEvents()

        self.display_window.media_files = media_files
        self.progress_bar.setVisible(False)
        self.populate_thumbnails()
        self.media_tags = self.load_media_tags()
        self.update_tag_checkboxes()

    def populate_thumbnails(self, files=None):
        if files is None:
            files = self.display_window.media_files

        self.loaded_thumbnail_count = 0
        self.total_thumbnail_count = len(files)
        self.thumbnail_progress_label.setText(f"Thumbnails geladen: 0 / {self.total_thumbnail_count}")
        self.active_thumbnail_paths.clear()
        self.thread_pool.clear()

        # Alle bestehenden Widgets im Grid entfernen
        for i in reversed(range(self.preview_layout.count())):
            widget = self.preview_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        col_count = 3
        for idx, path in enumerate(files):
            placeholder = QLabel("Lade...")
            placeholder.setFixedWidth(self.thumbnail_size)
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.mousePressEvent = lambda e, p=path: self.handle_thumbnail_click(p)
            self.preview_layout.addWidget(placeholder, idx // col_count, idx % col_count)
            self.path_to_label[path] = placeholder

            # Bilddateien sofort anzeigen
            if path.lower().endswith(self.display_window.supported_images):
                pixmap = QPixmap(path).scaledToWidth(self.thumbnail_size, Qt.SmoothTransformation)
                placeholder.setPixmap(pixmap)
                self.loaded_thumbnail_count += 1
                self.thumbnail_progress_label.setText(
                    f"Thumbnails geladen: {self.loaded_thumbnail_count} / {self.total_thumbnail_count}"
                )
                continue

            # Für Videos: Cache prüfen
            cache_files = self.get_cache_file_paths(path)
            signal = ThumbnailSignal()
            self.thumbnail_signals.append(signal)
            signal.finished.connect(self.replace_thumbnail)
            self.active_thumbnail_paths.add(path)

            if all(os.path.exists(f) for f in cache_files):
                worker = CachedThumbnailLoaderImage(path, cache_files, signal)
            else:
                worker = VideoThumbnailLoader(path, self.thumbnail_size, signal, self.video_ranges)

            self.thread_pool.start(worker)


    def handle_thumbnail_click(self, path):
        self.display_window.show_specific_media(path)
        self.update_range_fields(path)
        self.update_volume_slider(path)

    def update_range_fields(self, path):
        bounds = self.video_ranges.get(path)
        if bounds:
            self.start_input.setText(str(bounds.get("start", "")))
            self.end_input.setText(str(bounds.get("end", "")))
        else:
            self.start_input.clear()
            self.end_input.clear()

        tags = self.media_tags.get(path, "")
        self.tag_input.setText(tags)
        if hasattr(self, 'tag_combobox'):
            self.tag_combobox.setCurrentText("")

    def replace_thumbnail(self, path, image_or_frames):

        if getattr(self, "is_closing", False):
            return

        if path not in self.active_thumbnail_paths:
            return

        # Wenn image_or_frames eine Liste von QImage ist, wandle sie um
        if isinstance(image_or_frames[0], QImage):
            frames = [QPixmap.fromImage(img) for img in image_or_frames]
        else:
            frames = image_or_frames

        self.thumbnail_cache[path] = frames
        label = self.path_to_label.get(path)
        if label is None or not isinstance(label, QLabel):
            return

        index = self.preview_layout.indexOf(label)
        if index != -1:
            row, col, _, _ = self.preview_layout.getItemPosition(index)
            self.preview_layout.removeWidget(label)
            label.deleteLater()

            widget = VideoThumbnailWidget(frames, interval=THUMBNAIL_DELAY)
            widget.mousePressEvent = lambda e, p=path: self.handle_thumbnail_click(p)
            self.preview_layout.addWidget(widget, row, col)
            self.path_to_label[path] = widget

        self.active_thumbnail_paths.discard(path)
        self.loaded_thumbnail_count += 1
        self.thumbnail_progress_label.setText(
            f"Thumbnails geladen: {self.loaded_thumbnail_count} / {self.total_thumbnail_count}"
        )

        # Speichern im Cache-Verzeichnis
        cache_files = self.get_cache_file_paths(path)
        for pixmap, cache_path in zip(frames, cache_files):
            pixmap.save(cache_path, "JPEG")


    def update_thumbnails_from_input(self):
        try:
            width = int(self.thumb_width_input.text())
            if 20 <= width <= 1000:
                self.thumbnail_size = width
                self.populate_thumbnails()
            else:
                print("Bitte eine Breite zwischen 20 und 1000 eingeben.")
        except ValueError:
            print("Ungültige Eingabe. Bitte eine ganze Zahl angeben.")

    def delete_selected_media(self):
        path = self.display_window.current_media_path
        if not path:
            return

        confirm = QMessageBox.question(
            self,
            "Löschen bestätigen",
            f"Möchtest du diese Datei wirklich löschen?\n{os.path.basename(path)}",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            os.remove(path)
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Löschen", str(e))
            return

        if path in self.display_window.media_files:
            self.display_window.media_files.remove(path)

        self.display_window.show_random_media()
        self.populate_thumbnails()

    def slider_pressed(self):
        self.slider_was_moved = True

    def slider_released(self):
        self.slider_was_moved = False
        value = self.video_slider.value()
        duration = self.display_window.media_player.duration()
        if duration > 0:
            new_pos = int(duration * value / 1000)
            self.display_window.media_player.setPosition(new_pos)

    def slider_moved(self, value):
        duration = self.display_window.media_player.duration()
        if duration > 0:
            seconds = duration * value / 1000 / 1000
            self.video_time_label.setText(f"{seconds:.1f} s")



    # Neue Methode für Tagging mit QComboBox
    def add_tag_from_combobox(self):
        tag = self.tag_combobox.currentText().strip().lower()
        if not tag:
            return

        path = self.display_window.current_media_path
        if not path:
            return

        tags_str = self.media_tags.get(path, "")
        current_tags = tags_str.strip().split()
        if tag in current_tags:
            self.tag_combobox.setCurrentText("")
            return

        current_tags.append(tag)
        self.media_tags[path] = " ".join(current_tags)
        self.save_media_tags()
        self.tag_input.setText(" ".join(current_tags))
        self.tag_combobox.setCurrentText("")
        print(f"Tag hinzugefügt für {os.path.basename(path)}: {tag}")
