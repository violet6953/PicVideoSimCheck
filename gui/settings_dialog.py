"""Application settings dialog.

Currently manages the persistent feature cache directory. The dialog is
self-contained: it accepts the current cache directory and default path,
then returns the chosen path via `selected_cache_dir()`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from services.feature_cache_service import clear_cache, get_cache_dir, get_default_cache_dir

from .win_dark_titlebar import set_dark_title_bar


def _format_size(size_bytes: int) -> str:
    """Format bytes to a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""

    def __init__(self, current_cache_dir: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(560, 220)
        self._current_cache_dir = current_cache_dir or str(get_cache_dir())
        self._default_cache_dir = str(get_default_cache_dir())
        self._selected_cache_dir = self._current_cache_dir

        self._init_ui()
        self._refresh_size_label()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("应用设置")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        # Cache directory row
        layout.addWidget(QLabel("特征缓存位置"))

        cache_row = QHBoxLayout()
        cache_row.setSpacing(8)

        self.cache_edit = QLineEdit(self._current_cache_dir)
        self.cache_edit.setReadOnly(True)
        cache_row.addWidget(self.cache_edit, 1)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setObjectName("secondary")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self._browse_cache_dir)
        cache_row.addWidget(self.browse_btn)

        layout.addLayout(cache_row)

        # Cache size + actions
        info_row = QHBoxLayout()
        info_row.setSpacing(12)

        self.size_label = QLabel("缓存大小：--")
        self.size_label.setObjectName("labelMuted")
        info_row.addWidget(self.size_label)

        info_row.addStretch()

        self.reset_btn = QPushButton("恢复默认")
        self.reset_btn.setObjectName("secondary")
        self.reset_btn.clicked.connect(self._reset_to_default)
        info_row.addWidget(self.reset_btn)

        self.clear_btn = QPushButton("清除缓存")
        self.clear_btn.setObjectName("danger")
        self.clear_btn.clicked.connect(self._clear_cache)
        info_row.addWidget(self.clear_btn)

        layout.addLayout(info_row)

        hint = QLabel("更改缓存位置不会迁移现有缓存文件。")
        hint.setObjectName("labelMuted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch()

        # Dialog buttons
        button_row = QHBoxLayout()
        button_row.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("保存")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        button_row.addWidget(self.save_btn)

        layout.addLayout(button_row)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        set_dark_title_bar(int(self.winId()))

    def _refresh_size_label(self) -> None:
        """Update the cache size display for the currently selected directory."""
        from services.feature_cache_service import get_cache_size_bytes

        try:
            size = get_cache_size_bytes(self._selected_cache_dir)
            self.size_label.setText(f"缓存大小：{_format_size(size)}")
        except Exception:
            self.size_label.setText("缓存大小：--")

    def _browse_cache_dir(self) -> None:
        """Open a directory picker for the cache location."""
        start_dir = self._selected_cache_dir
        if not Path(start_dir).exists():
            start_dir = str(get_default_cache_dir())

        chosen = QFileDialog.getExistingDirectory(
            self,
            "选择缓存目录",
            start_dir,
        )
        if not chosen:
            return

        p = Path(chosen)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法使用所选目录：\n{e}")
            return

        if not p.is_dir():
            QMessageBox.critical(self, "错误", "所选路径不是有效目录。")
            return

        self._selected_cache_dir = str(p)
        self.cache_edit.setText(self._selected_cache_dir)

    def _reset_to_default(self) -> None:
        """Reset the cache directory to the platform default."""
        self._selected_cache_dir = self._default_cache_dir
        self.cache_edit.setText(self._selected_cache_dir)

    def _clear_cache(self) -> None:
        """Clear the current cache after confirmation."""
        reply = QMessageBox.question(
            self,
            "确认清除",
            "确定要清除所有缓存的特征文件吗？\n已扫描过的图片下次需要重新提取特征。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            removed = clear_cache(self._selected_cache_dir)
            QMessageBox.information(self, "清除完成", f"已删除 {removed} 个缓存文件。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"清除缓存失败：\n{e}")
        finally:
            self._refresh_size_label()

    def _save(self) -> None:
        """Accept the dialog and persist the chosen cache directory."""
        try:
            from services.feature_cache_service import set_cache_dir

            set_cache_dir(self._selected_cache_dir)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法设置缓存目录：\n{e}")
            return
        self.accept()

    def selected_cache_dir(self) -> str:
        """Return the cache directory chosen by the user."""
        return self._selected_cache_dir
