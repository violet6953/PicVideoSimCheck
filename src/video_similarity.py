"""GPU accelerated video similarity detection using keyframe + ResNet50 feature extraction."""

from __future__ import annotations

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

_CPU_COUNT = os.cpu_count() or 20


class VideoSimilarity:
    """Video similarity using keyframe sampling + deep learning feature extraction.

    Extracts evenly distributed keyframes from each video, uses a shared
    GPUSimilarity instance to extract frame features on GPU, then computes
    inter-video similarity from frame-level cosine similarities.
    """

    def __init__(
        self,
        gpu_sim: GPUSimilarity | None = None,
        device: str | None = None,
        frames_per_second: float = 1.0,
        max_frames_per_video: int = 32,
        min_frames_per_video: int = 4,
    ):
        """
        Args:
            gpu_sim: Shared GPUSimilarity instance (creates one if None).
            device: Override torch device.
            frames_per_second: Target sampling rate (frames/sec).
            max_frames_per_video: Upper bound on sampled frames per video.
            min_frames_per_video: Lower bound on sampled frames per video.
        """
        if gpu_sim is not None:
            self.gpu_sim = gpu_sim
        else:
            self.gpu_sim = GPUSimilarity(device=device)

        self.frames_per_second = frames_per_second
        self.max_frames_per_video = max(max_frames_per_video, min_frames_per_video)
        self.min_frames_per_video = max(min_frames_per_video, 1)
        self.device = self.gpu_sim.device

        # Reuse the same image preprocessing transform from GPUSimilarity
        self.transform = self.gpu_sim.transform

        self._load_pool = ThreadPoolExecutor(max_workers=_CPU_COUNT)

    def extract_keyframes(self, video_path: str | Path) -> list[np.ndarray]:
        """Extract evenly distributed keyframes from a video file.

        Returns a list of RGB numpy arrays (H, W, 3) in uint8.
        Returns an empty list if the video cannot be opened.
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
            # Evenly distributed indices
            step = total_frames / target_count
            frame_indices = [min(int(i * step), total_frames - 1) for i in range(target_count)]

        frames: list[np.ndarray] = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret and frame is not None:
                # BGR -> RGB
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(rgb)

        cap.release()
        return frames

    def _extract_all_keyframes(
        self,
        video_paths: list[str | Path],
        progress_callback: Callable[[int, int], bool] | None = None,
    ) -> tuple[list[list[np.ndarray]], list[int]]:
        """Extract keyframes from all videos in parallel, return (frames_per_video, video_frame_counts).

        Uses ThreadPoolExecutor to extract keyframes from multiple videos
        concurrently to fully utilize CPU (e.g. 10C/20T).
        """
        total = len(video_paths)
        if total == 0:
            return [], []

        all_frames: list[list[np.ndarray] | None] = [None] * total
        counts: list[int] = [0] * total
        completed = 0

        def _worker(idx: int) -> None:
            nonlocal completed
            frames = self.extract_keyframes(video_paths[idx])
            all_frames[idx] = frames
            counts[idx] = len(frames)
            completed += 1

        with ThreadPoolExecutor(max_workers=_CPU_COUNT) as executor:
            futures = {executor.submit(_worker, i): i for i in range(total)}
            for future in futures:
                i = futures[future]
                try:
                    future.result()
                except Exception:
                    all_frames[i] = []
                    counts[i] = 0

                if progress_callback and completed % 5 == 0:
                    if progress_callback(completed, total):
                        # Cancel remaining futures
                        for f in futures:
                            f.cancel()
                        raise CancelledError()

        # Filter out None (shouldn't happen but safety check)
        all_frames = [f if f is not None else [] for f in all_frames]
        return all_frames, counts

    def _flatten_frames(
        self,
        all_frames: list[list[np.ndarray]],
    ) -> tuple[list[np.ndarray], list[tuple[int, int]]]:
        """Flatten nested frame lists into a single list + index mapping.

        Returns (flat_frames, mapping) where mapping[i] = (video_idx, frame_idx_in_video).
        """
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
        """Extract ResNet50 features for a list of RGB numpy arrays using GPU.

        Uses the shared GPUSimilarity model. Falls back to CPU preprocessing
        if GPU is not available.
        """
        if not frames:
            return np.zeros((0, 2048), dtype=np.float32)

        total = len(frames)
        features: list[np.ndarray] = []

        # Preprocess frames to tensors on CPU using thread pool
        def _preprocess(frame: np.ndarray) -> torch.Tensor | None:
            try:
                pil_img = Image.fromarray(frame)
                return self.transform(pil_img)
            except Exception:
                return None

        with torch.no_grad():
            for batch_start in range(0, total, batch_size):
                if progress_callback and progress_callback(batch_start, total):
                    raise CancelledError()

                batch_frames = frames[batch_start : batch_start + batch_size]

                # Multi-threaded preprocessing
                futures = {
                    self._load_pool.submit(_preprocess, f): idx
                    for idx, f in enumerate(batch_frames)
                }
                tensors: list[torch.Tensor | None] = [None] * len(batch_frames)
                for future in futures:
                    idx = futures[future]
                    result = future.result()
                    tensors[idx] = result

                valid_tensors = [t for t in tensors if t is not None]
                if not valid_tensors:
                    for _ in batch_frames:
                        features.append(np.zeros(2048, dtype=np.float32))
                    continue

                batch_input = torch.stack(valid_tensors, dim=0)
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

                if self.gpu_sim.using_cuda:
                    torch.cuda.empty_cache()

        return np.stack(features, axis=0)

    def compute_video_similarity(
        self,
        features_a: np.ndarray,
        features_b: np.ndarray,
    ) -> float:
        """Compute similarity between two videos from their frame features.

        For each frame in A, find the best matching frame in B (max cosine sim),
        then average. This is robust to small temporal shifts.
        """
        if features_a.shape[0] == 0 or features_b.shape[0] == 0:
            return 0.0

        # L2 normalize
        norms_a = np.linalg.norm(features_a, axis=1, keepdims=True)
        norms_a[norms_a == 0] = 1.0
        fa = features_a / norms_a

        norms_b = np.linalg.norm(features_b, axis=1, keepdims=True)
        norms_b[norms_b == 0] = 1.0
        fb = features_b / norms_b

        # Cosine similarity matrix: (n_frames_a, n_frames_b)
        sim_matrix = np.dot(fa, fb.T)
        sim_matrix = np.clip(sim_matrix, -1.0, 1.0)
        # Map [-1, 1] -> [0, 1]
        sim_matrix = (sim_matrix + 1.0) / 2.0

        # For each frame in A, best match in B
        best_matches = np.max(sim_matrix, axis=1)
        return float(np.mean(best_matches))

    def find_duplicates(
        self,
        video_paths: list[str | Path],
        threshold: float = 0.90,
        batch_size: int = 64,
        progress_callback: Callable[[int, int], bool] | None = None,
    ) -> list[tuple[Path, Path, float]]:
        """Find duplicate/similar video pairs.

        Returns list of (path1, path2, similarity_score) tuples.
        """
        n = len(video_paths)
        if n < 2:
            return []

        # Phase 1: Extract keyframes from all videos
        if progress_callback and progress_callback(0, n * 3):
            raise CancelledError()

        all_frames, frame_counts = self._extract_all_keyframes(
            video_paths,
            progress_callback=lambda c, t: progress_callback(c, t * 3) if progress_callback else False,
        )

        # Skip videos with no extractable frames
        valid_indices = [i for i, c in enumerate(frame_counts) if c > 0]
        if len(valid_indices) < 2:
            return []

        # Phase 2: Flatten all frames and extract features
        flat_frames, mapping = self._flatten_frames(
            [all_frames[i] for i in valid_indices]
        )

        def _feat_progress(c: int, t: int) -> bool:
            if progress_callback:
                return progress_callback(n + c, n * 3)
            return False

        all_features = self._extract_frame_features(
            flat_frames,
            batch_size=batch_size,
            progress_callback=_feat_progress,
        )

        # Map features back to videos
        video_features: dict[int, list[np.ndarray]] = {i: [] for i in valid_indices}
        for feat, (vi_in_valid, _) in zip(all_features, mapping):
            actual_idx = valid_indices[vi_in_valid]
            video_features[actual_idx].append(feat)

        # Phase 3: Compare all video pairs
        duplicates: list[tuple[Path, Path, float]] = []
        m = len(valid_indices)
        total_pairs = m * (m - 1) // 2
        pair_idx = 0

        for i_idx in range(m):
            vi = valid_indices[i_idx]
            feats_i = np.stack(video_features[vi], axis=0)

            for j_idx in range(i_idx + 1, m):
                vj = valid_indices[j_idx]
                feats_j = np.stack(video_features[vj], axis=0)

                score = self.compute_video_similarity(feats_i, feats_j)
                if score >= threshold:
                    duplicates.append((Path(video_paths[vi]), Path(video_paths[vj]), score))

                pair_idx += 1
                if progress_callback and pair_idx % 10 == 0:
                    if progress_callback(n * 2 + pair_idx, n * 3):
                        raise CancelledError()

        duplicates.sort(key=lambda x: x[2], reverse=True)
        return duplicates

    def find_duplicates_large(
        self,
        video_paths: list[str | Path],
        threshold: float = 0.90,
        batch_size: int = 64,
        progress_callback: Callable[[int, int], bool] | None = None,
    ) -> list[tuple[Path, Path, float]]:
        """Optimized version for large video sets — same algorithm but with GPU batched pair comparison.

        Currently delegates to find_duplicates since video count is typically small.
        Can be enhanced with GPU matrix operations if needed.
        """
        return self.find_duplicates(
            video_paths,
            threshold=threshold,
            batch_size=batch_size,
            progress_callback=progress_callback,
        )


class CancelledError(Exception):
    """Raised when scan task is cancelled."""
    pass
