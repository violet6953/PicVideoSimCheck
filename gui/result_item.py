"""Result item widget: thumbnail + checkbox + metadata."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from .thumbnail_loader import ThumbnailLoader


class ResultItemWidget(QFrame):
    """Widget representing a single image/video in a similarity group."""

    clicked = Signal(str)
    selection_changed = Signal()

    def __init__(self, path: str, name: str, resolution: str, size_text: str,
                 duration_text: str = "", is_video: bool = False, parent=None):
        super().__init__(parent)
        self.path = path
        self.is_video = is_video
        self.setObjectName("resultItemVideo" if is_video else "resultItem")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(196, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Top row: checkbox + optional video indicator
        top_layout = QHBoxLayout()
        top_layout.setSpacing(4)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.checkbox = QCheckBox(self)
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        top_layout.addWidget(self.checkbox)
        top_layout.addStretch()

        if is_video and duration_text:
            indicator = QLabel(duration_text)
            indicator.setObjectName("videoIndicator")
            top_layout.addWidget(indicator)

        layout.addLayout(top_layout)

        # Thumbnail
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(180, 135)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet("background-color: #0f172a; border-radius: 6px;")
        layout.addWidget(self.thumb_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Info
        self.filename_label = QLabel(name)
        self.filename_label.setObjectName("filename")
        self.filename_label.setWordWrap(False)
        self.filename_label.setToolTip(name)

        meta_parts = [p for p in [resolution, size_text, duration_text] if p]
        self.meta_label = QLabel(" · ".join(meta_parts))
        self.meta_label.setObjectName("meta")

        layout.addWidget(self.filename_label)
        layout.addWidget(self.meta_label)
        layout.addStretch()

        # Load thumbnail async
        self._load_thumbnail()

    def _load_thumbnail(self) -> None:
        from .thumbnail_loader import get_cached_pixmap
        cached = get_cached_pixmap(self.path)
        if cached is not None:
            self.thumb_label.setPixmap(cached)
            return

        loader = ThumbnailLoader(self.path, 180, 135)
        loader.signals.loaded.connect(self._on_thumbnail_loaded)
        QThreadPool.globalInstance().start(loader)

    def _on_thumbnail_loaded(self, path: str, pixmap) -> None:
        if path != self.path:
            return
        self.thumb_label.setPixmap(pixmap)

    def _on_checkbox_changed(self) -> None:
        selected = self.checkbox.isChecked()
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.selection_changed.emit()

    def is_selected(self) -> bool:
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool) -> None:
        self.checkbox.setChecked(checked)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.path)
        super().mousePressEvent(event)
