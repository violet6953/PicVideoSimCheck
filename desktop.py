#!/usr/bin/env python3
"""PicSimProcess Desktop Application entry point."""

from __future__ import annotations

import sys

from src.utils import configure_cpu_limits

# Cap BLAS/OpenMP threads before any numeric libraries are imported.
configure_cpu_limits()

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.styles import DARK_STYLE


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
