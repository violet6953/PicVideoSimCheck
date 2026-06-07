"""Animated button with press feedback using QPropertyAnimation."""

from __future__ import annotations

from PySide6.QtCore import Property, QParallelAnimationGroup, QPropertyAnimation, QEasingCurve, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QPushButton


class AnimatedButton(QPushButton):
    """QPushButton with scale and opacity press/release animations."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._scale = 1.0
        self._setup_animations()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_animations(self) -> None:
        # Scale animation
        self.scale_anim = QPropertyAnimation(self, b"buttonScale")
        self.scale_anim.setDuration(120)
        self.scale_anim.setEasingCurve(QEasingCurve.Type.OutBack)

        # Stylesheet can react to pressed via a dynamic property
        self.setProperty("pressedDepth", 0)

    def get_scale(self) -> float:
        return self._scale

    def set_scale(self, value: float) -> None:
        self._scale = value
        # Use transform scale via stylesheet for performance
        self.setStyleSheet(self.styleSheet() + f"""
            AnimatedButton {{
                transform: scale({value:.3f});
            }}
        """)

    buttonScale = Property(float, get_scale, set_scale)

    def mousePressEvent(self, event) -> None:
        self.setProperty("pressedDepth", 1)
        self.style().unpolish(self)
        self.style().polish(self)
        # Stop any running animation and start press animation
        self.scale_anim.stop()
        self.scale_anim.setStartValue(1.0)
        self.scale_anim.setEndValue(0.96)
        self.scale_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.scale_anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.setProperty("pressedDepth", 0)
        self.style().unpolish(self)
        self.style().polish(self)
        self.scale_anim.stop()
        self.scale_anim.setStartValue(0.96)
        self.scale_anim.setEndValue(1.0)
        self.scale_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self.scale_anim.start()
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        # Subtle hover lift
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
