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

from .workspace_service import is_temp_or_obsolete_path, get_templates_dir

TEMPLATE_DESIGN_KEYS = [
    # Built-in layout preset & output resolution
    "template",
    "resolution",
    "resource_profile",
    "export_quality",
    "target_bitrate",

    # Playlist layout, positioning, dimensions & density
    "playlist_position",
    "playlist_columns",
    "playlist_row_spacing",
    "playlist_col_spacing",
    "playlist_width_ratio",
    "playlist_x_offset",
    "playlist_y_offset",
    "track_wrap_text",
    "track_max_chars",

    # Playlist panel backing & styling
    "playlist_bg_opacity",
    "playlist_bg_color",
    "playlist_bg_radius",

    # Collection title styling & positioning
    "title_font_family",
    "title_font_style",
    "title_font_size",
    "custom_title_font_path",
    "title_position",
    "title_show",
    "title_margin",
    "title_color",
    "title_outline_color",
    "title_outline_width",
    "title_shadow",
    "title_playlist_spacing",
    "title_opacity",
    "title_softening",

    # Track title styling & appearance
    "track_font_family",
    "track_font_style",
    "track_font_size",
    "custom_track_font_path",
    "track_color",
    "track_outline_color",
    "track_outline_width",
    "track_shadow",
    "active_track_color",
    "track_opacity",
    "track_softening",
    "text_softening",

    # Cursor & active-track indicator styling
    "indicator_mode",
    "cursor_size",
    "cursor_path",
    "highlight_style",
    "highlight_color",
    "highlight_bg_opacity",
    "highlight_outline_width",
    "highlight_corner_radius",
    "highlight_target",
    "highlight_padding_x",
    "highlight_padding_y",
    "highlight_opacity",
    "cursor_y_offset",
    "highlight_y_offset",

    # Logo placement & cleanup
    "logo_position",
    "logo_scale",
    "logo_cleanup_mode",

    # Website watermark placement & styling
    "website_position",
    "website_font_size",
    "website_show",
    "website_opacity",
    "website_font_family",
    "website_font_style",
    "website_color",

    # Intro presentation card & animations
    "intro_enabled",
    "intro_duration",
    "intro_animation",

    # Video background behavior
    "background_type",
    "video_fit_mode",
    "video_start_time",
    "video_loop",
    "video_mute_audio",

    # Audio transition sound effect
    "transition_sfx_enabled",
    "transition_sfx_volume",
    "transition_sfx_path",
]

PROTECTED_PROJECT_CONTENT_KEYS = {
    "collection_title",
    "tracks",
    "background",
    "logo",
    "output_path",
    "website_text",
}


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
    """Extract only reusable visual design, layout, and styling settings from a project."""
    data = {
        "version": 1,
        "type": "template",
        "template_name": template_name,
    }
    for key in TEMPLATE_DESIGN_KEYS:
        if key in project_data:
            val = project_data[key]
            # Custom cursor persistence validation
            if key == "cursor_path":
                if val and Path(str(val)).is_file():
                    src_p = Path(str(val)).resolve()
                    # If cursor is in a temporary directory, copy it to templates assets dir for durability
                    if is_temp_or_obsolete_path(src_p):
                        try:
                            assets_dir = get_templates_dir() / "assets"
                            assets_dir.mkdir(parents=True, exist_ok=True)
                            dest_p = assets_dir / f"cursor_{src_p.name}"
                            shutil.copy2(src_p, dest_p)
                            data[key] = str(dest_p)
                        except Exception:
                            data[key] = ""
                    else:
                        data[key] = str(src_p)
                else:
                    data[key] = ""
            elif key == "transition_sfx_path":
                if val and Path(str(val)).is_file() and not is_temp_or_obsolete_path(val):
                    data[key] = str(Path(str(val)).resolve())
                else:
                    data[key] = ""
            else:
                data[key] = val

    # Optional starter background & logo if present and durable
    if "background" in project_data and project_data["background"]:
        bg_p = Path(project_data["background"])
        if bg_p.is_file() and not is_temp_or_obsolete_path(bg_p):
            data["background"] = str(bg_p.resolve())
    if "logo" in project_data and project_data["logo"]:
        logo_p = Path(project_data["logo"])
        if logo_p.is_file() and not is_temp_or_obsolete_path(logo_p):
            data["logo"] = str(logo_p.resolve())

    return data


def save_template_atomic(template_data: dict, target_path: str | Path) -> bool:
    """Save a template JSON file atomically."""
    return save_project_atomic(template_data, target_path)


def load_template(target_path: str | Path) -> dict:
    """Load and validate a template JSON file with strict error handling for malformed files."""
    path = Path(target_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Template file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Template path is not a file: {path}")

    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed template file (invalid JSON in {path.name}): {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Could not read template file ({path.name}): {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Invalid template format: root must be a JSON object")

    return data


def apply_template_to_project(project_data: dict, template_data: dict) -> dict:
    """
    Apply reusable styling settings from a template onto an existing project.
    Strictly preserves collection title, tracks list/order, asset paths, and output path.
    Adopts template starter background or logo only if receiving project has none.
    """
    updated = dict(project_data)
    for key in TEMPLATE_DESIGN_KEYS:
        if key in template_data and key not in PROTECTED_PROJECT_CONTENT_KEYS:
            updated[key] = template_data[key]

    # Adopt starter background / logo only if receiving project does not have one
    if not updated.get("background") and template_data.get("background"):
        bg_candidate = template_data["background"]
        if Path(bg_candidate).is_file():
            updated["background"] = bg_candidate
    if not updated.get("logo") and template_data.get("logo"):
        logo_candidate = template_data["logo"]
        if Path(logo_candidate).is_file():
            updated["logo"] = logo_candidate

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


def discover_user_templates(project_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Discover all valid reusable JSON templates in user_templates/ (and fallback templates/).
    Returns a sorted list of template summaries with metadata.
    """
    root = project_root or Path(__file__).resolve().parent.parent.parent
    search_dirs = [root / "user_templates", root / "templates"]
    discovered: List[Dict[str, Any]] = []
    seen_paths = set()

    for sdir in search_dirs:
        if not sdir.is_dir():
            continue
        for p in sorted(sdir.glob("*.json")):
            resolved = p.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                name = data.get("template_name") or p.stem.replace("_", " ").title()
                desc = data.get("description", "")
                cat = "User Template" if sdir.name == "user_templates" else "Preset"
                discovered.append({
                    "path": str(resolved),
                    "filename": p.name,
                    "name": name,
                    "description": desc,
                    "category": cat,
                    "data": data,
                })
            except Exception:
                continue

    return discovered
