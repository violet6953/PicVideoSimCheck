#!/usr/bin/env python3
"""PicSimProcess - 图片/视频相似度检查命令行工具。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.processor import BatchProcessor
from src.similarity import ImageSimilarity
from src.utils import format_similarity, list_video_files
from src.video_similarity import VideoSimilarity


def cmd_compare(args: argparse.Namespace) -> int:
    """比较两张图片。"""
    sim = ImageSimilarity(method=args.method, threshold=args.threshold)
    score = sim.compare(args.image1, args.image2, method=args.method)
    similar = "是" if score >= args.threshold else "否"

    print(f"方法: {args.method}")
    print(f"相似度: {format_similarity(score)}")
    print(f"阈值: {format_similarity(args.threshold)}")
    print(f"是否相似: {similar}")
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    """在目录中查找重复图片和视频。"""
    processor = BatchProcessor(
        method=args.method,
        threshold=args.threshold,
        progress=not args.no_progress,
    )

    # Find image duplicates
    image_duplicates = processor.find_duplicates(
        args.directory,
        recursive=args.recursive,
    )

    # Find video duplicates if enabled
    video_duplicates: list[tuple[Path, Path, float]] = []
    if args.video_enabled:
        video_files = list_video_files(args.directory, recursive=args.recursive)
        if len(video_files) >= 2:
            from src.gpu_similarity import GPUSimilarity

            gpu_sim = GPUSimilarity() if args.video_method == "gpu" else None
            video_sim = VideoSimilarity(
                gpu_sim=gpu_sim,
                frames_per_second=args.video_fps,
                max_frames_per_video=args.video_max_frames,
            )
            video_duplicates = video_sim.find_duplicates(
                video_files,
                threshold=args.video_threshold,
            )

    all_duplicates = image_duplicates + video_duplicates

    if not all_duplicates:
        print("未发现相似文件。")
        return 0

    if image_duplicates:
        print(f"发现 {len(image_duplicates)} 对相似图片:")
        for p1, p2, score in image_duplicates:
            print(f"  [{format_similarity(score)}] {p1}")
            print(f"           -> {p2}")
        print()

    if video_duplicates:
        print(f"发现 {len(video_duplicates)} 对相似视频:")
        for p1, p2, score in video_duplicates:
            print(f"  [{format_similarity(score)}] {p1}")
            print(f"           -> {p2}")
        print()

    if args.report:
        processor.export_report(all_duplicates, args.report)
        print(f"报告已保存: {args.report}")

    return 0


def cmd_group(args: argparse.Namespace) -> int:
    """将相似文件分组。"""
    processor = BatchProcessor(
        method=args.method,
        threshold=args.threshold,
        progress=not args.no_progress,
    )
    image_groups = processor.group_similar(args.directory, recursive=args.recursive)

    video_groups: list[list[Path]] = []
    if args.video_enabled:
        video_files = list_video_files(args.directory, recursive=args.recursive)
        if len(video_files) >= 2:
            from src.gpu_similarity import GPUSimilarity

            gpu_sim = GPUSimilarity() if args.video_method == "gpu" else None
            video_sim = VideoSimilarity(
                gpu_sim=gpu_sim,
                frames_per_second=args.video_fps,
                max_frames_per_video=args.video_max_frames,
            )
            video_dups = video_sim.find_duplicates(
                video_files,
                threshold=args.video_threshold,
            )

            # Union-find for videos
            parent: dict[Path, Path] = {}

            def find(x: Path) -> Path:
                if parent.get(x, x) != x:
                    parent[x] = find(parent[x])
                return parent.get(x, x)

            def union(x: Path, y: Path) -> None:
                px, py = find(x), find(y)
                if px != py:
                    parent[px] = py

            for a, b, _ in video_dups:
                union(a, b)

            groups_dict: dict[Path, list[Path]] = {}
            for f in video_files:
                root = find(f)
                groups_dict.setdefault(root, []).append(f)

            video_groups = [g for g in groups_dict.values() if len(g) > 1]

    if not image_groups and not video_groups:
        print("未发现相似文件分组。")
        return 0

    if image_groups:
        print(f"发现 {len(image_groups)} 个相似图片分组:\n")
        for i, group in enumerate(image_groups, 1):
            print(f"  图片分组 {i} ({len(group)} 张):")
            for p in group:
                print(f"    - {p}")
            print()

    if video_groups:
        print(f"发现 {len(video_groups)} 个相似视频分组:\n")
        for i, group in enumerate(video_groups, 1):
            print(f"  视频分组 {i} ({len(group)} 个):")
            for p in group:
                print(f"    - {p}")
            print()

    return 0


def cmd_dedup(args: argparse.Namespace) -> int:
    """删除重复文件。"""
    processor = BatchProcessor(
        method=args.method,
        threshold=args.threshold,
        progress=not args.no_progress,
    )
    image_removed = processor.remove_duplicates(
        args.directory,
        output_dir=args.output,
        strategy=args.strategy,
        recursive=args.recursive,
    )

    video_removed: list[Path] = []
    if args.video_enabled:
        video_files = list_video_files(args.directory, recursive=args.recursive)
        if len(video_files) >= 2:
            from src.gpu_similarity import GPUSimilarity

            gpu_sim = GPUSimilarity() if args.video_method == "gpu" else None
            video_sim = VideoSimilarity(
                gpu_sim=gpu_sim,
                frames_per_second=args.video_fps,
                max_frames_per_video=args.video_max_frames,
            )
            video_dups = video_sim.find_duplicates(
                video_files,
                threshold=args.video_threshold,
            )

            parent: dict[Path, Path] = {}

            def find(x: Path) -> Path:
                if parent.get(x, x) != x:
                    parent[x] = find(parent[x])
                return parent.get(x, x)

            def union(x: Path, y: Path) -> None:
                px, py = find(x), find(y)
                if px != py:
                    parent[px] = py

            for a, b, _ in video_dups:
                union(a, b)

            groups_dict: dict[Path, list[Path]] = {}
            for f in video_files:
                root = find(f)
                groups_dict.setdefault(root, []).append(f)

            video_groups = [g for g in groups_dict.values() if len(g) > 1]

            import shutil

            for group in video_groups:
                if args.strategy == "keep_best":
                    keeper = max(group, key=lambda p: p.stat().st_size)
                else:
                    keeper = group[0]

                for f in group:
                    if f == keeper:
                        continue
                    if args.output:
                        output_dir = Path(args.output)
                        output_dir.mkdir(parents=True, exist_ok=True)
                        dest = output_dir / f.name
                        shutil.move(str(f), str(dest))
                        video_removed.append(dest)
                    else:
                        f.unlink()
                        video_removed.append(f)

    removed = image_removed + video_removed

    if not removed:
        print("未发现重复文件。")
        return 0

    action = "移动到" if args.output else "删除"
    print(f"已{action} {len(removed)} 个重复文件:")
    for p in removed:
        print(f"  - {p}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="PicSimProcess",
        description="图片/视频相似度检查与去重工具",
    )
    parser.add_argument(
        "--method",
        default="phash",
        choices=["phash", "dhash", "ahash", "whash", "histogram", "ssim", "orb", "gpu"],
        help="图片相似度算法 (默认: phash)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="图片相似度阈值 0~1 (默认: 0.85)",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="不显示进度条",
    )

    # Video options
    parser.add_argument(
        "--video-enabled",
        action="store_true",
        help="同时检测视频相似度",
    )
    parser.add_argument(
        "--video-method",
        default="gpu",
        choices=["gpu"],
        help="视频检测算法 (默认: gpu)",
    )
    parser.add_argument(
        "--video-threshold",
        type=float,
        default=0.90,
        help="视频相似度阈值 0~1 (默认: 0.90)",
    )
    parser.add_argument(
        "--video-fps",
        type=float,
        default=1.0,
        help="视频采样帧率 帧/秒 (默认: 1.0)",
    )
    parser.add_argument(
        "--video-max-frames",
        type=int,
        default=32,
        help="每视频最大采样帧数 (默认: 32)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # compare
    p_compare = subparsers.add_parser("compare", help="比较两张图片")
    p_compare.add_argument("image1", help="第一张图片路径")
    p_compare.add_argument("image2", help="第二张图片路径")
    p_compare.set_defaults(func=cmd_compare)

    # find
    p_find = subparsers.add_parser("find", help="查找目录中的相似文件")
    p_find.add_argument("directory", help="目标目录")
    p_find.add_argument("-r", "--recursive", action="store_true", help="递归子目录")
    p_find.add_argument("--report", help="导出 JSON 报告路径")
    p_find.set_defaults(func=cmd_find)

    # group
    p_group = subparsers.add_parser("group", help="将相似文件分组")
    p_group.add_argument("directory", help="目标目录")
    p_group.add_argument("-r", "--recursive", action="store_true", help="递归子目录")
    p_group.set_defaults(func=cmd_group)

    # dedup
    p_dedup = subparsers.add_parser("dedup", help="删除/移动重复文件")
    p_dedup.add_argument("directory", help="目标目录")
    p_dedup.add_argument("-r", "--recursive", action="store_true", help="递归子目录")
    p_dedup.add_argument("--output", help="移动到的目录（不指定则直接删除）")
    p_dedup.add_argument(
        "--strategy",
        choices=["keep_first", "keep_best"],
        default="keep_first",
        help="保留策略 (默认: keep_first)",
    )
    p_dedup.set_defaults(func=cmd_dedup)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
