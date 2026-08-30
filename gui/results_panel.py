"""Results panel displaying similarity groups and actions."""

from __future__ import annotations

import errno
import time
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .group_card import GroupCard
from .thumbnail_loader import clear_pixmap_cache_for


def _is_file_locked_error(exc: OSError) -> bool:
    """Return True if *exc* indicates the file is locked by another process."""
    if hasattr(exc, "winerror"):
        # ERROR_SHARING_VIOLATION
        return exc.winerror == 32
    return exc.errno in (errno.EBUSY, errno.EAGAIN)


def _find_locking_processes(path: str) -> list[str]:
    """Best-effort query of processes locking *path* on Windows via RestartManager."""
    import sys

    if sys.platform != "win32":
        return []

    try:
        import ctypes
        from ctypes import wintypes

        rm_start = ctypes.windll.rstrtmgr.RmStartSession
        rm_start.argtypes = [ctypes.POINTER(ctypes.c_uint), ctypes.c_ulong, ctypes.c_wchar_p]
        rm_start.restype = ctypes.c_uint

        rm_register = ctypes.windll.rstrtmgr.RmRegisterResources
        rm_register.argtypes = [
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_void_p,
        ]
        rm_register.restype = ctypes.c_uint

        rm_get_list = ctypes.windll.rstrtmgr.RmGetList
        rm_get_list.argtypes = [
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        rm_get_list.restype = ctypes.c_uint

        rm_end = ctypes.windll.rstrtmgr.RmEndSession
        rm_end.argtypes = [ctypes.c_uint]
        rm_end.restype = ctypes.c_uint

        session = ctypes.c_uint()
        key = ctypes.create_unicode_buffer("")
        ret = rm_start(ctypes.byref(session), 0, key)
        if ret != 0:
            return []

        try:
            path_buf = ctypes.create_unicode_buffer(path)
            ret = rm_register(session, 1, path_buf, 0, None, 0, None)
            if ret != 0:
                return []

            needed = ctypes.c_uint()
            proc_count = ctypes.c_uint()
            reboot = ctypes.c_ulong()
            ret = rm_get_list(
                session,
                ctypes.byref(needed),
                ctypes.byref(proc_count),
                None,
                ctypes.byref(reboot),
            )
            if ret != 122:  # ERROR_MORE_DATA
                return []

            class RM_PROCESS_INFO(ctypes.Structure):
                _fields_ = [
                    ("Process", wintypes.DWORD),
                    ("StartTime", wintypes.FILETIME),
                    ("AppName", wintypes.WCHAR * 256),
                    ("ShortServiceName", wintypes.WCHAR * 64),
                    ("ApplicationType", wintypes.DWORD),
                    ("AppStatus", wintypes.DWORD),
                    ("TSSessionId", wintypes.DWORD),
                    ("PerformanceImpact", wintypes.DWORD),
                ]

            proc_info = (RM_PROCESS_INFO * needed.value)()
            ret = rm_get_list(
                session,
                ctypes.byref(needed),
                ctypes.byref(proc_count),
                proc_info,
                ctypes.byref(reboot),
            )
            if ret != 0:
                return []

            processes: list[str] = []
            for i in range(proc_count.value):
                name = proc_info[i].AppName.strip("\x00")
                if name and name not in processes:
                    processes.append(name)
            return processes
        finally:
            rm_end(session)
    except Exception:
        return []


def _delete_with_retry(path: Path) -> None:
    """Delete *path*, retrying a few times if it is temporarily locked."""
    last_error: Exception | None = None
    for delay in (0.0, 0.3, 0.6, 1.2):
        if delay:
            time.sleep(delay)
        try:
            path.unlink()
            return
        except OSError as exc:
            last_error = exc
            if not _is_file_locked_error(exc):
                raise
    # All retries exhausted for a locked file.
    raise last_error or OSError(errno.EBUSY, "文件被占用", str(path))


class ResultsPanel(QFrame):
    """Right panel showing scan results with groups and actions."""

    mark_all_false_positive = Signal()
    delete_selected = Signal()
    preview_requested = Signal(str, list)
    selection_changed = Signal()

    # Number of groups to render per page to keep widget creation fast.
    GROUPS_PER_PAGE = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._all_groups: list[dict] = []
        self._cards: list[GroupCard] = []
        self._load_more_btn: QPushButton | None = None
        self._footer_widget: QWidget | None = None
        self._current_page = 0
        self._blocklist_count = 0
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        header_layout = QHBoxLayout()
        title_layout = QHBoxLayout()
        title = QLabel("扫描结果")
        title.setObjectName("sectionTitle")
        title_layout.addWidget(title)
        self.blocklist_info_label = QLabel("")
        self.blocklist_info_label.setObjectName("statusOk")
        title_layout.addWidget(self.blocklist_info_label)
        title_layout.addStretch()
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        self.mark_all_btn = QPushButton("一键清除误报")
        self.mark_all_btn.setObjectName("secondary")
        self.mark_all_btn.setProperty("class", "small")
        self.mark_all_btn.clicked.connect(self.mark_all_false_positive.emit)
        header_layout.addWidget(self.mark_all_btn)

        self.delete_btn = QPushButton("删除选中")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.setProperty("class", "small")
        self.delete_btn.clicked.connect(self._confirm_delete_selected)
        header_layout.addWidget(self.delete_btn)
        layout.addLayout(header_layout)

        self.summary_label = QLabel("请在左侧选择文件夹并点击“开始扫描”")
        self.summary_label.setObjectName("labelMuted")
        layout.addWidget(self.summary_label)

        # Scroll area for groups
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
        """)

        self.groups_container = QWidget()
        self.groups_layout = QVBoxLayout(self.groups_container)
        self.groups_layout.setSpacing(16)
        self.groups_layout.addStretch()
        self.scroll.setWidget(self.groups_container)
        layout.addWidget(self.scroll)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        # Keep groups container width matching scroll area to avoid horizontal relayout
        if self.groups_container:
            self.groups_container.setFixedWidth(self.scroll.viewport().width())

    def set_results(self, groups: list[dict], blocklist_count: int = 0) -> None:
        self.clear_results()
        self._all_groups = list(groups)
        self._blocklist_count = blocklist_count
        self._current_page = 0

        if not groups:
            self.summary_label.setText("未发现相似文件。")
            self.blocklist_info_label.setText(f"已排除 {blocklist_count} 组误报" if blocklist_count > 0 else "")
            return

        self._update_summary()
        self.blocklist_info_label.setText(f"已排除 {blocklist_count} 组误报" if blocklist_count > 0 else "")

        # Render first page
        self._render_page(0)

    def _render_page(self, page: int) -> None:
        """Render one page of groups. Removes the load-more footer first if present."""
        self._remove_footer()

        # Remove stretch to append widgets, then re-add it at the end
        stretch = self.groups_layout.takeAt(self.groups_layout.count() - 1)

        start = page * self.GROUPS_PER_PAGE
        end = min(start + self.GROUPS_PER_PAGE, len(self._all_groups))
        for idx in range(start, end):
            group = self._all_groups[idx]
            card = GroupCard(
                group_index=idx + 1,
                group_type=group.get("type", "image"),
                items=group.get("items", []),
            )
            card.mark_false_positive.connect(self._on_card_mark_fp)
            card.delete_group_selected.connect(self._on_card_delete)
            card.preview_requested.connect(self.preview_requested.emit)
            card.selection_changed.connect(self.selection_changed.emit)
            self.groups_layout.addWidget(card)
            self._cards.append(card)

        self._current_page = page

        # Add load-more footer if there are more groups. Because not all groups
        # are rendered, also surface a delete button here so the user can remove
        # selected files without scrolling back to the top header.
        if end < len(self._all_groups):
            remaining = len(self._all_groups) - end
            self._footer_widget = QWidget()
            footer_layout = QHBoxLayout(self._footer_widget)
            footer_layout.setContentsMargins(0, 0, 0, 0)
            footer_layout.setSpacing(12)

            self._load_more_btn = QPushButton(f"加载更多（还剩 {remaining} 组）")
            self._load_more_btn.setObjectName("secondary")
            self._load_more_btn.clicked.connect(self._load_next_page)
            footer_layout.addWidget(self._load_more_btn, stretch=1)

            delete_selected_btn = QPushButton("删除所有选中")
            delete_selected_btn.setObjectName("danger")
            delete_selected_btn.clicked.connect(self._confirm_delete_all_selected)
            footer_layout.addWidget(delete_selected_btn)

            self.groups_layout.addWidget(self._footer_widget)

        self.groups_layout.addStretch()
        if stretch and stretch.widget():
            stretch.widget().deleteLater()

    def _load_next_page(self) -> None:
        next_page = self._current_page + 1
        if next_page * self.GROUPS_PER_PAGE < len(self._all_groups):
            self._render_page(next_page)

    def _remove_footer(self) -> None:
        """Remove the load-more / delete footer if it is currently shown."""
        if self._footer_widget:
            self.groups_layout.removeWidget(self._footer_widget)
            self._footer_widget.deleteLater()
            self._footer_widget = None
        self._load_more_btn = None

    def clear_results(self) -> None:
        for card in self._cards:
            self.groups_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._all_groups.clear()
        self._remove_footer()
        self._current_page = 0
        self.summary_label.setText("请在左侧选择文件夹并点击“开始扫描”")
        self.blocklist_info_label.setText("")

    def remove_card(self, card: GroupCard) -> None:
        if card in self._cards:
            self.groups_layout.removeWidget(card)
            card.deleteLater()
            self._cards.remove(card)
        # Keep the stored full group list in sync
        card_paths = {item["path"] for item in card.items}
        self._all_groups = [
            g
            for g in self._all_groups
            if {item["path"] for item in g.get("items", [])} != card_paths
        ]
        self._update_summary()

    def remove_items(self, paths: set[str]) -> None:
        cards_to_remove = []
        for card in self._cards:
            card.remove_items_by_path(paths)
            # Remove the group if it is empty or only one item remains,
            # because a single file is no longer a similarity group.
            if card.is_empty() or card.has_single_item():
                cards_to_remove.append(card)
        for card in cards_to_remove:
            self.remove_card(card)

        # Update the stored full group list, dropping groups with 0 or 1 item
        new_all_groups: list[dict] = []
        for g in self._all_groups:
            new_items = [item for item in g.get("items", []) if item["path"] not in paths]
            if len(new_items) > 1:
                new_all_groups.append({**g, "items": new_items})
        self._all_groups = new_all_groups
        self._update_summary()

    def get_selected_paths(self) -> list[str]:
        paths = []
        for card in self._cards:
            paths.extend(card.get_selected_paths())
        return paths

    def get_selected_paths_all(self) -> list[str]:
        """Selected paths across rendered cards, plus the default selection for
        groups that have not been rendered yet.

        Unrendered groups have no checkboxes, so we apply the same default rule a
        rendered card uses: keep the first item (the best/largest, since the scan
        worker pre-sorts each group with the same sort key) and select the rest.
        """
        paths: list[str] = []
        rendered_first_paths: set[str] = set()
        for card in self._cards:
            paths.extend(card.get_selected_paths())
            if card.items:
                rendered_first_paths.add(card.items[0]["path"])

        for g in self._all_groups:
            items = g.get("items", [])
            if not items:
                continue
            # Skip groups already shown as a card (handled via checkboxes above).
            if items[0]["path"] in rendered_first_paths:
                continue
            paths.extend(item["path"] for item in items[1:])

        # De-duplicate while preserving order.
        return list(dict.fromkeys(paths))

    def get_all_groups_paths(self) -> list[list[str]]:
        return [
            [item["path"] for item in g.get("items", [])]
            for g in self._all_groups
            if g.get("items")
        ]

    def set_blocklist_info(self, count: int) -> None:
        self.blocklist_info_label.setText(f"已排除 {count} 组误报" if count > 0 else "")

    def _on_card_mark_fp(self, card: GroupCard) -> None:
        paths = [item["path"] for item in card.items]
        if paths:
            from services.blocklist_service import add_blocklist_entry

            try:
                status, count = add_blocklist_entry(paths)
                if status in ("added", "covered", "replaced"):
                    self.remove_card(card)
                    self.selection_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"标记误报失败：{e}")

    def _on_card_delete(self, card: GroupCard) -> None:
        paths = card.get_selected_paths()
        if not paths:
            QMessageBox.information(self, "提示", "请先勾选本组中要删除的文件")
            return
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除本组选中的 {len(paths)} 个文件吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_items(paths)

    def _confirm_delete_selected(self) -> None:
        paths = self.get_selected_paths()
        if not paths:
            QMessageBox.information(self, "提示", "请先勾选要删除的文件")
            return
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {len(paths)} 个文件吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_selected.emit()

    def _confirm_delete_all_selected(self) -> None:
        """Delete selected files across ALL groups, including ones not yet rendered.

        Used by the footer button shown when groups are paginated, so the user can
        clear every selected file without scrolling up or loading every page first.
        """
        paths = self.get_selected_paths_all()
        if not paths:
            QMessageBox.information(self, "提示", "请先勾选要删除的文件")
            return

        rendered_groups = len(self._cards)
        unrendered_groups = max(0, len(self._all_groups) - rendered_groups)
        extra = (
            f"\n（含 {unrendered_groups} 个未加载分组中默认选中的文件）"
            if unrendered_groups > 0
            else ""
        )
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {len(paths)} 个文件吗？{extra}\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_items(paths)

    def delete_items(self, paths: list[str]) -> None:
        deleted = []
        failed = []

        # Release any cached pixmaps/thumbnails that may hold file handles.
        clear_pixmap_cache_for(paths)

        for p in paths:
            path = Path(p)
            try:
                if path.exists() and path.is_file():
                    _delete_with_retry(path)
                    deleted.append(str(path))
            except Exception as e:
                failed.append((p, str(e)))

        if deleted:
            self.remove_items(set(deleted))
        if failed:
            messages = []
            for p, e in failed:
                locking = _find_locking_processes(p)
                if locking:
                    proc_text = "、".join(locking[:3])
                    messages.append(f"{p}\n  原因：{e}（可能被「{proc_text}」占用）")
                else:
                    messages.append(f"{p}\n  原因：{e}")
            QMessageBox.warning(
                self,
                "删除失败",
                f"{len(failed)} 个文件删除失败：\n\n" + "\n\n".join(messages)
                + "\n\n请关闭播放器、浏览器或杀毒软件后重试。",
            )

    def _update_summary(self) -> None:
        if not self._all_groups:
            self.summary_label.setText("暂无相似文件分组。")
            return
        img_groups = [g for g in self._all_groups if g.get("type") == "image"]
        vid_groups = [g for g in self._all_groups if g.get("type") == "video"]
        total_items = sum(len(g.get("items", [])) for g in self._all_groups)
        text = f"共 {len(self._all_groups)} 组相似文件"
        if img_groups and vid_groups:
            text += f"（{len(img_groups)} 组图片、{len(vid_groups)} 组视频）"
        text += f"，{total_items} 个文件"
        self.summary_label.setText(text)
