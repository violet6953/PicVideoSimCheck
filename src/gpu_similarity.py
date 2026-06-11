"""GPU accelerated image similarity using PyTorch ResNet50 feature extraction."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image
from torchvision import models

# Dynamically detect CPU thread count (e.g. 10-core 20-thread -> 20)
_CPU_COUNT = os.cpu_count() or 20


class GPUSimilarity:
    """Extract image features with ResNet50 pre-trained model, compute cosine similarity."""

    def __init__(self, device: str | None = None):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        weights = models.ResNet50_Weights.IMAGENET1K_V2
        self.model = models.resnet50(weights=weights)
        self.model.fc = torch.nn.Identity()
        self.model = self.model.to(self.device)
        self.model.eval()

        # Use torch.compile for speedup (PyTorch 2.0+)
        # Note: Triton is not available on Windows, so only compile on Linux
        import platform

        if hasattr(torch, "compile") and self.using_cuda and platform.system() == "Linux":
            try:
                self.model = torch.compile(self.model, mode="max-autotune")
            except Exception:
                pass

        # Set PyTorch CPU intra-op parallelism to match physical threads
        torch.set_num_threads(_CPU_COUNT)

        self.transform = T.Compose([
            T.Resize(256),
            T.CenterCrop(224),
            T.ToTensor(),
            T.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

        self._feature_cache: dict[Path, np.ndarray] = {}
        # Reuse thread pool across batches to avoid repeated creation overhead
        self._load_pool = ThreadPoolExecutor(max_workers=_CPU_COUNT)

    @property
    def using_cuda(self) -> bool:
        return self.device.type == "cuda"

    def _load_image_cpu(self, path: str | Path) -> torch.Tensor | None:
        """Load and preprocess single image on CPU (called by thread pool)."""
        try:
            img = Image.open(path).convert("RGB")
            return self.transform(img)
        except Exception:
            return None

    def extract_features(
        self,
        image_paths: list[str | Path],
        batch_size: int = 128,
        progress_callback: Callable[[int, int], bool] | None = None,
    ) -> np.ndarray:
        features: list[np.ndarray] = []
        total = len(image_paths)

        # Pre-allocate pinned memory buffer for faster CPU->GPU transfer
        pin_memory = self.using_cuda

        with torch.no_grad():
            for batch_start in range(0, total, batch_size):
                if progress_callback and progress_callback(batch_start, total):
                    raise CancelledError()

                batch_paths = image_paths[batch_start : batch_start + batch_size]
                batch_size_actual = len(batch_paths)

                # Phase 1: Multi-threaded CPU image loading (reuse pool)
                tensors = [None] * batch_size_actual
                future_to_idx: dict = {}
                for idx, p in enumerate(batch_paths):
                    p = Path(p)
                    if p in self._feature_cache:
                        tensors[idx] = self._feature_cache[p]
                    else:
                        future = self._load_pool.submit(self._load_image_cpu, p)
                        future_to_idx[future] = idx

                for future in future_to_idx:
                    idx = future_to_idx[future]
                    result = future.result()
                    tensors[idx] = result

                # Phase 2: Stack valid tensors and move to GPU
                valid_tensors = [t for t in tensors if t is not None]
                if not valid_tensors:
                    # All failed in this batch
                    for _ in batch_paths:
                        features.append(np.zeros(2048, dtype=np.float32))
                    continue

                batch_input = torch.stack(valid_tensors, dim=0)
                if pin_memory:
                    batch_input = batch_input.pin_memory()
                batch_input = batch_input.to(self.device, non_blocking=True)

                # Phase 3: GPU inference
                batch_feats = self.model(batch_input).cpu().numpy()

                # Map results back (handle failures)
                feat_idx = 0
                for idx, p in enumerate(batch_paths):
                    p = Path(p)
                    if p in self._feature_cache:
                        features.append(self._feature_cache[p])
                    elif tensors[idx] is not None:
                        self._feature_cache[p] = batch_feats[feat_idx]
                        features.append(batch_feats[feat_idx])
                        feat_idx += 1
                    else:
                        zero_feat = np.zeros(2048, dtype=np.float32)
                        self._feature_cache[p] = zero_feat
                        features.append(zero_feat)

        # Free cached GPU memory once after all batches (PyTorch allocator
        # reuses cached allocations; per-batch empty_cache stalls the pipeline)
        if self.using_cuda:
            torch.cuda.empty_cache()

        return np.stack(features, axis=0)

    def find_duplicates(
        self,
        image_paths: list[str | Path],
        threshold: float = 0.85,
        batch_size: int = 128,
        progress_callback: Callable[[int, int], bool] | None = None,
    ) -> list[tuple[Path, Path, float]]:
        if len(image_paths) < 2:
            return []

        features = self.extract_features(
            image_paths,
            batch_size=batch_size,
            progress_callback=progress_callback,
        )
        sim_matrix = self.compute_similarity_matrix(features)

        duplicates: list[tuple[Path, Path, float]] = []
        n = len(image_paths)
        for i in range(n):
            for j in range(i + 1, n):
                score = float(sim_matrix[i, j])
                if score >= threshold:
                    duplicates.append((Path(image_paths[i]), Path(image_paths[j]), score))

        duplicates.sort(key=lambda x: x[2], reverse=True)
        return duplicates

    def find_duplicates_large(
        self,
        image_paths: list[str | Path],
        threshold: float = 0.85,
        sim_batch_size: int = 2000,
        progress_callback: Callable[[int, int], bool] | None = None,
    ) -> list[tuple[Path, Path, float]]:
        """
        Optimized for large-scale comparison (100k+ images).
        Uses GPU batched matrix multiplication to avoid O(n^2) memory.
        """
        if len(image_paths) < 2:
            return []

        n = len(image_paths)
        features = self.extract_features(
            image_paths,
            batch_size=128,
            progress_callback=progress_callback,
        )

        if progress_callback and progress_callback(0, 100):
            raise CancelledError()

        # Normalize features
        norms = np.linalg.norm(features, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized = features / norms

        # Move to GPU tensor (pinned memory transfer)
        feats_np = normalized.astype(np.float32)
        feats_t = torch.from_numpy(feats_np).pin_memory().to(self.device, non_blocking=True)

        duplicates: list[tuple[Path, Path, float]] = []
        total_batches = (n + sim_batch_size - 1) // sim_batch_size

        # Batched similarity computation
        for batch_start in range(0, n, sim_batch_size):
            if progress_callback and progress_callback(batch_start, n):
                raise CancelledError()

            batch_end = min(batch_start + sim_batch_size, n)
            batch_feats = feats_t[batch_start:batch_end]

            # sim = batch_feats @ all_feats.T => (B, N)
            sim = torch.matmul(batch_feats, feats_t.T)
            sim = (sim + 1.0) / 2.0

            # Vectorized extraction: find all (i,j) where sim >= threshold and j > i
            B = batch_end - batch_start
            row_idx = torch.arange(B, device=sim.device).unsqueeze(1)     # (B, 1)
            col_idx = torch.arange(n, device=sim.device).unsqueeze(0)     # (1, N)
            global_row = batch_start + row_idx                             # (B, 1)

            triu_mask = col_idx > global_row                               # j > i
            thr_mask = sim >= threshold
            valid_mask = triu_mask & thr_mask

            if valid_mask.any():
                rows, cols = torch.where(valid_mask)
                global_rows = rows + batch_start
                scores = sim[rows, cols].cpu().numpy()
                batch_dups = [
                    (Path(image_paths[global_rows[k].item()]), Path(image_paths[cols[k].item()]), float(scores[k]))
                    for k in range(len(scores))
                ]
                duplicates.extend(batch_dups)

            del sim

        del feats_t
        # Single cleanup after all similarity computation is done
        if self.using_cuda:
            torch.cuda.empty_cache()

        duplicates.sort(key=lambda x: x[2], reverse=True)
        return duplicates

    def compute_similarity_matrix(self, features: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(features, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized = features / norms
        sim = np.dot(normalized, normalized.T)
        sim = np.clip(sim, -1.0, 1.0)
        sim = (sim + 1.0) / 2.0
        return sim


class CancelledError(Exception):
    """Raised when scan task is cancelled."""
    pass
