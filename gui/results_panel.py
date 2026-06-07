"""Results panel displaying similarity groups and actions."""

from __future__ import annotations

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


class ResultsPanel(QFrame):
    """Right panel showing scan results with groups and actions."""

    mark_all_false_positive = Signal()
    delete_selected = Signal()
    preview_requested = Signal(str, list)
    selection_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._cards: list[GroupCard] = []
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
        if not groups:
            self.summary_label.setText("未发现相似文件。")
            self.blocklist_info_label.setText(f"已排除 {blocklist_count} 组误报" if blocklist_count > 0 else "")
            return

        img_groups = [g for g in groups if g.get("type") == "image"]
        vid_groups = [g for g in groups if g.get("type") == "video"]
        text = f"发现 {len(groups)} 组相似/重复文件"
        if img_groups and vid_groups:
            text += f"（{len(img_groups)} 组图片、{len(vid_groups)} 组视频）"

        total_items = sum(len(g.get("items", [])) for g in groups)
        text += f"，{total_items} 个文件"
        self.summary_label.setText(text)
        self.blocklist_info_label.setText(f"已排除 {blocklist_count} 组误报" if blocklist_count > 0 else "")

        # Remove stretch first
        stretch = self.groups_layout.takeAt(self.groups_layout.count() - 1)

        for idx, group in enumerate(groups, 1):
            card = GroupCard(
                group_index=idx,
                group_type=group.get("type", "image"),
                items=group.get("items", []),
            )
            card.mark_false_positive.connect(self._on_card_mark_fp)
            card.delete_group_selected.connect(self._on_card_delete)
            card.preview_requested.connect(self.preview_requested.emit)
            card.selection_changed.connect(self.selection_changed.emit)
            self.groups_layout.addWidget(card)
            self._cards.append(card)

        self.groups_layout.addStretch()

    def clear_results(self) -> None:
        for card in self._cards:
            self.groups_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self.summary_label.setText("请在左侧选择文件夹并点击“开始扫描”")
        self.blocklist_info_label.setText("")

    def remove_card(self, card: GroupCard) -> None:
        if card in self._cards:
            self.groups_layout.removeWidget(card)
            card.deleteLater()
            self._cards.remove(card)
        self._update_summary()

    def remove_items(self, paths: set[str]) -> None:
        empty_cards = []
        for card in self._cards:
            card.remove_items_by_path(paths)
            if card.is_empty():
                empty_cards.append(card)
        for card in empty_cards:
            self.remove_card(card)
        self._update_summary()

    def get_selected_paths(self) -> list[str]:
        paths = []
        for card in self._cards:
            paths.extend(card.get_selected_paths())
        return paths

    def get_all_groups_paths(self) -> list[list[str]]:
        groups = []
        for card in self._cards:
            paths = [item["path"] for item in card.items]
            if paths:
                groups.append(paths)
        return groups

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

    def delete_items(self, paths: list[str]) -> None:
        deleted = []
        failed = []
        from pathlib import Path

        for p in paths:
            path = Path(p)
            try:
                if path.exists() and path.is_file():
                    path.unlink()
                    deleted.append(str(path))
            except Exception as e:
                failed.append((p, str(e)))

        if deleted:
            self.remove_items(set(deleted))
        if failed:
            QMessageBox.warning(self, "删除失败", f"{len(failed)} 个文件删除失败：\n" + "\n".join(f"{p}: {e}" for p, e in failed))

    def _update_summary(self) -> None:
        if not self._cards:
            self.summary_label.setText("暂无相似文件分组。")
            return
        img_groups = [c for c in self._cards if c.group_type == "image"]
        vid_groups = [c for c in self._cards if c.group_type == "video"]
        total_items = sum(len(c.items) for c in self._cards)
        text = f"共 {len(self._cards)} 组相似文件"
        if img_groups and vid_groups:
            text += f"（{len(img_groups)} 组图片、{len(vid_groups)} 组视频）"
        text += f"，{total_items} 个文件"
        self.summary_label.setText(text)
