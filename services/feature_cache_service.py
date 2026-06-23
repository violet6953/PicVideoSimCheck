"""Persistent feature cache for image similarity algorithms.

Caches extracted features and perceptual hashes on disk so unchanged images
do not need to be re-processed across scans. Cache entries are keyed by the
file's absolute path, size, and modification time; any change invalidates the
cache entry automatically.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


# Module-level override for the cache directory. When None, the platform
# default is used; otherwise it must be a writable directory path.
_custom_cache_dir: Path | None = None


def _is_windows() -> bool:
    return sys.platform == "win32"


def get_default_cache_dir() -> Path:
    """Return the platform-default cache directory for PicSimProcess."""
    if _is_windows():
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            base = Path(local_app_data) / "PicSimProcess" / "cache"
        else:
            base = Path.home() / "AppData" / "Local" / "PicSimProcess" / "cache"
    else:
        base = Path.home() / ".cache" / "PicSimProcess"

    return base


def set_cache_dir(path: str | Path | None) -> None:
    """Set a custom cache directory.

    Pass None to reset to the platform default. The directory will be created
    if it does not exist. Raises ValueError if the path cannot be used.
    """
    global _custom_cache_dir
    if path is None:
        _custom_cache_dir = None
        return

    p = Path(path)
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise ValueError(f"无法创建缓存目录: {p}") from e

    if not p.is_dir():
        raise ValueError(f"缓存路径不是目录: {p}")

    _custom_cache_dir = p


def get_cache_dir() -> Path:
    """Return the currently effective cache directory."""
    if _custom_cache_dir is not None:
        return _custom_cache_dir
    return get_default_cache_dir()


def _get_user_cache_dir() -> Path:
    """Return the active cache directory (custom or default).

    On Windows this is ``%LOCALAPPDATA%\\PicSimProcess\\cache`` by default.
    On other platforms it falls back to ``~/.cache/PicSimProcess``.
    """
    base = get_cache_dir()
    base.mkdir(parents=True, exist_ok=True)
    return base


def _get_cache_root() -> Path:
    """Return the root cache directory for features and hashes."""
    root = _get_user_cache_dir() / "features"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _cache_key(path: str | Path) -> str:
    """Generate a stable cache key from file path, size and mtime.

    The key changes when the file is edited, moved, or renamed, ensuring
    stale features are not reused.
    """
    p = Path(path)
    # Use absolute path so the same file reached via different paths shares
    # a cache entry only when its canonical absolute path matches.
    abs_path = os.path.abspath(str(p))
    try:
        stat = p.stat()
        size = stat.st_size
        mtime_ns = stat.st_mtime_ns
    except Exception:
        size = 0
        mtime_ns = 0

    raw = f"{abs_path}\x00{size}\x00{mtime_ns}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _video_cache_key(
    path: str | Path,
    frames_per_second: float,
    max_frames_per_video: int,
    min_frames_per_video: int,
) -> str:
    """Generate a cache key for video frame features.

    Includes the video sampling parameters so that changing fps or frame limits
    automatically invalidates cached features.
    """
    base_key = _cache_key(path)
    raw = (
        f"{base_key}\x00"
        f"{frames_per_second}\x00"
        f"{max_frames_per_video}\x00"
        f"{min_frames_per_video}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _shard_path(root: Path, key: str, suffix: str) -> Path:
    """Shard cache files into subdirectories by the first two hex chars."""
    return root / key[:2] / f"{key}{suffix}"


# ---------------------------------------------------------------------------
# GPU ResNet50 feature cache
# ---------------------------------------------------------------------------

def load_feature(path: str | Path) -> "np.ndarray | None":
    """Load a cached ResNet50 feature vector for *path*, or None on miss/error."""
    import numpy as np

    key = _cache_key(path)
    cache_path = _shard_path(_get_cache_root() / "gpu", key, ".npy")
    if not cache_path.exists():
        return None

    try:
        return np.load(cache_path, allow_pickle=False)
    except Exception:
        # Corrupted or incompatible cache file; remove it.
        try:
            cache_path.unlink()
        except Exception:
            pass
        return None


def save_feature(path: str | Path, feature: "np.ndarray") -> None:
    """Save a ResNet50 feature vector for *path* to disk."""
    key = _cache_key(path)
    cache_path = _shard_path(_get_cache_root() / "gpu", key, ".npy")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Use a temporary file and rename for atomicity.  np.save appends .npy
        # automatically when the path does not end with .npy, so keep the same
        # extension on the temp file.
        temp_path = cache_path.with_suffix(".tmp.npy")
        import numpy as np

        np.save(temp_path, feature)
        temp_path.replace(cache_path)
    except Exception:
        # If caching fails, the scan should continue without it.
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Video frame feature cache
# ---------------------------------------------------------------------------

def load_video_features(
    path: str | Path,
    frames_per_second: float,
    max_frames_per_video: int,
    min_frames_per_video: int,
) -> "np.ndarray | None":
    """Load cached video frame features for *path*, or None on miss/error.

    The returned array has shape (num_frames, 2048) where num_frames varies
    depending on the video length and sampling parameters.
    """
    import numpy as np

    key = _video_cache_key(
        path, frames_per_second, max_frames_per_video, min_frames_per_video
    )
    cache_path = _shard_path(_get_cache_root() / "video", key, ".npy")
    if not cache_path.exists():
        return None

    try:
        return np.load(cache_path, allow_pickle=False)
    except Exception:
        try:
            cache_path.unlink()
        except Exception:
            pass
        return None


def save_video_features(
    path: str | Path,
    features: "np.ndarray",
    frames_per_second: float,
    max_frames_per_video: int,
    min_frames_per_video: int,
) -> None:
    """Save video frame features (num_frames, 2048) to disk."""
    key = _video_cache_key(
        path, frames_per_second, max_frames_per_video, min_frames_per_video
    )
    cache_path = _shard_path(_get_cache_root() / "video", key, ".npy")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        temp_path = cache_path.with_suffix(".tmp.npy")
        import numpy as np

        np.save(temp_path, features)
        temp_path.replace(cache_path)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Perceptual hash cache
# ---------------------------------------------------------------------------

def load_hash(path: str | Path, method: str) -> "imagehash.ImageHash | None":
    """Load a cached perceptual hash for *path* and *method*, or None."""
    import imagehash

    key = _cache_key(path)
    cache_path = _shard_path(
        _get_cache_root() / "hashes" / method.lower(), key, ".json"
    )
    if not cache_path.exists():
        return None

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return imagehash.hex_to_hash(data["hash"])
    except Exception:
        try:
            cache_path.unlink()
        except Exception:
            pass
        return None


def save_hash(path: str | Path, method: str, hash_value: "imagehash.ImageHash") -> None:
    """Save a perceptual hash for *path* and *method* to disk."""
    key = _cache_key(path)
    cache_path = _shard_path(
        _get_cache_root() / "hashes" / method.lower(), key, ".json"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        temp_path = cache_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps({"hash": str(hash_value)}, ensure_ascii=False),
            encoding="utf-8",
        )
        temp_path.replace(cache_path)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Cache management utilities
# ---------------------------------------------------------------------------

def clear_cache(root_dir: str | Path | None = None) -> int:
    """Remove all cached features and hashes. Returns number of files removed.

    Args:
        root_dir: Optional cache root to clear. When omitted, the currently
            configured cache root is used.
    """
    if root_dir is None:
        root = _get_cache_root()
    else:
        root = Path(root_dir) / "features"

    removed = 0
    try:
        for subdir in ["gpu", "hashes", "video"]:
            subroot = root / subdir
            if not subroot.exists():
                continue
            for path in subroot.rglob("*"):
                if path.is_file():
                    try:
                        path.unlink()
                        removed += 1
                    except Exception:
                        pass
    except Exception:
        pass
    return removed


def get_cache_size_bytes(root_dir: str | Path | None = None) -> int:
    """Return total size of the feature cache in bytes.

    Args:
        root_dir: Optional cache root to measure. When omitted, the currently
            configured cache root is used.
    """
    if root_dir is None:
        root = _get_cache_root()
    else:
        root = Path(root_dir) / "features"

    total = 0
    try:
        for path in root.rglob("*"):
            if path.is_file():
                try:
                    total += path.stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    return total
