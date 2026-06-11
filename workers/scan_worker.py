"""Scan worker thread for PicSimProcess desktop application."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from services.blocklist_service import is_group_blocked, load_blocklist, save_blocklist
from src.processor import BatchProcessor, CancelledError
from src.utils import (
    format_duration,
    format_file_size,
    get_image_info,
    get_video_info,
    list_image_files,
    list_video_files,
)


class ScanWorker(QThread):
    """Background thread that performs image/video similarity scanning."""

    progress = Signal(dict)
    finished_with_results = Signal(list)
    error_occurred = Signal(str)
    stopped = Signal()

    def __init__(
        self,
        folders: list[str],
        method: str,
        threshold: float,
        video_enabled: bool,
        video_method: str,
        video_threshold: float,
        video_fps: float,
        video_max_frames: int,
        cancel_event: threading.Event,
        parent=None,
    ):
        super().__init__(parent)
        self.folders = folders
        self.method = method
        self.threshold = threshold
        self.video_enabled = video_enabled
        self.video_method = video_method
        self.video_threshold = video_threshold
        self.video_fps = video_fps
        self.video_max_frames = video_max_frames
        self.cancel_event = cancel_event

    def run(self) -> None:
        try:
            self._emit_progress(stage="扫描文件", current=0, total=100, message="正在扫描文件夹...")

            all_image_files: list[Path] = []
            all_video_files: list[Path] = []
            for folder in self.folders:
                images = list_image_files(folder, recursive=True)
                all_image_files.extend([f for f in images if f.is_file()])
                if self.video_enabled:
                    videos = list_video_files(folder, recursive=True)
                    all_video_files.extend([f for f in videos if f.is_file()])

            # Use normcase+abspath instead of resolve() to avoid expensive symlink resolution
            seen_images: set[str] = set()
            unique_images: list[Path] = []
            for f in all_image_files:
                resolved = os.path.normcase(os.path.abspath(str(f)))
                if resolved not in seen_images:
                    seen_images.add(resolved)
                    unique_images.append(f)

            seen_videos: set[str] = set()
            unique_videos: list[Path] = []
            for f in all_video_files:
                resolved = os.path.normcase(os.path.abspath(str(f)))
                if resolved not in seen_videos:
                    seen_videos.add(resolved)
                    unique_videos.append(f)

            image_files = unique_images
            video_files = unique_videos
            total_images = len(image_files)
            total_videos = len(video_files)

            if total_images < 2 and total_videos < 2:
                self._emit_progress(
                    stage="完成",
                    current=100,
                    total=100,
                    message="文件夹中图片和视频均不足 2 个，无需比较",
                )
                self.finished_with_results.emit([])
                return

            # ===== 阶段2-3: 图片处理 =====
            image_duplicates: list[tuple[Path, Path, float]] = []
            if total_images >= 2:
                self._emit_progress(
                    stage="图片特征提取",
                    current=0,
                    total=total_images,
                    message=f"正在提取图片特征... 0/{total_images}",
                )

                if self.method == "gpu":
                    import numpy as np
                    import torch
                    from src.gpu_similarity import GPUSimilarity

                    gpu_sim = GPUSimilarity()

                    def img_extract_progress(current: int, total: int) -> bool:
                        self._emit_progress(
                            stage="图片特征提取",
                            current=current,
                            total=total,
                            message=f"正在提取图片特征... {current}/{total}",
                        )
                        return self.cancel_event.is_set()

                    features = gpu_sim.extract_features(
                        image_files,
                        batch_size=128,
                        progress_callback=img_extract_progress,
                    )

                    batch_size = 2000 if total_images > 5000 else 500
                    total_batches = (total_images + batch_size - 1) // batch_size

                    self._emit_progress(
                        stage="图片相似度计算",
                        current=0,
                        total=total_batches,
                        message=f"正在计算图片相似度... 批次 0/{total_batches}",
                    )

                    norms = np.linalg.norm(features, axis=1, keepdims=True)
                    norms[norms == 0] = 1.0
                    normalized = features / norms
                    feats_t = torch.from_numpy(normalized).to(gpu_sim.device, dtype=torch.float32)

                    batch_idx = 0
                    for batch_start in range(0, total_images, batch_size):
                        if self.cancel_event.is_set():
                            raise CancelledError()

                        batch_idx += 1
                        self._emit_progress(
                            stage="图片相似度计算",
                            current=batch_idx,
                            total=total_batches,
                            message=f"正在计算图片相似度... 批次 {batch_idx}/{total_batches} ({batch_start}/{total_images} 张)",
                        )

                        batch_end = min(batch_start + batch_size, total_images)
                        batch_feats = feats_t[batch_start:batch_end]

                        sim = torch.matmul(batch_feats, feats_t.T)
                        sim = (sim + 1.0) / 2.0

                        for bi in range(batch_end - batch_start):
                            i = batch_start + bi
                            row = sim[bi, i + 1:]
                            mask = row >= self.threshold
                            if mask.any():
                                js = (torch.where(mask)[0] + i + 1).cpu().numpy()
                                scores = sim[bi, js].cpu().numpy()
                                for j, score in zip(js, scores):
                                    image_duplicates.append((image_files[i], image_files[j], float(score)))

                        del sim

                    del feats_t
                    # Single cleanup after all similarity computation
                    if gpu_sim.using_cuda:
                        torch.cuda.empty_cache()

                else:
                    processor = BatchProcessor(
                        method=self.method,
                        threshold=self.threshold,
                        progress=False,
                        cancelled=self.cancel_event.is_set,
                    )

                    checked_pairs = 0
                    total_pairs = total_images * (total_images - 1) // 2

                    self._emit_progress(
                        stage="图片相似度计算",
                        current=0,
                        total=total_images,
                        message=f"正在比较图片... 0/{total_images}",
                    )

                    # 哈希方法：预计算所有特征，避免每张图片被反复加载 O(n) 次
                    use_precomputed = self.method in ("phash", "dhash", "ahash", "whash")
                    precomputed_hashes = None
                    if use_precomputed:
                        self._emit_progress(
                            stage="图片特征提取",
                            current=0,
                            total=total_images,
                            message=f"正在预计算 {self.method} 特征... 0/{total_images}",
                        )
                        precomputed_hashes = processor.similarity.precompute_hashes(image_files)
                        self._emit_progress(
                            stage="图片相似度计算",
                            current=0,
                            total=total_images,
                            message=f"正在比较图片... 0/{total_images} 张（预计算完成，共 {total_pairs} 对）",
                        )

                    for i in range(total_images):
                        if self.cancel_event.is_set():
                            raise CancelledError()

                        if i % 100 == 0 or i == total_images - 1:
                            self._emit_progress(
                                stage="图片相似度计算",
                                current=i,
                                total=total_images,
                                message=f"正在比较图片... {i}/{total_images} 张（已检查 {checked_pairs} 对）",
                            )

                        for j in range(i + 1, total_images):
                            checked_pairs += 1
                            try:
                                if use_precomputed and precomputed_hashes is not None:
                                    score = processor.similarity.compare_hashes(
                                        precomputed_hashes.get(str(image_files[i])),
                                        precomputed_hashes.get(str(image_files[j])),
                                    )
                                else:
                                    score = processor.similarity.compare(image_files[i], image_files[j])
                            except Exception:
                                continue
                            if score >= self.threshold:
                                image_duplicates.append((image_files[i], image_files[j], score))

            # ===== 阶段4-5: 视频处理 =====
            video_duplicates: list[tuple[Path, Path, float]] = []
            if self.video_enabled and total_videos >= 2:
                from src.video_similarity import VideoSimilarity

                gpu_sim_for_video = None
                if self.video_method == "gpu":
                    from src.gpu_similarity import GPUSimilarity
                    gpu_sim_for_video = GPUSimilarity()

                video_sim = VideoSimilarity(
                    gpu_sim=gpu_sim_for_video,
                    frames_per_second=self.video_fps,
                    max_frames_per_video=self.video_max_frames,
                )

                def video_progress(current: int, total: int) -> bool:
                    self._emit_progress(
                        stage="视频相似度检测",
                        current=current,
                        total=total,
                        message=f"正在处理视频... {current}/{total}",
                    )
                    return self.cancel_event.is_set()

                self._emit_progress(
                    stage="视频相似度检测",
                    current=0,
                    total=total_videos * 3,
                    message=f"正在检测视频相似度... 0/{total_videos * 3}",
                )

                video_duplicates = video_sim.find_duplicates(
                    video_files,
                    threshold=self.video_threshold,
                    batch_size=64,
                    progress_callback=video_progress,
                )

                if gpu_sim_for_video and gpu_sim_for_video.using_cuda:
                    import torch
                    torch.cuda.empty_cache()

            # ===== 阶段6: 结果分组 =====
            self._emit_progress(
                stage="结果分组",
                current=0,
                total=100,
                message="正在整理结果...",
            )

            parent_map: dict[str, str] = {}

            def find(x: str) -> str:
                if parent_map.get(x, x) != x:
                    parent_map[x] = find(parent_map[x])
                return parent_map.get(x, x)

            def union(x: str, y: str) -> None:
                px, py = find(x), find(y)
                if px != py:
                    parent_map[px] = py

            for a, b, _ in image_duplicates:
                union(str(a), str(b))
            for a, b, _ in video_duplicates:
                union(str(a), str(b))

            image_groups_dict: dict[str, list[str]] = {}
            for f in image_files:
                root = find(str(f))
                image_groups_dict.setdefault(root, []).append(str(f))
            image_groups = [g for g in image_groups_dict.values() if len(g) > 1]

            video_groups_dict: dict[str, list[str]] = {}
            for f in video_files:
                root = find(str(f))
                video_groups_dict.setdefault(root, []).append(str(f))
            video_groups = [g for g in video_groups_dict.values() if len(g) > 1]

            # ===== 过滤排除的组 =====
            blocklist = load_blocklist()

            def filter_groups(groups: list[list[str]]) -> list[list[str]]:
                filtered = []
                for g in groups:
                    group_set = frozenset(Path(p).resolve() for p in g)
                    blocked = False
                    for entry in blocklist:
                        entry_set = frozenset(Path(p).resolve() for p in entry.get("paths", []) if p)
                        if not entry_set:
                            continue
                        if entry_set == group_set or entry_set.issubset(group_set) or group_set.issubset(entry_set):
                            blocked = True
                            break
                    if not blocked:
                        filtered.append(g)
                return filtered

            image_groups = filter_groups(image_groups)
            video_groups = filter_groups(video_groups)

            blocked_count = (len(image_groups_dict) - len(image_groups)) + (len(video_groups_dict) - len(video_groups))

            # ===== 收集结果 =====
            result_groups = []
            cpu_count = os.cpu_count() or 20

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

            def _sort_key(x: dict):
                name = x["name"]
                has_copy_number = bool(re.search(r"\(\d+\)", name))
                has_duplicate_suffix = "副本" in name
                return (
                    -x["size"],
                    -(x["width"] * x["height"]),
                    (has_copy_number, has_duplicate_suffix),
                    x["ctime"],
                )

            for gi, group in enumerate(image_groups):
                with ThreadPoolExecutor(max_workers=cpu_count) as executor:
                    group_items = list(executor.map(_collect_image_info, group))

                group_items.sort(key=_sort_key)
                for item in group_items:
                    item.pop("ctime", None)

                result_groups.append({"type": "image", "items": group_items})

                if gi % 50 == 0:
                    self._emit_progress(
                        stage="结果分组",
                        current=gi,
                        total=len(image_groups) + len(video_groups),
                        message=f"正在整理结果... {gi}/{len(image_groups) + len(video_groups)} 组",
                    )

            for gi, group in enumerate(video_groups):
                with ThreadPoolExecutor(max_workers=cpu_count) as executor:
                    group_items = list(executor.map(_collect_video_info, group))

                group_items.sort(key=_sort_key)
                for item in group_items:
                    item.pop("ctime", None)

                result_groups.append({"type": "video", "items": group_items})

            total_groups = len(image_groups) + len(video_groups)
            msg_parts = []
            if image_groups:
                msg_parts.append(f"{len(image_groups)} 组相似图片")
            if video_groups:
                msg_parts.append(f"{len(video_groups)} 组相似视频")

            msg = "扫描完成"
            if msg_parts:
                msg += "，发现 " + "、".join(msg_parts)
            else:
                msg += "，未发现相似文件"

            if blocked_count > 0:
                msg += f"（已排除 {blocked_count} 组误报）"

            self._emit_progress(
                stage="完成",
                current=100,
                total=100,
                message=msg,
            )
            self.finished_with_results.emit(result_groups)

        except CancelledError:
            self.stopped.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _emit_progress(self, stage: str, current: int, total: int, message: str) -> None:
        self.progress.emit({
            "stage": stage,
            "stage_current": current,
            "stage_total": total,
            "message": message,
        })
