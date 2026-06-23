"""Utility functions."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp", ".heic"}
_VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".m2ts", ".3gp", ".ogv"}

# Default CPU usage cap to leave headroom for other applications.
_CPU_USAGE_RATIO = 0.90


def configure_cpu_limits(ratio: float = _CPU_USAGE_RATIO) -> int:
    """Configure environment variables to cap CPU usage of numeric libraries.

    Must be called *before* importing numpy, cv2, torch, scikit-image, etc.
    for the limits to take effect.

    Returns:
        Number of worker threads/cores to use.
    """
    total = os.cpu_count() or 1
    limited = max(1, int(total * ratio))

    os.environ.setdefault("OMP_NUM_THREADS", str(limited))
    os.environ.setdefault("MKL_NUM_THREADS", str(limited))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(limited))
    os.environ.setdefault("NUMEXPR_NUM_THREADS", str(limited))
    os.environ.setdefault("VECLIB_MAXIMUM_THREADS", str(limited))

    return limited


def get_worker_cpu_count(ratio: float = _CPU_USAGE_RATIO) -> int:
    """Return the number of CPU workers appropriate for background tasks.

    Defaults to 90% of available cores so the OS and other apps remain
    responsive while scanning.
    """
    return max(1, int((os.cpu_count() or 1) * ratio))


def _scandir_list(directory: str | Path, exts: set[str], recursive: bool) -> list[Path]:
    """Fast directory listing using os.scandir / os.walk.

    ~2-3x faster than pathlib.glob for large directories.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return []

    results: list[Path] = []
    root_str = str(directory)

    if recursive:
        for root, _, files in os.walk(root_str):
            for fname in files:
                if os.path.splitext(fname)[1].lower() in exts:
                    results.append(Path(root) / fname)
    else:
        with os.scandir(root_str) as it:
            for entry in it:
                if entry.is_file() and os.path.splitext(entry.name)[1].lower() in exts:
                    results.append(Path(entry.path))

    return results


def list_image_files(directory: str | Path, recursive: bool = True) -> list[Path]:
    """List all image files in a directory."""
    return _scandir_list(directory, _IMAGE_EXTS, recursive)


def list_video_files(directory: str | Path, recursive: bool = True) -> list[Path]:
    """List all video files in a directory."""
    return _scandir_list(directory, _VIDEO_EXTS, recursive)


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


# ---------------------------------------------------------------------------
# Exact duplicate detection
# ---------------------------------------------------------------------------

_HASH_BLOCK_SIZE = 65536


def file_hash(path: str | Path, algorithm: str = "blake2b") -> str:
    """Return the hex digest of a file's contents."""
    hasher = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_HASH_BLOCK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def are_files_identical(path1: str | Path, path2: str | Path) -> bool:
    """Check whether two files are byte-for-byte identical.

    Uses a fast size check first; only computes a content hash when the
    sizes match. This is useful as a robust fallback for perceptual
    similarity methods: truly identical images always compare as similar,
    regardless of the chosen algorithm or threshold.
    """
    p1, p2 = Path(path1), Path(path2)
    try:
        stat1, stat2 = p1.stat(), p2.stat()
    except Exception:
        return False

    if stat1.st_size != stat2.st_size:
        return False

    # On platforms where st_ino/dev are meaningful, identical inode means
    # the same underlying file (hard link), so no need to read contents.
    if stat1.st_ino == stat2.st_ino and stat1.st_dev == stat2.st_dev:
        return True

    return file_hash(p1) == file_hash(p2)


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
