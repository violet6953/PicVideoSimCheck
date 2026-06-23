"""Icon helpers for PicSimProcess build scripts.

Provides a single helper to generate the Windows ICO file used by
PyInstaller and Inno Setup from the canonical PNG icon stored under
src/Icon/Icon.png.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

# Canonical icon source (project root relative).
ICON_SOURCE = Path("src") / "Icon" / "Icon.png"

# Where PyInstaller / Inno Setup expect the Windows ICO file.
ICON_BUILD = Path("build") / "icon.ico"

# Standard Windows icon sizes produced from the source PNG.
ICON_SIZES = [
    (16, 16),
    (32, 32),
    (48, 48),
    (256, 256),
]


def ensure_build_icon(project_root: Path | str | None = None) -> Path:
    """Regenerate build/icon.ico from src/Icon/Icon.png.

    Args:
        project_root: Root of the project. Defaults to the current working
            directory.

    Returns:
        Path to the generated ICO file.

    Raises:
        FileNotFoundError: If the source PNG icon cannot be found.
    """
    root = Path(project_root) if project_root else Path.cwd()
    source = root / ICON_SOURCE
    output = root / ICON_BUILD

    if not source.exists():
        raise FileNotFoundError(f"Icon source not found: {source}")

    output.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as img:
        img = img.convert("RGBA")
        img.save(output, format="ICO", sizes=ICON_SIZES)

    return output
