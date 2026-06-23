#!/usr/bin/env python3
"""PicSimProcess Desktop Application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from src.utils import configure_cpu_limits

# Cap BLAS/OpenMP threads before any numeric libraries are imported.
configure_cpu_limits()

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.styles import DARK_STYLE


def _resolve_icon_path() -> Path | None:
    """Locate src/Icon/Icon.png in dev and PyInstaller bundle layouts."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "src" / "Icon" / "Icon.png")
        candidates.append(exe_dir / "_internal" / "src" / "Icon" / "Icon.png")
    else:
        candidates.append(Path(__file__).resolve().parent / "src" / "Icon" / "Icon.png")

    for path in candidates:
        if path.exists():
            return path
    return None


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)

    icon_path = _resolve_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
