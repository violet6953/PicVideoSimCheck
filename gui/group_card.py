"""Group card widget: displays a similarity group with thumbnails."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .flow_layout import FlowLayout
from .metadata_loader import GroupMetadataLoader
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
        self.is_video = group_type == "video"
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
        self._paths_in_group: list[str] = [item["path"] for item in items]

        # Footer actions (create before widgets so selection signals can update delete_btn)
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

        # Placeholder items: show path + loading state immediately
        self._create_widgets(items)

        container = QFrame()
        container.setLayout(self.flow)
        layout.addWidget(container)
        layout.addLayout(footer_layout)

        # Load metadata asynchronously and re-sort widgets when done
        self._load_metadata()

    def _create_widgets(self, items: list[dict]) -> None:
        """Create ResultItemWidget for each item. Items may be incomplete dicts."""
        paths_in_group = self._paths_in_group
        for item in items:
            path = item["path"]
            rw = ResultItemWidget(path=path, is_video=self.is_video)
            rw.clicked.connect(lambda p=path: self.preview_requested.emit(p, paths_in_group))
            rw.selection_changed.connect(self._on_selection_changed)
            self.flow.addWidget(rw)
            self._item_widgets.append(rw)

        # Auto-check all except the first
        for i, rw in enumerate(self._item_widgets):
            if i > 0:
                rw.set_checked(True)

    def _load_metadata(self) -> None:
        from PySide6.QtCore import QThreadPool

        loader = GroupMetadataLoader(self._paths_in_group, is_video=self.is_video)
        loader.signals.loaded.connect(self._on_metadata_loaded)
        QThreadPool.globalInstance().start(loader)

    def _on_metadata_loaded(self, sorted_items: list[dict]) -> None:
        """Replace placeholder widgets with sorted metadata-populated widgets."""
        # Remove old widgets
        for rw in self._item_widgets:
            self.flow.removeWidget(rw)
            rw.deleteLater()
        self._item_widgets.clear()

        self.items = sorted_items
        self._paths_in_group = [item["path"] for item in sorted_items]
        self._create_widgets(sorted_items)

        # Apply metadata to each widget
        for rw, item in zip(self._item_widgets, sorted_items):
            rw.set_metadata(
                width=item.get("width", 0),
                height=item.get("height", 0),
                size_formatted=item.get("size_formatted", ""),
                duration_formatted=item.get("duration_formatted", "") if self.is_video else "",
            )

        # Re-apply selection state: keep first unselected, others selected
        for i, rw in enumerate(self._item_widgets):
            rw.set_checked(i > 0)
        self._update_delete_button()
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

    def has_single_item(self) -> bool:
        """Return True if only one item remains in the group."""
        return len(self._item_widgets) == 1

    def _on_selection_changed(self) -> None:
        self._update_delete_button()
        self.selection_changed.emit()

    def _update_delete_button(self) -> None:
        has_selected = any(w.is_selected() for w in self._item_widgets)
        self.delete_btn.setEnabled(has_selected)
