"""
Font discovery and resolution service for Windows and cross-platform fallback.

Discovers installed system and user fonts via the Windows Registry and filesystem,
maps font families and styles (Regular, Bold, Italic, Bold Italic) to concrete
TTF/OTF font file paths for Pillow ImageFont, and provides graceful fallbacks.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_FONT_REGISTRY_CACHE: Optional[Dict[str, Dict[str, str]]] = None
_SYSTEM_FAMILIES_CACHE: Optional[List[str]] = None

STYLE_VARIANTS = {
    "Regular": ["regular", "normal", "book", "roman"],
    "Bold": ["bold", "black", "heavy", "semibold", "demibold", "extrabold"],
    "Italic": ["italic", "oblique"],
    "Bold Italic": ["bold italic", "bolditalic", "bold oblique", "black italic"],
}

PREFERRED_DEFAULTS = ["Segoe UI", "Arial", "Calibri", "Verdana", "Tahoma"]


def _clean_descriptor(raw_name: str) -> Tuple[str, str]:
    """Parse a registry font descriptor (e.g., 'Segoe UI Bold (TrueType)') into family and style."""
    cleaned = re.sub(r"\s*\((TrueType|OpenType)\)$", "", raw_name, flags=re.IGNORECASE).strip()
    
    # Check for compound styles first
    lower = cleaned.lower()
    if "bold italic" in lower or "bolditalic" in lower:
        family = re.sub(r"\s+bold\s*italic\b", "", cleaned, flags=re.IGNORECASE).strip()
        return family, "Bold Italic"
    if "bold" in lower:
        family = re.sub(r"\s+bold\b", "", cleaned, flags=re.IGNORECASE).strip()
        return family, "Bold"
    if "italic" in lower or "oblique" in lower:
        family = re.sub(r"\s+(italic|oblique)\b", "", cleaned, flags=re.IGNORECASE).strip()
        return family, "Italic"

    return cleaned, "Regular"


def _build_font_cache() -> Dict[str, Dict[str, str]]:
    """Scan Windows registry and Fonts directories to build a family -> style -> file path mapping."""
    cache: Dict[str, Dict[str, str]] = {}
    win_dir = Path(os.environ.get("WINDIR", "C:\\Windows"))
    sys_fonts_dir = win_dir / "Fonts"

    def register_font(family_name: str, style_name: str, full_path: Path) -> None:
        if not full_path.is_file():
            return
        fam_key = family_name.strip()
        if not fam_key or fam_key.startswith("@"):
            return
        if fam_key not in cache:
            cache[fam_key] = {}
        # Only set if not already set or if replacing with an exact style match
        if style_name not in cache[fam_key]:
            cache[fam_key][style_name] = str(full_path.resolve())

    # 1. Windows Registry scan (if on Windows)
    if sys.platform == "win32":
        try:
            import winreg

            roots = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts", sys_fonts_dir),
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\Fonts", Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"),
            ]

            for root_key, subkey, base_dir in roots:
                try:
                    with winreg.OpenKey(root_key, subkey) as key:
                        count = winreg.QueryInfoKey(key)[1]
                        for i in range(count):
                            try:
                                name, file_val, _ = winreg.EnumValue(key, i)
                                family, style = _clean_descriptor(name)
                                file_path = Path(file_val)
                                if not file_path.is_absolute():
                                    file_path = base_dir / file_val
                                register_font(family, style, file_path)
                            except Exception:
                                continue
                except Exception:
                    continue
        except Exception:
            pass

    # 2. Filesystem scan fallback for standard Windows fonts directory
    if sys_fonts_dir.is_dir():
        for ext in ("*.ttf", "*.otf"):
            for font_file in sys_fonts_dir.glob(ext):
                stem = font_file.stem
                fam, style = _clean_descriptor(stem)
                register_font(fam, style, font_file)

    # 3. Linux / macOS fallback search paths
    fallback_dirs = [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
        Path.home() / ".local/share/fonts",
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
    ]
    for d in fallback_dirs:
        if d.is_dir():
            for p in d.rglob("*.ttf"):
                fam, style = _clean_descriptor(p.stem)
                register_font(fam, style, p)

    return cache


def refresh_fonts() -> None:
    """Clear and rebuild the font cache."""
    global _FONT_REGISTRY_CACHE, _SYSTEM_FAMILIES_CACHE
    _FONT_REGISTRY_CACHE = None
    _SYSTEM_FAMILIES_CACHE = None
    get_font_cache()


def get_font_cache() -> Dict[str, Dict[str, str]]:
    """Return the cached font mapping."""
    global _FONT_REGISTRY_CACHE
    if _FONT_REGISTRY_CACHE is None:
        _FONT_REGISTRY_CACHE = _build_font_cache()
    return _FONT_REGISTRY_CACHE


def list_system_font_families() -> List[str]:
    """Return a sorted list of unique font family names available on the system."""
    global _SYSTEM_FAMILIES_CACHE
    if _SYSTEM_FAMILIES_CACHE is not None:
        return _SYSTEM_FAMILIES_CACHE

    cache = get_font_cache()
    families = set(cache.keys())

    # Try Qt QFontDatabase if QGuiApplication is running
    try:
        from PySide6.QtGui import QFontDatabase, QGuiApplication
        if QGuiApplication.instance():
            qt_families = [f for f in QFontDatabase.families() if not f.startswith("@")]
            families.update(qt_families)
    except Exception:
        pass

    # Order preferred families first, then alphabetical
    preferred = [f for f in PREFERRED_DEFAULTS if f in families]
    others = sorted([f for f in families if f not in preferred], key=lambda s: s.lower())
    _SYSTEM_FAMILIES_CACHE = preferred + others
    return _SYSTEM_FAMILIES_CACHE


def list_family_styles(family: str) -> List[str]:
    """Return available styles for a given family, defaulting to Regular, Bold, Italic, Bold Italic."""
    cache = get_font_cache()
    styles = ["Regular", "Bold", "Italic", "Bold Italic"]
    if family in cache:
        available = list(cache[family].keys())
        # Keep standard order, plus any non-standard styles
        result = [s for s in styles if s in available]
        extras = [s for s in available if s not in styles]
        if result:
            return result + extras
    return styles


def resolve_font_path(family: str = "Segoe UI", style: str = "Regular") -> str:
    """
    Resolve a font family and style to a concrete .ttf or .otf file path.
    Gracefully falls back to preferred system fonts if the specific family or style is unavailable.
    """
    cache = get_font_cache()

    # Normalize style
    norm_style = style.strip()
    if norm_style.lower() in ("normal", "book", "roman"):
        norm_style = "Regular"
    elif norm_style.lower() in ("semibold", "black", "heavy", "demibold"):
        norm_style = "Bold"

    # 1. Exact family match
    if family in cache:
        family_styles = cache[family]
        if norm_style in family_styles:
            return family_styles[norm_style]
        # Match Bold with Bold Italic or Regular
        if norm_style == "Bold":
            for fallback_style in ["Bold", "Regular", "Italic"]:
                if fallback_style in family_styles:
                    return family_styles[fallback_style]
        # Fallback to any available style in family
        if family_styles:
            return next(iter(family_styles.values()))

    # 2. Case-insensitive family match
    lower_target = family.lower().strip()
    for fam, family_styles in cache.items():
        if fam.lower() == lower_target:
            if norm_style in family_styles:
                return family_styles[norm_style]
            if "Regular" in family_styles:
                return family_styles["Regular"]
            if family_styles:
                return next(iter(family_styles.values()))

    # 3. Preferred system fallbacks
    for fallback_family in PREFERRED_DEFAULTS:
        if fallback_family in cache:
            fam_styles = cache[fallback_family]
            if norm_style in fam_styles:
                return fam_styles[norm_style]
            if "Regular" in fam_styles:
                return fam_styles["Regular"]
            if fam_styles:
                return next(iter(fam_styles.values()))

    # 4. Standard hardcoded paths
    win_dir = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
    hardcoded = [
        win_dir / ("segoeui.ttf" if norm_style != "Bold" else "segoeuib.ttf"),
        win_dir / ("arial.ttf" if norm_style != "Bold" else "arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for p in hardcoded:
        if p.is_file():
            return str(p)

    return ""
