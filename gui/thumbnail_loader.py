"""Asynchronous thumbnail loading utilities."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QObject, QRunnable, Qt, Signal, Slot
from PySide6.QtGui import QImage, QPixmap


_THUMB_WIDTH = 180
_THUMB_HEIGHT = 135
_VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".m2ts", ".3gp", ".ogv"}

# In-memory LRU cache for pixmaps
_pixmap_cache: OrderedDict[str, QPixmap] = OrderedDict()
_MAX_CACHE_SIZE = 300


def get_cached_pixmap(path: str) -> QPixmap | None:
    """Get a cached pixmap if available."""
    if path in _pixmap_cache:
        _pixmap_cache.move_to_end(path)
        return _pixmap_cache[path]
    return None


def set_cached_pixmap(path: str, pixmap: QPixmap) -> None:
    """Cache a pixmap with LRU eviction."""
    if path in _pixmap_cache:
        _pixmap_cache.move_to_end(path)
        return
    _pixmap_cache[path] = pixmap
    while len(_pixmap_cache) > _MAX_CACHE_SIZE:
        _pixmap_cache.popitem(last=False)


def _video_first_frame(path: str) -> np.ndarray | None:
    """Extract the first frame of a video as RGB numpy array."""
    try:
        cap = cv2.VideoCapture(path)
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    except Exception:
        pass
    return None


def create_thumbnail(path: str, width: int = _THUMB_WIDTH, height: int = _THUMB_HEIGHT) -> QPixmap:
    """Create a thumbnail pixmap for an image or video file."""
    cached = get_cached_pixmap(path)
    if cached is not None:
        return cached

    suffix = Path(path).suffix.lower()
    pixmap: QPixmap | None = None

    if suffix in _VIDEO_EXTS:
        frame = _video_first_frame(path)
        if frame is not None:
            h, w, ch = frame.shape
            image = QImage(frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(image)
    else:
        pixmap = QPixmap(path)

    if pixmap is None or pixmap.isNull():
        # Return a colored placeholder
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.darkGray)
        set_cached_pixmap(path, pixmap)
        return pixmap

    scaled = pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    set_cached_pixmap(path, scaled)
    return scaled


class ThumbnailLoaderSignals(QObject):
    loaded = Signal(str, object)  # path, QPixmap


class ThumbnailLoader(QRunnable):
    """Background thumbnail loader for QThreadPool."""

    def __init__(self, path: str, width: int = _THUMB_WIDTH, height: int = _THUMB_HEIGHT):
        super().__init__()
        self.path = path
        self.width = width
        self.height = height
        self.signals = ThumbnailLoaderSignals()

    @Slot()
    def run(self):
        try:
            pixmap = create_thumbnail(self.path, self.width, self.height)
            self.signals.loaded.emit(self.path, pixmap)
        except Exception:
            # Emit a gray placeholder on failure
            pixmap = QPixmap(self.width, self.height)
            pixmap.fill(Qt.GlobalColor.darkGray)
            self.signals.loaded.emit(self.path, pixmap)
