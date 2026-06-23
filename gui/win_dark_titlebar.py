"""Enable dark title bars on Windows via DWM.

Qt stylesheets cannot paint the native window frame; on Windows 10/11 the
DWM attribute DWMWA_USE_IMMERSIVE_DARK_MODE tells the OS to render a dark
title bar and border. This module exposes helper functions that are safe to
call on any platform (they no-op on non-Windows).
"""

from __future__ import annotations

import sys


def _is_windows() -> bool:
    return sys.platform == "win32"


def _color_to_colorref(hex_color: str) -> int:
    """Convert '#RRGGBB' to Windows COLORREF 0x00BBGGRR."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return 0
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (b << 16) | (g << 8) | r


def set_dark_title_bar(hwnd: int, dark: bool = True) -> None:
    """Apply DWM dark mode to the native window with handle *hwnd*.

    No-op on non-Windows platforms or if DWM does not support the attribute.
    """
    if not _is_windows():
        return

    try:
        import ctypes
        from ctypes import wintypes

        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dwm = ctypes.windll.dwmapi
        value = ctypes.c_int(1 if dark else 0)
        dwm.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            ctypes.c_uint(DWMWA_USE_IMMERSIVE_DARK_MODE),
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    except Exception:
        pass


def set_caption_color(hwnd: int, color: str | int | None = None) -> None:
    """Set a custom caption (title bar) color.

    *color* can be a hex string like '#0a0f1a' or a Windows COLORREF integer.
    This attribute is only supported on Windows 11 (build 22000+); failures
    on older Windows are silently ignored.
    """
    if not _is_windows():
        return
    if color is None:
        return

    if isinstance(color, str):
        color_ref = _color_to_colorref(color)
    else:
        color_ref = int(color)

    try:
        import ctypes
        from ctypes import wintypes

        DWMWA_CAPTION_COLOR = 35
        dwm = ctypes.windll.dwmapi
        value = ctypes.c_int(color_ref)
        dwm.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            ctypes.c_uint(DWMWA_CAPTION_COLOR),
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    except Exception:
        pass
