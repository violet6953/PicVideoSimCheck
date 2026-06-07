"""Custom animated tab widget with smooth transitions."""

from __future__ import annotations

from PySide6.QtCore import (
    QPoint,
    QPropertyAnimation,
    QEasingCurve,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class AnimatedTabs(QFrame):
    """Tab widget with custom tab bar and smooth fade transition between pages."""

    currentChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._tabs: list[tuple[QPushButton, QWidget]] = []
        self._current_index = 0
        self._indicator_anim: QPropertyAnimation | None = None
        self._fade_anim: QPropertyAnimation | None = None
        self._pending_index: int | None = None
        self._overlay: QLabel | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Custom tab bar
        self.tab_bar = QFrame()
        self.tab_bar.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                border-bottom: 2px solid rgba(255, 255, 255, 0.08);
            }
        """)
        tab_layout = QHBoxLayout(self.tab_bar)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)
        layout.addWidget(self.tab_bar)

        # Active indicator line (child of tab_bar so it floats above border)
        self.indicator = QFrame(self.tab_bar)
        self.indicator.setStyleSheet("background-color: #3b82f6; border-radius: 1px;")
        self.indicator.setFixedHeight(3)
        self.indicator.setGeometry(0, 0, 0, 3)
        self.indicator.raise_()

        # Content stack
        self.stack = QStackedWidget()
        self.stack.setObjectName("panel")
        self.stack.setStyleSheet("""
            QStackedWidget#panel {
                background-color: transparent;
                border: none;
            }
        """)
        layout.addWidget(self.stack, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._move_indicator(self._current_index, animate=False)
        self._update_overlay_geometry()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Defer until layout is complete
        QTimer.singleShot(0, lambda: self._move_indicator(self._current_index, animate=False))

    def addTab(self, widget: QWidget, title: str) -> int:
        index = len(self._tabs)
        btn = QPushButton(title)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: none;
                border-bottom: 3px solid transparent;
                padding: 10px 24px;
                font-weight: 500;
                border-radius: 0px;
            }
            QPushButton:hover {
                color: #e2e8f0;
                background-color: rgba(255, 255, 255, 0.03);
            }
            QPushButton:checked {
                color: #3b82f6;
                border-bottom-color: #3b82f6;
                background-color: rgba(59, 130, 246, 0.08);
            }
            QPushButton:pressed {
                padding-top: 11px;
                padding-bottom: 9px;
            }
        """)
        btn.clicked.connect(lambda checked, idx=index: self.setCurrentIndex(idx))

        tab_layout = self.tab_bar.layout()
        tab_layout.addWidget(btn)

        self.stack.addWidget(widget)
        self._tabs.append((btn, widget))

        if index == 0:
            btn.setChecked(True)

        return index

    def setCurrentIndex(self, index: int) -> None:
        if index == self._current_index or not (0 <= index < len(self._tabs)):
            return

        # If an animation is already running, queue the new target
        if self._fade_anim is not None and self._fade_anim.state() == QPropertyAnimation.State.Running:
            self._pending_index = index
            return

        self._current_index = index

        for i, (btn, _) in enumerate(self._tabs):
            btn.setChecked(i == index)

        self._move_indicator(index, animate=True)
        self._fade_to_page(index)
        self.currentChanged.emit(index)

    def currentIndex(self) -> int:
        return self._current_index

    def widget(self, index: int) -> QWidget | None:
        if 0 <= index < len(self._tabs):
            return self._tabs[index][1]
        return None

    def _move_indicator(self, index: int, animate: bool = True) -> None:
        if not self._tabs or not (0 <= index < len(self._tabs)):
            return
        btn = self._tabs[index][0]
        pos = btn.mapTo(self.tab_bar, btn.rect().topLeft())
        target_geo = self.indicator.geometry().__class__(pos.x(), self.tab_bar.height() - 3, btn.width(), 3)

        if animate:
            if self._indicator_anim is not None:
                self._indicator_anim.stop()
            self._indicator_anim = QPropertyAnimation(self.indicator, b"geometry")
            self._indicator_anim.setDuration(250)
            self._indicator_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self._indicator_anim.setStartValue(self.indicator.geometry())
            self._indicator_anim.setEndValue(target_geo)
            self._indicator_anim.start()
        else:
            self.indicator.setGeometry(target_geo)

    def _update_overlay_geometry(self) -> None:
        if self._overlay is None:
            return
        # Position overlay over the stack area
        stack_pos = self.stack.mapTo(self, QPoint(0, 0))
        self._overlay.setGeometry(stack_pos.x(), stack_pos.y(), self.stack.width(), self.stack.height())

    def _fade_to_page(self, new_index: int) -> None:
        if self._fade_anim is not None:
            self._fade_anim.stop()

        self._pending_index = None

        # Use an overlay widget for the fade instead of QGraphicsOpacityEffect on the stack,
        # because applying an opacity effect to a QStackedWidget containing QScrollAreas can
        # cause rendering freezes or performance issues when the content is empty/transparent.
        self._overlay = QLabel(self)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._overlay.setStyleSheet("background-color: #0a0f1a;")
        self._update_overlay_geometry()
        self._overlay.show()
        self._overlay.raise_()

        overlay_opacity = QGraphicsOpacityEffect(self._overlay)
        overlay_opacity.setOpacity(0.0)
        self._overlay.setGraphicsEffect(overlay_opacity)

        # Fade overlay in
        fade_in = QPropertyAnimation(overlay_opacity, b"opacity")
        fade_in.setDuration(90)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def on_fade_in_finished():
            self.stack.setCurrentIndex(new_index)
            # Fade overlay out
            fade_out = QPropertyAnimation(overlay_opacity, b"opacity")
            fade_out.setDuration(150)
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.0)
            fade_out.setEasingCurve(QEasingCurve.Type.OutCubic)

            def on_fade_out_finished():
                self._fade_anim = None
                if self._overlay is not None:
                    self._overlay.deleteLater()
                    self._overlay = None
                if self._pending_index is not None and self._pending_index != self._current_index:
                    self.setCurrentIndex(self._pending_index)

            fade_out.finished.connect(on_fade_out_finished)
            self._fade_anim = fade_out
            fade_out.start()

        fade_in.finished.connect(on_fade_in_finished)
        self._fade_anim = fade_in
        fade_in.start()
