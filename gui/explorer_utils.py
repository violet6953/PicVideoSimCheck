"""Windows Explorer utility helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path


def open_folder_and_select(target_path: str) -> None:
    """Open Windows Explorer at the given file and set Extra Large Icons view."""
    target = Path(target_path).resolve()
    if not target.exists():
        return

    # Open explorer with file highlighted
    subprocess.Popen(["explorer", "/select,", str(target)], shell=True)

    # Set Extra Large Icons in background thread
    import threading
    thread = threading.Thread(target=_set_explorer_extra_large_icons, args=(str(target),))
    thread.daemon = True
    thread.start()


def _set_explorer_extra_large_icons(target_path: str) -> None:
    """Find the explorer window for target_path and set Extra Large Icons view.

    Uses ctypes to enumerate windows, find the matching CabinetWClass explorer
    window, bring it to foreground, and send Ctrl+Shift+1 shortcut.
    """
    import ctypes
    import time

    target_dir = str(Path(target_path).parent)
    dir_name = Path(target_dir).name

    time.sleep(0.8)  # Wait for explorer to open

    user32 = ctypes.windll.user32
    VK_CONTROL = 0x11
    VK_SHIFT = 0x10
    VK_1 = 0x31
    KEYEVENTF_KEYUP = 0x0002

    windows: list[tuple[int, str]] = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def enum_proc(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value != "CabinetWClass":
            return True

        text_len = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if text_len > 0:
            text_buf = ctypes.create_unicode_buffer(text_len + 1)
            user32.GetWindowTextW(hwnd, text_buf, text_len + 1)
            title = text_buf.value

        windows.append((hwnd, title))
        return True

    callback = EnumWindowsProc(enum_proc)
    user32.EnumWindows(callback, 0)

    target_hwnd = None
    for hwnd, title in windows:
        if dir_name in title:
            target_hwnd = hwnd
            break

    if target_hwnd is None and windows:
        target_hwnd = windows[0][0]

    if target_hwnd is None:
        return

    user32.SetForegroundWindow(target_hwnd)
    time.sleep(0.15)

    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_SHIFT, 0, 0, 0)
    user32.keybd_event(VK_1, 0, 0, 0)
    user32.keybd_event(VK_1, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
