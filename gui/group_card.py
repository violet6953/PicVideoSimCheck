"""Group card widget: displays a similarity group with thumbnails."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .flow_layout import FlowLayout
from .result_item import ResultItemWidget


class GroupCard(QFrame):
    """Widget representing one group of similar images/videos."""

    mark_false_positive = Signal(object)  # emits self
    delete_group_selected = Signal(object)  # emits self
    preview_requested = Signal(str, list)  # path, list of paths in group
    selection_changed = Signal()

    def __init__(self, group_index: int, group_type: str, items: list[dict], parent=None):
        super().__init__(parent)
        self.group_index = group_index
        self.group_type = group_type  # "image" or "video"
        self.items = items
        self.setObjectName("groupCardVideo" if group_type == "video" else "groupCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        type_badge = QLabel("视频" if group_type == "video" else "图片")
        type_badge.setObjectName("typeBadgeVideo" if group_type == "video" else "typeBadgeImage")
        header_layout.addWidget(type_badge)
        header_layout.addWidget(QLabel(f"分组 {group_index} - 共 {len(items)} 个"))
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Thumbnail grid
        self.flow = FlowLayout(spacing=12)
        self._item_widgets: list[ResultItemWidget] = []
        paths_in_group: list[str] = []

        for i, item in enumerate(items):
            path = item["path"]
            paths_in_group.append(path)
            rw = ResultItemWidget(
                path=path,
                name=item.get("name", ""),
                resolution=item.get("resolution", ""),
                size_text=item.get("size_formatted", ""),
                duration_text=item.get("duration_formatted", ""),
                is_video=(group_type == "video"),
            )
            rw.clicked.connect(lambda p=path: self.preview_requested.emit(p, paths_in_group))
            rw.selection_changed.connect(self._on_selection_changed)
            self.flow.addWidget(rw)
            self._item_widgets.append(rw)

        container = QFrame()
        container.setLayout(self.flow)
        layout.addWidget(container)

        # Footer actions
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        self.mark_fp_btn = QPushButton("标记为非相似（误报）")
        self.mark_fp_btn.setObjectName("secondary")
        self.mark_fp_btn.setProperty("class", "small")
        self.mark_fp_btn.clicked.connect(lambda: self.mark_false_positive.emit(self))
        footer_layout.addWidget(self.mark_fp_btn)

        self.delete_btn = QPushButton("删除本组选中")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.setProperty("class", "small")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(lambda: self.delete_group_selected.emit(self))
        footer_layout.addWidget(self.delete_btn)

        layout.addLayout(footer_layout)

        # Auto-check all except the first (done after delete_btn is created)
        for i, rw in enumerate(self._item_widgets):
            if i > 0:
                rw.set_checked(True)

    def get_selected_paths(self) -> list[str]:
        return [w.path for w in self._item_widgets if w.is_selected()]

    def remove_items_by_path(self, paths: set[str]) -> None:
        to_remove = [w for w in self._item_widgets if w.path in paths]
        for w in to_remove:
            self.flow.removeWidget(w)
            w.deleteLater()
            self._item_widgets.remove(w)
        self._update_delete_button()

    def is_empty(self) -> bool:
        return len(self._item_widgets) == 0

    def _on_selection_changed(self) -> None:
        self._update_delete_button()
        self.selection_changed.emit()

    def _update_delete_button(self) -> None:
        has_selected = any(w.is_selected() for w in self._item_widgets)
        self.delete_btn.setEnabled(has_selected)
