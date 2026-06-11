"""GPU accelerated video similarity detection using keyframe + ResNet50 feature extraction."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image

from .gpu_similarity import GPUSimilarity
from .memory_utils import (
    AdaptiveBatchSizer,
    calculate_batch_size,
    get_gpu_memory_limit,
    get_video_processing_memory_limit,
)
from .utils import configure_cpu_limits, get_video_info, get_worker_cpu_count

configure_cpu_limits()  # Must run before importing cv2/torch below

import cv2
import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image

_CPU_COUNT = get_worker_cpu_count()
logger = logging.getLogger(__name__)


class VideoSimilarity:
    """Video similarity using keyframe sampling + deep learning feature extraction.

    Memory-aware batch processing:
    - Automatically detects system total memory, limits to 80% of RAM.
    - Processes videos in batches; keyframes are freed immediately after
      feature extraction.
    - Uses a lightweight memory monitor every N batches (not every batch).
    """

    def __init__(
        self,
        gpu_sim: GPUSimilarity | None = None,
        device: str | None = None,
        frames_per_second: float = 1.0,
        max_frames_per_video: int = 32,
        min_frames_per_video: int = 4,
    ):
        if gpu_sim is not None:
            self.gpu_sim = gpu_sim
        else:
            self.gpu_sim = GPUSimilarity(device=device)

        self.frames_per_second = frames_per_second
        self.max_frames_per_video = max(max_frames_per_video, min_frames_per_video)
        self.min_frames_per_video = max(min_frames_per_video, 1)
        self.device = self.gpu_sim.device
        self.transform = self.gpu_sim.transform
        self._load_pool = ThreadPoolExecutor(max_workers=_CPU_COUNT)

    def extract_keyframes(self, video_path: str | Path) -> list[np.ndarray]:
        """Extract evenly distributed keyframes from a video file.

        Returns RGB numpy arrays (H, W, 3) in uint8. Empty list on failure.
        """
        path = str(video_path)
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            cap.release()
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or total_frames <= 0:
            cap.release()
            return []

        duration = total_frames / fps
        target_count = max(
            self.min_frames_per_video,
            min(self.max_frames_per_video, int(duration * self.frames_per_second)),
        )

        if target_count >= total_frames:
            frame_indices = list(range(total_frames))
        else:
            step = total_frames / target_count
            frame_indices = [min(int(i * step), total_frames - 1) for i in range(target_count)]

        frames: list[np.ndarray] = []
        # Choose reading strategy based on sampling density.
        # - Sparse sampling (typical case: 32 frames from thousands): use seek.
        #   OpenCV/ffmpeg seeks to the nearest keyframe then decodes forward,
        #   which is much faster than decoding the whole video sequentially.
        # - Dense sampling (>50% of frames): sequential read is more efficient.
        sampling_ratio = target_count / total_frames if total_frames > 0 else 1.0
        use_sequential = sampling_ratio > 0.5

        if use_sequential:
            target_iter = iter(frame_indices)
            next_target = next(target_iter, None)
            frame_idx = 0
            while next_target is not None:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break
                if frame_idx == next_target:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frames.append(rgb)
                    next_target = next(target_iter, None)
                frame_idx += 1
        else:
            for idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret and frame is not None:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frames.append(rgb)

        cap.release()
        return frames

    def _extract_keyframes_parallel(
        self,
        video_paths: list[str | Path],
        indices: list[int],
    ) -> list[list[np.ndarray]]:
        """Extract keyframes from multiple videos in parallel using the class pool.

        Reuses self._load_pool to avoid ThreadPoolExecutor creation overhead.
        Returns a list aligned with *indices* (same order).
        """
        def _worker(idx: int) -> list[np.ndarray]:
            try:
                return self.extract_keyframes(video_paths[idx])
            except Exception:
                return []

        futures = {self._load_pool.submit(_worker, idx): i for i, idx in enumerate(indices)}
        results: list[list[np.ndarray]] = [[] for _ in indices]
        for future in futures:
            pos = futures[future]
            try:
                results[pos] = future.result()
            except Exception:
                results[pos] = []
        return results

    def _flatten_frames(
        self,
        all_frames: list[list[np.ndarray]],
    ) -> tuple[list[np.ndarray], list[tuple[int, int]]]:
        """Flatten nested frame lists into a single list + index mapping."""
        flat: list[np.ndarray] = []
        mapping: list[tuple[int, int]] = []
        for vi, frames in enumerate(all_frames):
            for fi, frame in enumerate(frames):
                flat.append(frame)
                mapping.append((vi, fi))
        return flat, mapping

    def _extract_frame_features(
        self,
        frames: list[np.ndarray],
        batch_size: int = 64,
        progress_callback: Callable[[int, int], bool] | None = None,
    ) -> np.ndarray:
        """Extract ResNet50 features for RGB numpy arrays."""
        if not frames:
            return np.zeros((0, 2048), dtype=np.float32)

        total = len(frames)
        features: list[np.ndarray] = []

        def _preprocess(frame: np.ndarray) -> torch.Tensor | None:
            try:
                return self.transform(Image.fromarray(frame))
            except Exception:
                return None

        with torch.no_grad():
            for batch_start in range(0, total, batch_size):
                if progress_callback and progress_callback(batch_start, total):
                    raise CancelledError()

                batch_frames = frames[batch_start : batch_start + batch_size]
                futures = {
                    self._load_pool.submit(_preprocess, f): idx
                    for idx, f in enumerate(batch_frames)
                }
                tensors: list[torch.Tensor | None] = [None] * len(batch_frames)
                for future in futures:
                    idx = futures[future]
                    tensors[idx] = future.result()

                valid = [t for t in tensors if t is not None]
                if not valid:
                    for _ in batch_frames:
                        features.append(np.zeros(2048, dtype=np.float32))
                    continue

                batch_input = torch.stack(valid, dim=0)
                if self.gpu_sim.using_cuda:
                    batch_input = batch_input.pin_memory().to(self.device, non_blocking=True)
                else:
                    batch_input = batch_input.to(self.device)

                batch_feats = self.gpu_sim.model(batch_input).cpu().numpy()

                feat_idx = 0
                for t in tensors:
                    if t is not None:
                        features.append(batch_feats[feat_idx])
                        feat_idx += 1
                    else:
                        features.append(np.zeros(2048, dtype=np.float32))

        return np.stack(features, axis=0)

    def compute_video_similarity(
        self,
        features_a: np.ndarray,
        features_b: np.ndarray,
    ) -> float:
        """Compute similarity from frame-level cosine similarities."""
        if features_a.shape[0] == 0 or features_b.shape[0] == 0:
            return 0.0

        norms_a = np.linalg.norm(features_a, axis=1, keepdims=True)
        norms_a[norms_a == 0] = 1.0
        fa = features_a / norms_a

        norms_b = np.linalg.norm(features_b, axis=1, keepdims=True)
        norms_b[norms_b == 0] = 1.0
        fb = features_b / norms_b

        sim_matrix = np.dot(fa, fb.T)
        sim_matrix = np.clip(sim_matrix, -1.0, 1.0)
        sim_matrix = (sim_matrix + 1.0) / 2.0
        best_matches = np.max(sim_matrix, axis=1)
        return float(np.mean(best_matches))

    def _sample_video_dimensions(
        self,
        video_paths: list[str | Path],
        sample_count: int = 3,
    ) -> tuple[int, int]:
        """Sample a few videos to estimate average resolution.

        Uses at most *sample_count* videos to avoid opening every file.
        """
        if not video_paths:
            return 1920, 1080

        sample_count = min(sample_count, len(video_paths))
        widths: list[int] = []
        heights: list[int] = []
        for path in video_paths[:sample_count]:
            try:
                w, h, _, _ = get_video_info(path)
                if w > 0 and h > 0:
                    widths.append(w)
                    heights.append(h)
            except Exception:
                continue

        if widths:
            avg_width = int(sum(widths) / len(widths))
            avg_height = int(sum(heights) / len(heights))
            logger.info(
                "Sampled %d videos: average resolution %dx%d",
                len(widths), avg_width, avg_height,
            )
            return avg_width, avg_height

        return 1920, 1080

    def find_duplicates(
        self,
        video_paths: list[str | Path],
        threshold: float = 0.90,
        batch_size: int = 64,
        progress_callback: Callable[[int, int], bool] | None = None,
    ) -> list[tuple[Path, Path, float]]:
        """Find duplicate/similar video pairs with memory-aware batch processing.

        Optimizations:
        1. Parallel keyframe extraction inside each batch (multi-threaded).
        2. Memory monitoring every N batches instead of every batch.
        3. No forced page reclaim or GC per batch — only when under pressure.
        """
        n = len(video_paths)
        if n < 2:
            return []

        # ---- Phase 0: batch sizing ----
        memory_limit = get_video_processing_memory_limit(ratio=0.80)
        avg_width, avg_height = self._sample_video_dimensions(video_paths)
        video_batch_size = calculate_batch_size(
            video_count=n,
            memory_limit=memory_limit,
            avg_frame_count=self.max_frames_per_video,
            avg_width=avg_width,
            avg_height=avg_height,
        )
        inference_batch_size = batch_size

        logger.info(
            "Processing %d videos in batches of %d (memory limit: %s)",
            n, video_batch_size, f"{memory_limit / (1024**3):.1f} GB",
        )

        # ---- Phase 1: Extract features batch by batch ----
        video_features: dict[int, np.ndarray] = {}
        empty_videos: set[int] = set()

        gpu_limits = get_gpu_memory_limit(gpu_ratio=0.90) if self.gpu_sim.using_cuda else None
        sizer = AdaptiveBatchSizer(video_batch_size, memory_limit, gpu_memory_limit=gpu_limits)

        total_progress_units = n * 3
        batch_num = 0
        batch_start = 0

        # Only monitor memory every N batches to reduce syscall overhead
        MONITOR_EVERY = 3

        while batch_start < n:
            current_batch_size = sizer.batch_size
            batch_end = min(batch_start + current_batch_size, n)
            batch_indices = list(range(batch_start, batch_end))
            batch_num += 1

            should_monitor = (batch_num % MONITOR_EVERY == 1) or sizer._has_reduced
            if should_monitor:
                sizer.pre_batch()

            # ---- Parallel keyframe extraction ----
            batch_frames_list = self._extract_keyframes_parallel(video_paths, batch_indices)
            for pos, idx in enumerate(batch_indices):
                if not batch_frames_list[pos]:
                    empty_videos.add(idx)

            # Report Phase 1 progress (keyframe extraction: 0 ~ n)
            if progress_callback:
                progress_current = batch_end
                if progress_callback(progress_current, total_progress_units):
                    raise CancelledError()

            # ---- Feature extraction ----
            flat_frames, mapping = self._flatten_frames(batch_frames_list)
            if flat_frames:
                features = self._extract_frame_features(
                    flat_frames,
                    batch_size=inference_batch_size,
                    progress_callback=None,
                )
                for feat, (vi_in_batch, _) in zip(features, mapping):
                    actual_idx = batch_indices[vi_in_batch]
                    if actual_idx not in video_features:
                        video_features[actual_idx] = []
                    video_features[actual_idx].append(feat)

                # Report Phase 2 progress (feature extraction: n ~ 2n)
                if progress_callback:
                    progress_current = n + batch_end
                    if progress_callback(progress_current, total_progress_units):
                        raise CancelledError()

            # ---- Release keyframe memory immediately ----
            del batch_frames_list
            del flat_frames
            del mapping

            # ---- Memory monitoring (sparingly) ----
            if should_monitor:
                valid_count = sum(1 for i in batch_indices if i not in empty_videos)
                sizer.post_batch(videos_in_batch=valid_count)

            logger.debug(
                "Batch %d-%d done (size=%d), features: %d videos",
                batch_start, batch_end - 1, current_batch_size,
                len(video_features),
            )

            batch_start = batch_end

        # ---- Phase 2: Compare all video pairs ----
        valid_indices = sorted(video_features.keys())
        m = len(valid_indices)
        if m < 2:
            logger.info("Only %d valid videos, no pairs to compare", m)
            return []

        total_pairs = m * (m - 1) // 2
        pair_idx = 0
        duplicates: list[tuple[Path, Path, float]] = []

        stacked_features = {
            idx: np.stack(video_features[idx], axis=0)
            for idx in valid_indices
        }
        del video_features

        for i_idx in range(m):
            vi = valid_indices[i_idx]
            feats_i = stacked_features[vi]

            for j_idx in range(i_idx + 1, m):
                vj = valid_indices[j_idx]
                feats_j = stacked_features[vj]

                score = self.compute_video_similarity(feats_i, feats_j)
                if score >= threshold:
                    duplicates.append((Path(video_paths[vi]), Path(video_paths[vj]), score))

                pair_idx += 1
                if progress_callback and pair_idx % 10 == 0:
                    # Map pair progress to Phase 3 range (2n ~ 3n)
                    progress_current = int(2 * n + (pair_idx / total_pairs) * n)
                    if progress_callback(progress_current, total_progress_units):
                        raise CancelledError()

        # Ensure we end at exactly 3n for a clean progress bar
        if progress_callback:
            if progress_callback(total_progress_units, total_progress_units):
                raise CancelledError()

        del stacked_features
        if self.gpu_sim.using_cuda:
            torch.cuda.empty_cache()

        duplicates.sort(key=lambda x: x[2], reverse=True)
        logger.info("Found %d duplicate video pairs", len(duplicates))
        return duplicates

    def find_duplicates_large(
        self,
        video_paths: list[str | Path],
        threshold: float = 0.90,
        batch_size: int = 64,
        progress_callback: Callable[[int, int], bool] | None = None,
    ) -> list[tuple[Path, Path, float]]:
        return self.find_duplicates(
            video_paths,
            threshold=threshold,
            batch_size=batch_size,
            progress_callback=progress_callback,
        )


class CancelledError(Exception):
    """Raised when scan task is cancelled."""
    pass
