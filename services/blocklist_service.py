"""Blocklist (false-positive exclusion) persistence service."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


def _get_blocklist_path() -> Path:
    """Return the path to blocklist.json.

    In a PyInstaller-frozen app, user-writable data lives next to the
    executable so upgrades do not overwrite it. During development it
    lives in the project root.
    """
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).parent
        user_data_dir = app_dir / "data"
        user_data_dir.mkdir(parents=True, exist_ok=True)
        return user_data_dir / "blocklist.json"
    return Path(__file__).parent.parent / "data" / "blocklist.json"


BLOCKLIST_PATH = _get_blocklist_path()


def load_blocklist() -> list[dict]:
    """加载排除列表（误报记录）。"""
    if BLOCKLIST_PATH.exists():
        try:
            data = json.loads(BLOCKLIST_PATH.read_text(encoding="utf-8"))
            return data.get("blocklist", [])
        except Exception:
            return []
    return []


def save_blocklist(blocklist: list[dict]) -> None:
    """保存排除列表到本地 JSON。"""
    BLOCKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": 1, "blocklist": blocklist}
    BLOCKLIST_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_group_blocked(group_paths: list[str], blocklist: list[dict]) -> bool:
    """
    判断一个相似分组是否被排除。
    规则：如果某个排除条目与该组有子集关系（任一方向），则该组被排除。
    """
    group_set = set(Path(p).resolve() for p in group_paths)
    for entry in blocklist:
        entry_paths = set(Path(p).resolve() for p in entry.get("paths", []) if p)
        if entry_paths and (entry_paths.issubset(group_set) or group_set.issubset(entry_paths)):
            return True
    return False


def add_blocklist_entry(paths: list[str]) -> tuple[str, int]:
    """添加单条排除条目。返回 (status, count)。"""
    if not paths:
        raise ValueError("路径不能为空")

    blocklist = load_blocklist()
    new_paths = set(Path(p).resolve() for p in paths if p)
    for entry in blocklist:
        existing = set(Path(p).resolve() for p in entry.get("paths", []) if p)
        if new_paths == existing or new_paths.issubset(existing):
            return "covered", len(blocklist)
        if existing.issubset(new_paths):
            entry["paths"] = paths
            entry["timestamp"] = time.time()
            save_blocklist(blocklist)
            return "replaced", len(blocklist)

    blocklist.append({"paths": paths, "timestamp": time.time()})
    save_blocklist(blocklist)
    return "added", len(blocklist)


def add_blocklist_batch(groups: list[list[str]]) -> dict:
    """批量添加排除条目。"""
    if not groups:
        raise ValueError("分组不能为空")

    blocklist = load_blocklist()
    added = 0
    covered = 0
    replaced = 0

    for paths in groups:
        if not paths:
            continue
        new_paths = set(Path(p).resolve() for p in paths if p)
        if not new_paths:
            continue
        handled = False
        for entry in blocklist:
            existing = set(Path(p).resolve() for p in entry.get("paths", []) if p)
            if not existing:
                continue
            if new_paths == existing or new_paths.issubset(existing):
                covered += 1
                handled = True
                break
            if existing.issubset(new_paths):
                entry["paths"] = paths
                entry["timestamp"] = time.time()
                replaced += 1
                handled = True
                break
        if not handled:
            blocklist.append({"paths": paths, "timestamp": time.time()})
            added += 1

    save_blocklist(blocklist)
    return {
        "status": "ok",
        "added": added,
        "covered": covered,
        "replaced": replaced,
        "total": len(blocklist),
    }


def remove_blocklist_entry(paths: list[str]) -> int:
    """移除单条误报记录，返回新的 count。"""
    if not paths:
        raise ValueError("路径不能为空")

    blocklist = load_blocklist()
    target = set(Path(p).resolve() for p in paths if p)
    new_blocklist = [e for e in blocklist if set(Path(p).resolve() for p in e.get("paths", []) if p) != target]
    save_blocklist(new_blocklist)
    return len(new_blocklist)


def clear_blocklist() -> None:
    """清空排除列表。"""
    save_blocklist([])


def filter_blocklist_for_folders(blocklist: list[dict], folders: list[str]) -> list[dict]:
    """按当前扫描文件夹过滤误报记录。"""
    if not folders:
        return blocklist
    folder_resolved = [str(Path(f).resolve()) for f in folders]
    filtered = []
    for entry in blocklist:
        paths = entry.get("paths", [])
        keep = False
        for p in paths:
            try:
                p_resolved = str(Path(p).resolve())
                for f in folder_resolved:
                    if p_resolved.replace("\\", "/").lower().startswith(f.replace("\\", "/").lower()):
                        keep = True
                        break
            except Exception:
                continue
            if keep:
                break
        if keep:
            filtered.append(entry)
    return filtered
