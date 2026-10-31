"""Application branding assets that remain optional in source and frozen builds."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon


def application_icon_path() -> Path | None:
    """Find the supplied application icon in source and PyInstaller layouts."""
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                bundle_dir / "assets" / "app_icon.png",
                bundle_dir / "_internal" / "assets" / "app_icon.png",
            ]
        )
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "assets" / "app_icon.png")

    source_root = Path(__file__).resolve().parents[2]
    candidates.append(source_root / "assets" / "app_icon.png")

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def application_icon() -> QIcon:
    """Return the client icon, or an empty icon if the optional asset is absent."""
    path = application_icon_path()
    return QIcon(str(path)) if path else QIcon()
