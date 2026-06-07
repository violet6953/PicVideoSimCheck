"""Utility functions."""

from __future__ import annotations

from pathlib import Path

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp", ".heic"}
_VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".m2ts", ".3gp", ".ogv"}


def list_image_files(directory: str | Path, recursive: bool = True) -> list[Path]:
    """List all image files in a directory."""
    directory = Path(directory)
    if not directory.is_dir():
        return []

    pattern = "**/*" if recursive else "*"
    files = [
        p for p in directory.glob(pattern)
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS
    ]
    return sorted(files)


def list_video_files(directory: str | Path, recursive: bool = True) -> list[Path]:
    """List all video files in a directory."""
    directory = Path(directory)
    if not directory.is_dir():
        return []

    pattern = "**/*" if recursive else "*"
    files = [
        p for p in directory.glob(pattern)
        if p.is_file() and p.suffix.lower() in _VIDEO_EXTS
    ]
    return sorted(files)


def format_similarity(score: float) -> str:
    """Format similarity score as percentage."""
    return f"{score * 100:.2f}%"


def get_image_info(path: str | Path) -> tuple[int, int, int]:
    """Get image width, height and file size in bytes."""
    path = Path(path)
    file_size = path.stat().st_size if path.exists() else 0
    try:
        from PIL import Image
        with Image.open(path) as img:
            return img.width, img.height, file_size
    except Exception:
        return 0, 0, file_size


def get_video_info(path: str | Path) -> tuple[int, int, float, int]:
    """Get video width, height, duration (seconds) and file size in bytes.

    Returns:
        (width, height, duration_seconds, file_size_bytes)
        On failure: (0, 0, 0.0, file_size_bytes)
    """
    path = Path(path)
    file_size = path.stat().st_size if path.exists() else 0
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            cap.release()
            return 0, 0, 0.0, file_size

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        if fps > 0 and frame_count > 0:
            duration = frame_count / fps
        else:
            duration = 0.0

        return width, height, duration, file_size
    except Exception:
        return 0, 0, 0.0, file_size


def format_file_size(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def format_duration(seconds: float) -> str:
    """Format seconds to human-readable duration string (HH:MM:SS or MM:SS)."""
    if seconds <= 0:
        return "00:00"
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
