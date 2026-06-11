"""Batch image similarity processing module."""

from __future__ import annotations

import json
import os
import shutil
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from tqdm import tqdm

from .similarity import ImageSimilarity
from .utils import get_worker_cpu_count, list_image_files

# Cap worker threads at 90% of CPU cores to keep the system responsive
_CPU_COUNT = get_worker_cpu_count()


class CancelledError(Exception):
    """Raised when scan task is cancelled."""
    pass


# Process-pool worker state: one ImageSimilarity instance per process
_worker_sim: ImageSimilarity | None = None


def _init_worker(method: str, threshold: float) -> None:
    """Initialize worker process with a reusable ImageSimilarity instance."""
    global _worker_sim
    _worker_sim = ImageSimilarity(method=method, threshold=threshold)


def _compare_pair(args: tuple) -> tuple[Path, Path, float] | None:
    """Worker function for parallel comparison (must be top-level for pickling)."""
    global _worker_sim
    f1, f2 = args
    try:
        score = _worker_sim.compare(f1, f2)
        return (f1, f2, score) if score >= _worker_sim.threshold else None
    except Exception:
        return None


class BatchProcessor:
    """Batch process image similarity checks, support deduplication and grouping."""

    def __init__(
        self,
        method: str = "phash",
        threshold: float = 0.85,
        progress: bool = True,
        cancelled: Callable[[], bool] | None = None,
    ):
        self.similarity = ImageSimilarity(method=method, threshold=threshold)
        self.threshold = threshold
        self.progress = progress
        self.cancelled = cancelled or (lambda: False)

    def _check_cancelled(self) -> None:
        if self.cancelled():
            raise CancelledError()

    def find_duplicates(
        self,
        image_dir: str | Path,
        *,
        recursive: bool = True,
        method: str | None = None,
    ) -> list[tuple[Path, Path, float]]:
        image_dir = Path(image_dir)
        files = list_image_files(image_dir, recursive=recursive)
        files = [f for f in files if f.is_file()]

        if len(files) < 2:
            return []

        if (method or self.similarity.method) == "gpu":
            from .gpu_similarity import GPUSimilarity

            gpu_sim = GPUSimilarity()

            def progress_callback(current: int, total: int) -> bool:
                return self.cancelled()

            return gpu_sim.find_duplicates(
                files,
                threshold=self.threshold,
                progress_callback=progress_callback,
            )

        active_method = method or self.similarity.method
        use_multiprocess = active_method in ("ssim", "orb")

        # Set worker instance for the current process (used by ThreadPoolExecutor)
        global _worker_sim
        _worker_sim = self.similarity

        # Build all comparison pairs
        pairs = []
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                pairs.append((files[i], files[j]))

        duplicates: list[tuple[Path, Path, float]] = []

        if use_multiprocess:
            # CPU-heavy methods: use ProcessPoolExecutor to bypass GIL
            with ProcessPoolExecutor(
                max_workers=_CPU_COUNT,
                initializer=_init_worker,
                initargs=(active_method, self.threshold),
            ) as executor:
                futures = {executor.submit(_compare_pair, p): p for p in pairs}
                iterable = as_completed(futures)
                if self.progress:
                    iterable = tqdm(iterable, total=len(pairs), desc="Scanning images")
                for future in iterable:
                    self._check_cancelled()
                    result = future.result()
                    if result is not None:
                        duplicates.append(result)
        else:
            # I/O-bound or lightweight methods: use ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=_CPU_COUNT) as executor:
                futures = {executor.submit(_compare_pair, p): p for p in pairs}
                iterable = as_completed(futures)
                if self.progress:
                    iterable = tqdm(iterable, total=len(pairs), desc="Scanning images")
                for future in iterable:
                    self._check_cancelled()
                    result = future.result()
                    if result is not None:
                        duplicates.append(result)

        duplicates.sort(key=lambda x: x[2], reverse=True)
        return duplicates

    def group_similar(
        self,
        image_dir: str | Path,
        *,
        recursive: bool = True,
        method: str | None = None,
    ) -> list[list[Path]]:
        duplicates = self.find_duplicates(image_dir, recursive=recursive, method=method)

        parent: dict[Path, Path] = {}

        def find(x: Path) -> Path:
            if parent.get(x, x) != x:
                parent[x] = find(parent[x])
            return parent.get(x, x)

        def union(x: Path, y: Path) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for a, b, _ in duplicates:
            union(a, b)

        groups: dict[Path, list[Path]] = {}
        files = list_image_files(Path(image_dir), recursive=recursive)
        for f in files:
            root = find(f)
            groups.setdefault(root, []).append(f)

        return [g for g in groups.values() if len(g) > 1]

    def remove_duplicates(
        self,
        image_dir: str | Path,
        output_dir: str | Path | None = None,
        *,
        strategy: str = "keep_first",
        recursive: bool = True,
        method: str | None = None,
    ) -> list[Path]:
        image_dir = Path(image_dir)
        groups = self.group_similar(image_dir, recursive=recursive, method=method)
        removed: list[Path] = []

        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        for group in groups:
            if strategy == "keep_best":
                keeper = max(group, key=lambda p: self._image_size(p))
            else:
                keeper = group[0]

            for f in group:
                if f == keeper:
                    continue
                if output_dir:
                    dest = output_dir / f.name
                    shutil.move(str(f), str(dest))
                    removed.append(dest)
                else:
                    f.unlink()
                    removed.append(f)

        return removed

    @staticmethod
    def _image_size(path: Path) -> int:
        try:
            from PIL import Image
            with Image.open(path) as img:
                return img.width * img.height
        except Exception:
            return 0

    def export_report(
        self,
        duplicates: list[tuple[Path, Path, float]],
        output_path: str | Path,
    ) -> None:
        output_path = Path(output_path)
        report = {
            "threshold": self.threshold,
            "method": self.similarity.method,
            "total_pairs": len(duplicates),
            "duplicates": [
                {
                    "image1": str(p1),
                    "image2": str(p2),
                    "similarity": round(score, 4),
                }
                for p1, p2, score in duplicates
            ],
        }
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
