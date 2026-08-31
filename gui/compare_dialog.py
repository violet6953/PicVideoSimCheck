"""Dialog for side-by-side comparison of two similar images."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt, QThreadPool
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .thumbnail_loader import ThumbnailLoader, get_cached_pixmap
from .win_dark_titlebar import set_dark_title_bar


class _CompareImageView(QWidget):
    """Single image view supporting synchronized zoom and pan."""

    def __init__(self, dialog: CompareDialog, side: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._dialog = dialog
        self._side = side
        self._pixmap: QPixmap | None = None
        self._dragging = False

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#0a0f1a"))

        if self._pixmap is None or self._pixmap.isNull():
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "无法加载图片")
            return

        widget_rect = self.rect()
        fit = self._pixmap.scaled(
            widget_rect.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        zoom = self._dialog.zoom
        pan = self._dialog.pan

        target_w = int(fit.width() * zoom)
        target_h = int(fit.height() * zoom)
        x = widget_rect.x() + (widget_rect.width() - target_w) // 2 + int(pan.x())
        y = widget_rect.y() + (widget_rect.height() - target_h) // 2 + int(pan.y())

        painter.drawPixmap(x, y, target_w, target_h, self._pixmap)

        # Left side uses red border, right side uses blue border.
        color = "#ef4444" if self._side == "left" else "#3b82f6"
        pen = QPen(QColor(color))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        delta = event.angleDelta().y()
        step = 0.15 if delta > 0 else -0.15
        self._dialog.change_zoom(step)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._dialog.toggle_side_selection(self._side)
            self._dialog.start_pan(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._dialog.move_pan(event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self._dialog.end_pan()
        super().mouseReleaseEvent(event)


class CompareDialog(QDialog):
    """Modal-less dialog for comparing two images with synchronized zoom/pan."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("比较图片")

        self._paths: list[str] = []
        self._slot_indices = [0, 0]  # two logical selected indices
        self._active_slot = 1        # slot replaced on next thumbnail click
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)

        self._drag_start_global: QPoint | None = None
        self._pan_start = QPointF(0.0, 0.0)
        self._thumbnail_buttons: dict[str, QPushButton] = {}

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header row
        header = QHBoxLayout()

        left_header = QVBoxLayout()
        left_header.setSpacing(2)
        left_title = QLabel("左图")
        left_title.setObjectName("sectionTitle")
        self._left_name_label = QLabel("")
        self._left_name_label.setObjectName("labelMuted")
        self._left_name_label.setWordWrap(False)
        self._left_path_label = QLabel("")
        self._left_path_label.setObjectName("labelMuted")
        self._left_path_label.setWordWrap(False)
        self._left_path_label.setStyleSheet("font-size: 11px; color: #64748b;")
        left_header.addWidget(left_title)
        left_header.addWidget(self._left_name_label)
        left_header.addWidget(self._left_path_label)
        header.addLayout(left_header)

        header.addStretch()

        swap_btn = QPushButton("⇄ 切换侧")
        swap_btn.setObjectName("secondary")
        swap_btn.setProperty("class", "small")
        swap_btn.clicked.connect(self._swap_sides)
        header.addWidget(swap_btn)

        header.addStretch()

        right_header = QVBoxLayout()
        right_header.setSpacing(2)
        right_title = QLabel("右图")
        right_title.setObjectName("sectionTitle")
        self._right_name_label = QLabel("")
        self._right_name_label.setObjectName("labelMuted")
        self._right_name_label.setWordWrap(False)
        self._right_path_label = QLabel("")
        self._right_path_label.setObjectName("labelMuted")
        self._right_path_label.setWordWrap(False)
        self._right_path_label.setStyleSheet("font-size: 11px; color: #64748b;")
        right_header.addWidget(right_title)
        right_header.addWidget(self._right_name_label)
        right_header.addWidget(self._right_path_label)
        header.addLayout(right_header)

        layout.addLayout(header)

        # Image views
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._left_view = _CompareImageView(self, "left")
        self._right_view = _CompareImageView(self, "right")
        self._splitter.addWidget(self._left_view)
        self._splitter.addWidget(self._right_view)
        self._splitter.setSizes([480, 480])
        layout.addWidget(self._splitter, 1)

        # Thumbnail strip
        thumb_container = QWidget()
        self._thumb_layout = QHBoxLayout(thumb_container)
        self._thumb_layout.setContentsMargins(0, 0, 0, 0)
        self._thumb_layout.setSpacing(8)
        self._thumb_layout.addStretch()

        self._thumb_scroll = QScrollArea()
        self._thumb_scroll.setWidgetResizable(True)
        self._thumb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._thumb_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._thumb_scroll.setFixedHeight(110)
        self._thumb_scroll.setWidget(thumb_container)
        self._thumb_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        layout.addWidget(self._thumb_scroll)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("secondary")
        close_btn.clicked.connect(self.close)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

        self._center_on_parent_screen()

    @property
    def zoom(self) -> float:
        return self._zoom

    @property
    def pan(self) -> QPointF:
        return self._pan

    @property
    def left_selected(self) -> bool:
        return True

    @property
    def right_selected(self) -> bool:
        return True

    @property
    def active_side(self) -> str | None:
        return None

    def toggle_side_selection(self, side: str) -> None:
        """Clicking a side makes the slot currently shown on that side active."""
        left_idx, right_idx = self._sorted_indices()
        slot_for_left = 0 if self._slot_indices[0] == left_idx else 1
        slot_for_right = 1 - slot_for_left
        if side == "left":
            self._active_slot = slot_for_left
        else:
            self._active_slot = slot_for_right
        self._update_active_markers()
        self._update_thumbnail_borders()

    def change_zoom(self, step: float) -> None:
        new_zoom = max(1.0, min(5.0, self._zoom + step))
        if new_zoom != self._zoom:
            self._zoom = new_zoom
            self._left_view.update()
            self._right_view.update()

    def start_pan(self, global_pos: QPoint) -> None:
        self._drag_start_global = global_pos
        self._pan_start = QPointF(self._pan)

    def move_pan(self, global_pos: QPoint) -> None:
        if self._drag_start_global is None:
            return
        delta = global_pos - self._drag_start_global
        self._pan = QPointF(self._pan_start.x() + delta.x(), self._pan_start.y() + delta.y())
        self._left_view.update()
        self._right_view.update()

    def end_pan(self) -> None:
        self._drag_start_global = None

    def load_group(self, paths: list[str]) -> None:
        self._paths = list(paths)
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._slot_indices = [0, min(1, len(self._paths) - 1)]
        self._active_slot = 1

        self._build_thumbnails()
        self._update_images()
        self._update_active_markers()

        self.show()
        self.raise_()
        self.activateWindow()

    def _build_thumbnails(self) -> None:
        # Remove old thumbnail buttons (all but the trailing stretch)
        while self._thumb_layout.count() > 1:
            item = self._thumb_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._thumbnail_buttons.clear()

        for path in self._paths:
            btn = QPushButton()
            btn.setFixedSize(90, 70)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("compare_path", path)
            btn.clicked.connect(lambda checked=False, p=path: self._on_thumbnail_clicked(p))
            self._thumb_layout.insertWidget(self._thumb_layout.count() - 1, btn)
            self._thumbnail_buttons[path] = btn

            cached = get_cached_pixmap(path)
            if cached is not None:
                self._set_button_pixmap(btn, cached)
            else:
                loader = ThumbnailLoader(path, 90, 70)
                loader.signals.loaded.connect(self._on_thumbnail_loaded)
                QThreadPool.globalInstance().start(loader)

        self._update_thumbnail_borders()

    def _on_thumbnail_loaded(self, path: str, pixmap: QPixmap) -> None:
        btn = self._thumbnail_buttons.get(path)
        if btn is None:
            return
        self._set_button_pixmap(btn, pixmap)

    def _set_button_pixmap(self, btn: QPushButton, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            86,
            66,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        btn.setIcon(QIcon(scaled))
        btn.setIconSize(QSize(86, 66))

    def _on_thumbnail_clicked(self, path: str) -> None:
        index = self._paths.index(path)
        if index in self._slot_indices:
            return
        self._slot_indices[self._active_slot] = index
        self._active_slot = 1 - self._active_slot
        self._update_images()
        self._update_active_markers()

    def _swap_sides(self) -> None:
        """Switch the active slot so the next thumbnail click replaces the other side."""
        self._active_slot = 1 - self._active_slot
        self._update_active_markers()
        self._update_thumbnail_borders()

    def _sorted_indices(self) -> tuple[int, int]:
        """Return the two selected indices sorted for left/right display."""
        a, b = self._slot_indices
        return (a, b) if a <= b else (b, a)

    def _update_images(self) -> None:
        if not self._paths:
            return

        left_idx, right_idx = self._sorted_indices()
        left_path = self._paths[left_idx]
        right_path = self._paths[right_idx]

        left_pixmap = QPixmap(left_path)
        right_pixmap = QPixmap(right_path)

        self._left_view.set_pixmap(left_pixmap)
        self._right_view.set_pixmap(right_pixmap)

        self._left_name_label.setText(Path(left_path).name)
        self._left_name_label.setToolTip(left_path)
        self._left_path_label.setText(left_path)
        self._left_path_label.setToolTip(left_path)
        self._right_name_label.setText(Path(right_path).name)
        self._right_name_label.setToolTip(right_path)
        self._right_path_label.setText(right_path)
        self._right_path_label.setToolTip(right_path)

        self._update_thumbnail_borders()

    def _update_thumbnail_borders(self) -> None:
        left_idx, right_idx = self._sorted_indices()
        for path, btn in self._thumbnail_buttons.items():
            index = self._paths.index(path)
            if index == left_idx:
                color = "#ef4444"
            elif index == right_idx:
                color = "#3b82f6"
            else:
                color = "transparent"

            btn.setStyleSheet(f"""
                QPushButton {{
                    border: 2px solid {color};
                    border-radius: 6px;
                    background-color: #0f172a;
                }}
                QPushButton:hover {{
                    border-color: #f97316;
                }}
            """)

    def _update_active_markers(self) -> None:
        self._left_view.update()
        self._right_view.update()

    def _center_on_parent_screen(self) -> None:
        parent = self.parent()
        if parent is not None:
            screen = parent.screen()
        else:
            screen = QApplication.primaryScreen()

        if screen is None:
            return

        available = screen.availableGeometry()
        screen_w = available.width()
        screen_h = available.height()
        scale = 0.85
        target_w = int(screen_w * scale)
        target_h = int(screen_h * scale)
        screen_ratio = screen_w / screen_h
        dialog_ratio = target_w / target_h
        if dialog_ratio > screen_ratio:
            target_w = int(target_h * screen_ratio)
        elif dialog_ratio < screen_ratio:
            target_h = int(target_w / screen_ratio)

        x = available.x() + (screen_w - target_w) // 2
        y = available.y() + (screen_h - target_h) // 2
        self.setGeometry(x, y, target_w, target_h)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        set_dark_title_bar(int(self.winId()))

    def closeEvent(self, event) -> None:
        self._left_view.set_pixmap(None)
        self._right_view.set_pixmap(None)
        super().closeEvent(event)
