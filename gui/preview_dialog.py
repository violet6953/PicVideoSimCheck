"""Preview dialog for images and videos with navigation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QPropertyAnimation,
    QRect,
    QEasingCurve,
    QTimer,
    QUrl,
    Qt,
)
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .explorer_utils import open_folder_and_select


def _format_time(ms: int) -> str:
    """Format milliseconds to MM:SS."""
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


class PreviewDialog(QDialog):
    """Dialog for previewing images/videos within a similarity group."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("预览")
        # 20:9 aspect ratio, height 800px
        self.resize(1778, 800)
        self._paths: list[str] = []
        self._current_index = 0
        self._is_video_list: list[bool] = []
        self._slide_anim: QPropertyAnimation | None = None
        self._old_snapshot: QLabel | None = None
        self._slider_dragging = False

        # Image zoom state
        self._original_pixmap: QPixmap | None = None
        self._image_scale: float = 1.0
        self._min_scale: float = 0.1
        self._max_scale: float = 5.0
        self._scale_step: float = 0.15

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Slide container (no internal layout; children manually positioned)
        self.slide_container = QFrame()
        self.slide_container.setObjectName("previewImageContainer")

        # Stacked widget for image/video
        self.stacked = QStackedWidget(self.slide_container)

        # Image page
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.wheelEvent = self._on_image_wheel
        self.stacked.addWidget(self.image_label)

        # Video page
        video_page = QWidget()
        video_layout = QVBoxLayout(video_page)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(0)

        self.video_widget = QVideoWidget()
        self.video_widget.mousePressEvent = self._on_video_clicked
        video_layout.addWidget(self.video_widget, 1)

        # Video controls
        controls = QWidget()
        controls.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.60);
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(16, 10, 16, 10)
        controls_layout.setSpacing(10)

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.15);
                color: white;
                border-radius: 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.25);
            }
        """)
        self.play_btn.clicked.connect(self._toggle_play)
        controls_layout.addWidget(self.play_btn)

        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("color: white; font-size: 12px; background: transparent;")
        controls_layout.addWidget(self.time_label)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 0)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background-color: white;
                width: 12px;
                height: 12px;
                border-radius: 6px;
                margin: -4px 0;
            }
            QSlider::sub-page:horizontal {
                background-color: #3b82f6;
                border-radius: 2px;
            }
        """)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.valueChanged.connect(self._on_slider_moved)
        controls_layout.addWidget(self.progress_slider, 1)

        self.duration_label = QLabel("00:00")
        self.duration_label.setStyleSheet("color: white; font-size: 12px; background: transparent;")
        controls_layout.addWidget(self.duration_label)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(0)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 3px;
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 1px;
            }
            QSlider::handle:horizontal {
                background-color: white;
                width: 10px;
                height: 10px;
                border-radius: 5px;
                margin: -3px 0;
            }
        """)
        self.volume_slider.valueChanged.connect(self._set_volume)
        controls_layout.addWidget(self.volume_slider)

        video_layout.addWidget(controls)
        self.stacked.addWidget(video_page)

        # Media player with audio output
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.0)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.positionChanged.connect(self._update_position)
        self.player.durationChanged.connect(self._update_duration)
        self.player.playbackStateChanged.connect(self._update_play_btn)

        # Click zones for left/right navigation (overlay on slide_container)
        self.left_zone = QLabel(self.slide_container)
        self.left_zone.setCursor(Qt.CursorShape.PointingHandCursor)
        self.left_zone.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border-top-left-radius: 12px;
                border-bottom-left-radius: 12px;
            }
            QLabel:hover {
                background-color: qlineargradient(
                    spread:pad, x1:0 y1:0, x2:1 y2:0,
                    stop:0 rgba(255, 255, 255, 0.10),
                    stop:1 rgba(255, 255, 255, 0)
                );
            }
        """)
        self.left_zone.mousePressEvent = lambda e: self.show_previous()

        self.right_zone = QLabel(self.slide_container)
        self.right_zone.setCursor(Qt.CursorShape.PointingHandCursor)
        self.right_zone.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
            }
            QLabel:hover {
                background-color: qlineargradient(
                    spread:pad, x1:0 y1:0, x2:1 y2:0,
                    stop:0 rgba(255, 255, 255, 0),
                    stop:1 rgba(255, 255, 255, 0.10)
                );
            }
        """)
        self.right_zone.mousePressEvent = lambda e: self.show_next()

        layout.addWidget(self.slide_container, 1)

        # Info row
        info_layout = QHBoxLayout()
        info_layout.addStretch()
        self.counter_label = QLabel("")
        self.counter_label.setStyleSheet("color: #3b82f6; font-weight: bold;")
        info_layout.addWidget(self.counter_label)

        self.filename_label = QLabel("")
        self.filename_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filename_label.mousePressEvent = lambda e: self._open_in_folder()
        info_layout.addWidget(self.filename_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        self.close_btn = QPushButton("关闭")
        self.close_btn.setObjectName("secondary")
        self.close_btn.clicked.connect(self.close)
        close_layout.addWidget(self.close_btn)
        layout.addLayout(close_layout)

    def _update_geometry(self) -> None:
        """Update manually positioned children of slide_container."""
        w = self.slide_container.width()
        h = self.slide_container.height()

        self.stacked.setGeometry(0, 0, w, h)

        zone_width = max(60, w // 6)

        # Image: hot zones match the displayed image height.
        # Video: keep existing shorter height to avoid covering controls.
        is_video = bool(
            self._paths
            and self._current_index < len(self._is_video_list)
            and self._is_video_list[self._current_index]
        )
        if is_video:
            zone_height = int(h * 0.82)
            zone_y = 0
        else:
            pixmap = self.image_label.pixmap()
            if pixmap is not None:
                zone_height = pixmap.height()
                zone_y = max(0, (h - pixmap.height()) // 2)
            else:
                zone_height = int(h * 0.82)
                zone_y = 0

        self.left_zone.setGeometry(0, zone_y, zone_width, zone_height)
        self.right_zone.setGeometry(w - zone_width, zone_y, zone_width, zone_height)
        self.left_zone.raise_()
        self.right_zone.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_geometry()
        # Rescale current image to fit new size while preserving zoom level
        if self._paths and not self._is_video_list[self._current_index]:
            if self._original_pixmap is not None:
                self._apply_image_scale()
            else:
                self._load_image(self._paths[self._current_index])

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._update_geometry)

    def open_group(self, start_path: str, paths: list[str]) -> None:
        self._paths = paths
        self._is_video_list = []
        video_exts = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".m2ts", ".3gp", ".ogv"}
        for p in paths:
            self._is_video_list.append(Path(p).suffix.lower() in video_exts)
        try:
            self._current_index = paths.index(start_path)
        except ValueError:
            self._current_index = 0
        self._update_display(animate=False)
        self.show()
        self.raise_()
        self.activateWindow()

    def show_previous(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            self._update_display(direction="right")

    def show_next(self) -> None:
        if self._current_index < len(self._paths) - 1:
            self._current_index += 1
            self._update_display(direction="left")

    def _update_display(self, direction: str | None = None, animate: bool = True) -> None:
        if not self._paths:
            return

        path = self._paths[self._current_index]
        is_video = self._is_video_list[self._current_index]
        self.setWindowTitle(f"预览 - {Path(path).name}")
        self.counter_label.setText(f"{self._current_index + 1} / {len(self._paths)}")
        self.filename_label.setText(Path(path).name)
        self.filename_label.setToolTip(str(path))

        if direction and animate:
            self._run_slide_transition(path, is_video, direction)
            return

        # No animation
        self._cleanup_slide()
        if is_video:
            self.player.stop()
            self.stacked.setCurrentIndex(1)
            self.player.setSource(QUrl.fromLocalFile(path))
            self.player.play()
        else:
            self.player.stop()
            self.stacked.setCurrentIndex(0)
            self._load_image(path)

    def _load_image(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.image_label.setText("无法加载图片")
            self._original_pixmap = None
            self._image_scale = 1.0
            self._update_geometry()
            return
        self._original_pixmap = pixmap
        self._image_scale = 1.0
        self._apply_image_scale()
        self._update_geometry()

    def _apply_image_scale(self) -> None:
        """Scale the original pixmap by current zoom factor and display it."""
        if self._original_pixmap is None or self._original_pixmap.isNull():
            return
        base_w = self.stacked.width() - 40
        base_h = self.stacked.height() - 40
        target_w = int(base_w * self._image_scale)
        target_h = int(base_h * self._image_scale)
        scaled = self._original_pixmap.scaled(
            target_w,
            target_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def _on_image_wheel(self, event) -> None:
        """Zoom in/out with mouse wheel when viewing an image."""
        # Only zoom when the image page is visible
        if self.stacked.currentIndex() != 0:
            return
        delta = event.angleDelta().y()
        if delta > 0:
            self._image_scale = min(self._max_scale, self._image_scale + self._scale_step)
        else:
            self._image_scale = max(self._min_scale, self._image_scale - self._scale_step)
        self._apply_image_scale()
        self._update_geometry()

    def _cleanup_slide(self) -> None:
        """Remove any snapshot from previous animation and reset stacked position."""
        if self._slide_anim is not None:
            self._slide_anim.stop()
            self._slide_anim = None
        if self._old_snapshot is not None:
            self._old_snapshot.deleteLater()
            self._old_snapshot = None
        self._update_geometry()

    def _run_slide_transition(self, new_path: str, is_video: bool, direction: str) -> None:
        """Slide old content out and new content in."""
        self._cleanup_slide()

        container_width = self.slide_container.width()
        container_height = self.slide_container.height()

        # Create snapshot of current content
        self._old_snapshot = QLabel(self.slide_container)
        self._old_snapshot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._old_snapshot.setGeometry(0, 0, container_width, container_height)
        self._old_snapshot.setStyleSheet("""
            QLabel {
                background-color: #0a0f1a;
                border-radius: 12px;
            }
        """)
        self._old_snapshot.show()
        self._old_snapshot.raise_()

        current_idx = self.stacked.currentIndex()
        if current_idx == 0 and self.image_label.pixmap() is not None:
            self._old_snapshot.setPixmap(self.image_label.pixmap())
        elif current_idx == 1:
            video_pixmap = self.video_widget.grab()
            if not video_pixmap.isNull():
                self._old_snapshot.setPixmap(video_pixmap)
            else:
                self._old_snapshot.setText("[视频]")
        else:
            self._old_snapshot.setText("")

        # Prepare new content
        if is_video:
            self.player.stop()
            self.stacked.setCurrentIndex(1)
            self.player.setSource(QUrl.fromLocalFile(new_path))
            self.player.play()
        else:
            self.player.stop()
            self.stacked.setCurrentIndex(0)
            self._load_image(new_path)

        # Position stacked off-screen
        if direction == "left":
            start_x = container_width
            end_x = 0
            old_start_x = 0
            old_end_x = -container_width
        else:
            start_x = -container_width
            end_x = 0
            old_start_x = 0
            old_end_x = container_width

        self.stacked.setGeometry(start_x, 0, container_width, container_height)
        self.stacked.show()
        self.stacked.raise_()

        # Animate stacked in
        self._slide_anim = QPropertyAnimation(self.stacked, b"geometry")
        self._slide_anim.setDuration(280)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._slide_anim.setStartValue(QRect(start_x, 0, container_width, container_height))
        self._slide_anim.setEndValue(QRect(end_x, 0, container_width, container_height))

        # Animate old snapshot out
        old_anim = QPropertyAnimation(self._old_snapshot, b"geometry")
        old_anim.setDuration(280)
        old_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        old_anim.setStartValue(QRect(old_start_x, 0, container_width, container_height))
        old_anim.setEndValue(QRect(old_end_x, 0, container_width, container_height))

        def on_old_finished():
            if self._old_snapshot is not None:
                self._old_snapshot.deleteLater()
                self._old_snapshot = None

        old_anim.finished.connect(on_old_finished)
        old_anim.start()

        def on_finished():
            self._slide_anim = None
            self._update_geometry()

        self._slide_anim.finished.connect(on_finished)
        self._slide_anim.start()

    # ------------------------------------------------------------------
    # Video controls
    # ------------------------------------------------------------------

    def _toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_video_clicked(self, event) -> None:
        """Toggle play/pause when clicking on the video area."""
        self._toggle_play()

    def _update_play_btn(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸")
            self.play_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    color: white;
                    border-radius: 16px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #dc2626;
                }
            """)
        else:
            self.play_btn.setText("▶")
            self.play_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.15);
                    color: white;
                    border-radius: 16px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.25);
                }
            """)

    def _update_position(self, position: int) -> None:
        if not self._slider_dragging:
            self.progress_slider.setValue(position)
        self.time_label.setText(_format_time(position))

    def _update_duration(self, duration: int) -> None:
        self.progress_slider.setRange(0, duration)
        self.duration_label.setText(_format_time(duration))

    def _on_slider_pressed(self) -> None:
        self._slider_dragging = True

    def _on_slider_released(self) -> None:
        self._slider_dragging = False
        self.player.setPosition(self.progress_slider.value())

    def _on_slider_moved(self, value: int) -> None:
        if self._slider_dragging:
            self.time_label.setText(_format_time(value))

    def _set_volume(self, value: int) -> None:
        self.audio_output.setVolume(value / 100.0)

    # ------------------------------------------------------------------

    def _open_in_folder(self) -> None:
        if not self._paths:
            return
        path = self._paths[self._current_index]
        target = Path(path).resolve()
        if not target.exists():
            return
        open_folder_and_select(str(target))

    def mousePressEvent(self, event) -> None:
        # Click outside the preview area closes the dialog
        if self.slide_container:
            container_rect = self.slide_container.geometry()
            if not container_rect.contains(event.pos()):
                self.close()
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Left:
            self.show_previous()
        elif key == Qt.Key.Key_Right:
            self.show_next()
        elif key == Qt.Key.Key_Escape:
            self.close()
        elif key == Qt.Key.Key_Space:
            self._toggle_play()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.player.stop()
        self._cleanup_slide()
        super().closeEvent(event)
