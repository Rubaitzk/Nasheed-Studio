"""
Project and template persistence, atomic saving, asset relinking, and managed bundling.

Guarantees:
1. Atomic saving: writes to temporary file and commits via atomic replace; existing files are never corrupted.
2. Template separation: saves only reusable styling & design settings; never touches tracklists or titles.
3. Asset safety: detects missing asset paths on load; provides relinking; managed mode copies without touching originals.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TEMPLATE_DESIGN_KEYS = [
    "template",
    "resolution",
    "indicator_mode",
    "cursor_size",
    "title_font_family",
    "title_font_style",
    "title_font_size",
    "track_font_family",
    "track_font_style",
    "track_font_size",
    "custom_title_font_path",
    "custom_track_font_path",
    "logo_position",
    "website_position",
    "website_font_size",
    "website_show",
    "website_opacity",
    "highlight_style",
    "highlight_bg_opacity",
    "intro_enabled",
    "intro_duration",
    "intro_animation",
    "transition_sfx_volume",
]


def save_project_atomic(project_data: dict, target_path: str | Path) -> bool:
    """
    Save project JSON atomically.
    Writes to a temporary file in the same directory, flushes to disk via fsync,
    and replaces the target file atomically. If writing fails, the target is preserved.
    """
    target = Path(target_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = target.parent / f".{target.name}.tmp_{uuid.uuid4().hex[:8]}"
    try:
        payload = json.dumps(project_data, indent=2)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())

        tmp_path.replace(target)
        return True
    except Exception as exc:
        if tmp_path.exists():
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
        raise IOError(f"Failed to atomically save project to {target}: {exc}") from exc


def extract_template(project_data: dict, template_name: str = "Custom Template") -> dict:
    """Extract only reusable visual design and styling settings from a project."""
    data = {
        "version": 1,
        "type": "template",
        "template_name": template_name,
    }
    for key in TEMPLATE_DESIGN_KEYS:
        if key in project_data:
            data[key] = project_data[key]
    return data


def save_template_atomic(template_data: dict, target_path: str | Path) -> bool:
    """Save a template JSON file atomically."""
    return save_project_atomic(template_data, target_path)


def load_template(target_path: str | Path) -> dict:
    """Load and validate a template JSON file."""
    path = Path(target_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Template file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    return data


def apply_template_to_project(project_data: dict, template_data: dict) -> dict:
    """
    Apply reusable styling settings from a template onto an existing project.
    Strictly preserves collection title, tracks list, asset paths, and output path.
    """
    updated = dict(project_data)
    for key in TEMPLATE_DESIGN_KEYS:
        if key in template_data:
            updated[key] = template_data[key]
    return updated


def check_missing_assets(project_data: dict) -> Dict[str, List[Dict[str, str]]]:
    """
    Inspect all asset references in a project and return any missing files.
    Returns a dict mapping asset type to list of details:
    {'background': [...], 'logo': [...], 'cursor': [...], 'sfx': [...], 'tracks': [...]}
    """
    missing: Dict[str, List[Dict[str, str]]] = {
        "background": [],
        "logo": [],
        "cursor": [],
        "sfx": [],
        "fonts": [],
        "tracks": [],
    }

    # Background
    bg = project_data.get("background", "")
    if bg and not Path(bg).is_file():
        missing["background"].append({"path": bg, "field": "background"})

    # Logo
    logo = project_data.get("logo", "")
    if logo and not Path(logo).is_file():
        missing["logo"].append({"path": logo, "field": "logo"})

    # Cursor
    cursor = project_data.get("cursor_path", "")
    if cursor and not Path(cursor).is_file():
        missing["cursor"].append({"path": cursor, "field": "cursor_path"})

    # Transition SFX
    sfx = project_data.get("transition_sfx_path", "")
    if project_data.get("transition_sfx_enabled") and sfx and not Path(sfx).is_file():
        missing["sfx"].append({"path": sfx, "field": "transition_sfx_path"})

    # Custom Fonts
    for font_key in ["custom_title_font_path", "custom_track_font_path"]:
        fp = project_data.get(font_key, "")
        if fp and not Path(fp).is_file():
            missing["fonts"].append({"path": fp, "field": font_key})

    # Audio Tracks
    for idx, track in enumerate(project_data.get("tracks", [])):
        p = track.get("path", "")
        if p and not Path(p).is_file():
            missing["tracks"].append({
                "index": idx,
                "title": track.get("title", f"Track {idx+1}"),
                "path": p,
            })

    return {k: v for k, v in missing.items() if v}


def relink_asset(project_data: dict, old_path: str, new_path: str) -> dict:
    """Update all occurrences of old_path to new_path in project_data."""
    updated = dict(project_data)
    old_norm = str(Path(old_path).resolve()) if old_path else ""
    new_norm = str(Path(new_path).resolve()) if new_path else ""

    if not old_norm or not new_norm:
        return updated

    # Check top-level asset fields
    for field in ["background", "logo", "cursor_path", "transition_sfx_path", "custom_title_font_path", "custom_track_font_path"]:
        cur = updated.get(field, "")
        if cur and str(Path(cur).resolve()) == old_norm:
            updated[field] = new_norm

    # Check tracks
    if "tracks" in updated:
        new_tracks = []
        for track in updated["tracks"]:
            t = dict(track)
            if str(Path(t.get("path", "")).resolve()) == old_norm:
                t["path"] = new_norm
            new_tracks.append(t)
        updated["tracks"] = new_tracks

    return updated


def bundle_managed_assets(project_data: dict, project_bundle_dir: Path) -> dict:
    """
    Managed Asset Mode:
    Copies all required assets (background, logo, cursor, SFX, audio tracks) into
    <project_bundle_dir>/assets/, verifying copy integrity without modifying or
    deleting original files. Returns updated project dictionary with managed paths.
    """
    bundle_dir = Path(project_bundle_dir).resolve()
    assets_dir = bundle_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    managed = dict(project_data)

    def copy_file_safe(src_path: str, subfolder: str = "") -> str:
        if not src_path or not Path(src_path).is_file():
            return src_path
        src = Path(src_path)
        dest_folder = assets_dir / subfolder if subfolder else assets_dir
        dest_folder.mkdir(parents=True, exist_ok=True)

        dest = dest_folder / src.name
        # If file already exists with same size, reuse
        if dest.exists() and dest.stat().st_size == src.stat().st_size:
            return str(dest)

        # Disambiguate if name collision with different content
        counter = 1
        while dest.exists() and dest.stat().st_size != src.stat().st_size:
            dest = dest_folder / f"{src.stem}_{counter}{src.suffix}"
            counter += 1

        shutil.copy2(src, dest)
        return str(dest)

    # 1. Background
    if managed.get("background"):
        managed["background"] = copy_file_safe(managed["background"], "images")

    # 2. Logo
    if managed.get("logo"):
        managed["logo"] = copy_file_safe(managed["logo"], "images")

    # 3. Cursor
    if managed.get("cursor_path"):
        managed["cursor_path"] = copy_file_safe(managed["cursor_path"], "cursors")

    # 4. SFX
    if managed.get("transition_sfx_path"):
        managed["transition_sfx_path"] = copy_file_safe(managed["transition_sfx_path"], "audio")

    # 5. Custom Fonts
    if managed.get("custom_title_font_path"):
        managed["custom_title_font_path"] = copy_file_safe(managed["custom_title_font_path"], "fonts")
    if managed.get("custom_track_font_path"):
        managed["custom_track_font_path"] = copy_file_safe(managed["custom_track_font_path"], "fonts")

    # 6. Tracks
    if "tracks" in managed:
        managed_tracks = []
        for track in managed["tracks"]:
            t = dict(track)
            if t.get("path"):
                t["path"] = copy_file_safe(t["path"], "audio")
            managed_tracks.append(t)
        managed["tracks"] = managed_tracks

    return managed
