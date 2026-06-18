"""Asynchronous metadata loading for result items."""

from __future__ import annotations

import os
import re
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from src.utils import format_duration, format_file_size, get_image_info, get_video_info


def _sort_key(item: dict) -> tuple:
    """Sort key matching the original ScanWorker ordering."""
    name = item.get("name", "")
    has_copy_number = bool(re.search(r"\(\d+\)", name))
    has_duplicate_suffix = "副本" in name
    return (
        -item.get("size", 0),
        -(item.get("width", 0) * item.get("height", 0)),
        (has_copy_number, has_duplicate_suffix),
        item.get("ctime", 0),
    )


def _collect_image_info(img_path: str) -> dict:
    w, h, size = get_image_info(img_path)
    try:
        ctime = os.path.getctime(img_path)
    except Exception:
        ctime = 0
    return {
        "path": img_path,
        "name": Path(img_path).name,
        "width": w,
        "height": h,
        "size": size,
        "size_formatted": format_file_size(size),
        "resolution": f"{w}x{h}" if w and h else "未知",
        "ctime": ctime,
    }


def _collect_video_info(video_path: str) -> dict:
    w, h, duration, size = get_video_info(video_path)
    try:
        ctime = os.path.getctime(video_path)
    except Exception:
        ctime = 0
    return {
        "path": video_path,
        "name": Path(video_path).name,
        "width": w,
        "height": h,
        "duration": round(duration, 1),
        "size": size,
        "size_formatted": format_file_size(size),
        "resolution": f"{w}x{h}" if w and h else "未知",
        "duration_formatted": format_duration(duration),
        "ctime": ctime,
    }


class MetadataLoaderSignals(QObject):
    loaded = Signal(list)  # list[dict] sorted items


class GroupMetadataLoader(QRunnable):
    """Background loader that reads metadata for all paths in one group."""

    def __init__(self, paths: list[str], is_video: bool = False):
        super().__init__()
        self.paths = paths
        self.is_video = is_video
        self.signals = MetadataLoaderSignals()

    @Slot()
    def run(self):
        collector = _collect_video_info if self.is_video else _collect_image_info
        items: list[dict] = []
        for path in self.paths:
            try:
                items.append(collector(path))
            except Exception:
                items.append(
                    {
                        "path": path,
                        "name": Path(path).name,
                        "width": 0,
                        "height": 0,
                        "size": 0,
                        "size_formatted": format_file_size(0),
                        "resolution": "未知",
                    }
                )
        items.sort(key=_sort_key)
        for item in items:
            item.pop("ctime", None)
        self.signals.loaded.emit(items)
