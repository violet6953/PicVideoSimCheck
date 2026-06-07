"""Blocklist panel showing ignored groups with batched lazy loading."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
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

from .flow_layout import FlowLayout
from .result_item import ResultItemWidget
from services.blocklist_service import (
    clear_blocklist,
    load_blocklist,
    remove_blocklist_entry,
)

_BATCH_SIZE = 15  # Cards created per batch
_SCROLL_THRESHOLD = 250  # px from bottom to trigger next batch


class BlocklistPanel(QFrame):
    """Panel displaying blocklisted groups with unblock action."""

    blocklist_changed = Signal()
    preview_requested = Signal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._cached_folders: tuple[str, ...] | None = None
        self._cached_count: int = -1

        # Lazy-loading state
        self._all_entries: list[dict] = []
        self._next_batch_index: int = 0
        self._hidden_count: int = 0
        self._scroll_connected: bool = False

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("误报记录")
        title.setObjectName("sectionTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.clear_btn = QPushButton("清除全部记录")
        self.clear_btn.setObjectName("secondary")
        self.clear_btn.setProperty("class", "small")
        self.clear_btn.clicked.connect(self._confirm_clear)
        header_layout.addWidget(self.clear_btn)
        layout.addLayout(header_layout)

        self.summary_label = QLabel("暂无被忽略的误报记录。")
        self.summary_label.setObjectName("labelMuted")
        layout.addWidget(self.summary_label)

        # Scroll area
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

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(16)
        self.container_layout.addStretch()
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    # ------------------------------------------------------------------
    # Lazy loading helpers
    # ------------------------------------------------------------------

    def _connect_scroll(self) -> None:
        """Attach scroll listener once."""
        if not self._scroll_connected:
            self.scroll.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
            self._scroll_connected = True

    def _disconnect_scroll(self) -> None:
        """Detach scroll listener."""
        if self._scroll_connected:
            try:
                self.scroll.verticalScrollBar().valueChanged.disconnect(self._on_scroll_changed)
            except Exception:
                pass
            self._scroll_connected = False

    def _on_scroll_changed(self, value: int) -> None:
        scrollbar = self.scroll.verticalScrollBar()
        if scrollbar.maximum() == 0:
            return
        # Trigger when near bottom
        if scrollbar.maximum() - value < _SCROLL_THRESHOLD:
            self._load_next_batch()

    def _load_next_batch(self) -> None:
        """Create the next batch of cards."""
        if self._next_batch_index >= len(self._all_entries):
            return

        end = min(self._next_batch_index + _BATCH_SIZE, len(self._all_entries))
        for i in range(self._next_batch_index, end):
            entry = self._all_entries[i]
            paths = entry.get("paths", [])
            if not paths:
                continue
            card = self._create_blocklist_card(i + 1, paths)
            # Insert before the trailing stretch
            self.container_layout.insertWidget(self.container_layout.count() - 1, card)

        self._next_batch_index = end

        # Update summary to show progress
        total = len(self._all_entries)
        loaded = min(self._next_batch_index, total)
        text = f"共 {total} 组被忽略的记录"
        if loaded < total:
            text += f"（已加载 {loaded}/{total}，向下滚动加载更多）"
        if self._hidden_count > 0:
            text += f"（另有 {self._hidden_count} 组不在当前扫描文件夹中，已隐藏）"
        self.summary_label.setText(text)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self, current_folders: list[str] | None = None, force: bool = False) -> None:
        folders_key = tuple(sorted(current_folders or []))
        blocklist = load_blocklist()
        total_count = len(blocklist)

        # Cache hit: same folders and same blocklist count -> skip rebuild
        if not force and folders_key == self._cached_folders and total_count == self._cached_count:
            return

        self._cached_folders = folders_key
        self._cached_count = total_count

        # Stop any pending scroll loads
        self._disconnect_scroll()

        # Clear existing widgets (keep the trailing stretch)
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if current_folders:
            from services.blocklist_service import filter_blocklist_for_folders
            filtered = filter_blocklist_for_folders(blocklist, current_folders)
            self._hidden_count = total_count - len(filtered)
        else:
            filtered = blocklist
            self._hidden_count = 0

        reversed_entries = list(reversed(filtered))

        if not reversed_entries:
            self._all_entries = []
            self._next_batch_index = 0
            if self._hidden_count > 0:
                self.summary_label.setText(
                    f"当前扫描文件夹中无被忽略的记录（另有 {self._hidden_count} 组误报记录不在当前扫描文件夹中，已隐藏）"
                )
            else:
                self.summary_label.setText("暂无被忽略的误报记录。")
            return

        self._all_entries = reversed_entries
        self._next_batch_index = 0

        # Load first batch immediately, rest on scroll
        self._load_next_batch()
        self._connect_scroll()

        # If first batch didn't fill the viewport, load more
        QTimer.singleShot(50, self._load_more_if_needed)

    def _load_more_if_needed(self) -> None:
        """Load additional batches until the viewport is filled or all loaded."""
        scrollbar = self.scroll.verticalScrollBar()
        # If scrollbar is not needed (content fits) and more to load, keep loading
        if scrollbar.maximum() == 0 and self._next_batch_index < len(self._all_entries):
            self._load_next_batch()
            QTimer.singleShot(50, self._load_more_if_needed)

    def _create_blocklist_card(self, index: int, paths: list[str]) -> QFrame:
        card = QFrame()
        card.setObjectName("groupCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel(f"被忽略分组 {index} - 共 {len(paths)} 个")
        header.setObjectName("labelMuted")
        layout.addWidget(header)

        flow = FlowLayout(spacing=12)
        for p in paths:
            rw = ResultItemWidget(
                path=p,
                name=p.split("/")[-1].split("\\")[-1],
                resolution="",
                size_text="",
                is_video=False,
            )
            rw.checkbox.setVisible(False)
            rw.clicked.connect(lambda clicked_path, group_paths=paths: self.preview_requested.emit(clicked_path, group_paths))
            flow.addWidget(rw)
        container = QWidget()
        container.setLayout(flow)
        layout.addWidget(container)

        footer = QHBoxLayout()
        footer.addStretch()
        unblock_btn = QPushButton("停止忽略该组")
        unblock_btn.setObjectName("primary")
        unblock_btn.setProperty("class", "small")
        unblock_btn.clicked.connect(lambda _checked, c=card, ps=paths: self._unblock_group(c, ps))
        footer.addWidget(unblock_btn)
        layout.addLayout(footer)

        return card

    def _unblock_group(self, card: QFrame, paths: list[str]) -> None:
        try:
            remove_blocklist_entry(paths)
            self.container_layout.removeWidget(card)
            card.deleteLater()
            self._cached_count = -1  # invalidate cache
            self.blocklist_changed.emit()
            self.refresh(force=True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"操作失败：{e}")

    def _confirm_clear(self) -> None:
        reply = QMessageBox.question(
            self,
            "确认清除",
            "确定清除所有误报排除记录吗？下次扫描将重新显示这些分组。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            clear_blocklist()
            self._cached_count = -1  # invalidate cache
            self.refresh(force=True)
            self.blocklist_changed.emit()
