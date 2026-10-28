"""Creates a clean base composition and transparent per-track cursor/highlight overlays."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
from typing import Optional, Tuple, Union, List, Dict, Any, Callable
import functools
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageChops, ImageFilter

from src.services.font_service import resolve_font_path, get_normalized_font_size
from src.services.media_probe import is_video_file, extract_video_frame

INDICATOR_MODES = ["both", "cursor_only", "highlight_only", "neither"]
CORNER_POSITIONS = ["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right"]
WEBSITE_POSITIONS = ["Top-Right", "Top-Left", "Bottom-Left", "Bottom-Right", "Bottom-Center", "Top-Center"]
PLAYLIST_POSITIONS = ["Left", "Center", "Right"]
TITLE_POSITIONS = ["Top-Center", "Above Playlist", "Top-Left", "Hidden"]
HIGHLIGHT_STYLES = ["Pill", "Accent Bar", "Outline", "Underline"]
LOGO_CLEANUP_MODES = ["none", "auto", "remove_white", "remove_checkerboard"]


def _hex_to_rgb(val: Union[str, tuple, list], default: tuple[int, int, int] = (242, 243, 231)) -> tuple[int, int, int]:
    """Convert hex string (#RRGGBB) or tuple/list to RGB integer tuple."""
    if isinstance(val, (tuple, list)) and len(val) >= 3:
        return (int(val[0]), int(val[1]), int(val[2]))
    if isinstance(val, str) and val.startswith("#"):
        v = val.lstrip("#")
        if len(v) == 6:
            try:
                return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))
            except ValueError:
                pass
    return default


def _draw_text_with_outline_and_shadow(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple,
    stroke_width: int = 0,
    stroke_fill: tuple = (0, 0, 0, 120),
    shadow: bool = False,
    shadow_offset: tuple[int, int] = (2, 2),
    shadow_fill: tuple = (0, 0, 0, 140),
) -> None:
    """Draw text with optional soft drop-shadow and restrained outline for cinematic legibility."""
    x, y = int(round(xy[0])), int(round(xy[1]))
    font_sz = getattr(font, "size", 20)
    line_spacing = max(2, int(font_sz * 0.25))
    if shadow:
        sx, sy = int(round(shadow_offset[0])), int(round(shadow_offset[1]))
        s_alpha = shadow_fill[3] if len(shadow_fill) > 3 else 140
        s_rgb = shadow_fill[:3]
        # Soft two-stage shadow falloff eliminates harsh jagged step-edges while ensuring background separation
        if sx > 1 or sy > 1:
            draw.text((x + sx, y + sy), text, font=font, fill=(*s_rgb, int(s_alpha * 0.40)), spacing=line_spacing)
        draw.text((x + max(1, sx // 2), y + max(1, sy // 2)), text, font=font, fill=(*s_rgb, int(s_alpha * 0.70)), spacing=line_spacing)
    if stroke_width > 0:
        draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill, spacing=line_spacing)
    else:
        draw.text((x, y), text, font=font, fill=fill, spacing=line_spacing)


def clean_logo_image(img: Image.Image, mode: str = "auto") -> Image.Image:
    """
    Remove solid white or checkerboard backgrounds from logo and cursor images while preserving inner graphics.
    Combines edge-connected flood-fill mask with the image's original alpha to preserve genuine transparency
    and antialiased contours.
    """
    mode = str(mode or "auto").lower()
    if mode == "none":
        return img.convert("RGBA")

    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()

    # Check corners for transparency or background color
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    if any(c[3] < 30 for c in corners) and mode == "auto":
        # Already has transparent corners in auto mode
        return rgba

    def is_white_bg(r: int, g: int, b: int, a: int = 255) -> bool:
        if a < 30:
            return False
        return r >= 230 and g >= 230 and b >= 230 and abs(r - g) <= 15 and abs(g - b) <= 15

    def is_checker_bg(r: int, g: int, b: int, a: int = 255) -> bool:
        if a < 30:
            return False
        is_grey = (175 <= r <= 225 and 175 <= g <= 225 and 175 <= b <= 225 and abs(r - g) <= 10 and abs(g - b) <= 10)
        is_white = (r >= 230 and g >= 230 and b >= 230 and abs(r - g) <= 15 and abs(g - b) <= 15)
        return is_white or is_grey

    is_bg_fn = is_white_bg
    if mode == "remove_checkerboard":
        is_bg_fn = is_checker_bg
    elif mode == "remove_white":
        is_bg_fn = is_white_bg
    elif mode == "auto":
        # Detect if corners alternate as checkerboard or solid white
        grey_corners = sum(1 for r, g, b, a in corners if 175 <= r <= 225 and abs(r - g) <= 10 and a >= 30)
        white_corners = sum(1 for r, g, b, a in corners if is_white_bg(r, g, b, a))
        if grey_corners >= 1 and (grey_corners + white_corners == 4):
            is_bg_fn = is_checker_bg
        elif white_corners >= 3:
            is_bg_fn = is_white_bg
        else:
            return rgba

    mask = Image.new("L", (w, h), 255)
    m_px = mask.load()

    q = deque()
    visited = set()

    for x in range(w):
        for y in (0, h - 1):
            r, g, b, a = px[x, y]
            if is_bg_fn(r, g, b, a) and (x, y) not in visited:
                q.append((x, y))
                visited.add((x, y))

    for y in range(h):
        for x in (0, w - 1):
            if (x, y) not in visited:
                r, g, b, a = px[x, y]
                if is_bg_fn(r, g, b, a):
                    q.append((x, y))
                    visited.add((x, y))

    while q:
        cx, cy = q.popleft()
        m_px[cx, cy] = 0
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                r, g, b, a = px[nx, ny]
                if is_bg_fn(r, g, b, a):
                    visited.add((nx, ny))
                    q.append((nx, ny))

    # Combine cleanup mask with existing alpha channel to preserve real transparency and antialiased contours
    orig_alpha = rgba.split()[3]
    combined_alpha = ImageChops.multiply(orig_alpha, mask)
    rgba.putalpha(combined_alpha)
    return rgba


@functools.lru_cache(maxsize=512)
def _get_font(family: str = "Segoe UI", style: str = "Regular", size: int = 20) -> ImageFont.ImageFont:
    """Resolve and load a TTF/OTF font for Pillow, falling back to default if unavailable."""
    path = resolve_font_path(family, style)
    if path and Path(path).is_file():
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def clear_font_cache() -> None:
    """Clear cached ImageFont instances."""
    _get_font.cache_clear()


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


_BG_CACHE: dict[tuple, tuple[Image.Image, Image.Image]] = {}


def clear_background_cache() -> None:
    """Clear cached scaled backgrounds."""
    _BG_CACHE.clear()


def _get_prepared_background(
    background_path: Optional[str],
    width: int,
    height: int,
    video_start_time: float,
    video_fit_mode: str,
    wash_alpha: int,
    bg_is_video: bool,
) -> tuple[Image.Image, Image.Image]:
    """Return cached (base_bg, fg_base) or prepare and cache a scaled background."""
    mtime = 0.0
    if background_path and Path(background_path).is_file():
        try:
            mtime = Path(background_path).stat().st_mtime
        except OSError:
            mtime = 0.0

    cache_key = (
        str(background_path or ""),
        mtime,
        width,
        height,
        round(float(video_start_time or 0.0), 2),
        str(video_fit_mode or "").lower().strip(),
        wash_alpha,
        bg_is_video,
    )

    if cache_key in _BG_CACHE:
        cached_bg, cached_fg = _BG_CACHE[cache_key]
        return cached_bg.copy(), cached_fg.copy()

    if bg_is_video and background_path:
        try:
            raw_frame = extract_video_frame(background_path, video_start_time)
            fit = str(video_fit_mode or "fill/crop").lower().strip()
            if fit in ("fit with padding", "pad") or "pad" in fit:
                bg = ImageOps.pad(raw_frame, (width, height), color=(0, 0, 0)).convert("RGBA")
            elif fit == "stretch":
                bg = raw_frame.resize((width, height), Image.Resampling.LANCZOS).convert("RGBA")
            else:  # "fill/crop" (default)
                bg = _cover(raw_frame, (width, height)).convert("RGBA")
        except Exception:
            bg = Image.new("RGBA", (width, height), (23, 28, 26, 255))
    elif background_path and Path(background_path).is_file():
        try:
            bg = _cover(Image.open(background_path), (width, height)).convert("RGBA")
        except Exception:
            bg = Image.new("RGBA", (width, height), (23, 28, 26, 255))
    else:
        bg = Image.new("RGBA", (width, height), (23, 28, 26, 255))

    wash = Image.new("RGBA", bg.size, (0, 0, 0, wash_alpha))
    bg = Image.alpha_composite(bg, wash)
    fg = Image.new("RGBA", (width, height), (0, 0, 0, wash_alpha if bg_is_video else 0))

    if len(_BG_CACHE) >= 4:
        _BG_CACHE.pop(next(iter(_BG_CACHE)))
    _BG_CACHE[cache_key] = (bg.copy(), fg.copy())
    return bg, fg


def render_svg_to_image(svg_path: str, target_w: int, target_h: int) -> Image.Image:
    """Render an SVG file to an RGBA PIL Image using QtSvg."""
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QImage, QPainter, QColor
    from PySide6.QtCore import QRectF

    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        raise ValueError(f"Invalid or unreadable SVG cursor file: {svg_path}")

    qimg = QImage(target_w, target_h, QImage.Format.Format_ARGB32_Premultiplied)
    qimg.fill(QColor(0, 0, 0, 0))
    painter = QPainter(qimg)
    renderer.render(painter, QRectF(0, 0, target_w, target_h))
    painter.end()

    raw = qimg.bits().tobytes()
    return Image.frombuffer("RGBA", (target_w, target_h), raw, "raw", "BGRA", 0, 1).convert("RGBA")


def load_cursor_image(cursor_path: str, target_dim: int, mode: str = "auto") -> Image.Image:
    """Load, validate, clean, and resize a custom SVG or raster cursor into an RGBA PIL Image."""
    p = Path(cursor_path)
    if not p.is_file():
        raise FileNotFoundError(f"Cursor file not found: {cursor_path}")

    suffix = p.suffix.lower()
    if suffix == ".svg":
        return render_svg_to_image(str(p), target_dim, target_dim)

    supported_raster = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    if suffix in supported_raster:
        try:
            with Image.open(str(p)) as src:
                cleaned = clean_logo_image(src, mode=mode)
                return ImageOps.contain(cleaned, (target_dim, target_dim), method=Image.Resampling.LANCZOS)
        except Exception as exc:
            raise ValueError(f"Could not decode cursor image {cursor_path}: {exc}")

    raise ValueError(f"Unsupported cursor file format: {suffix}. Supported formats: SVG, PNG, JPG, WEBP, BMP.")


def _calculate_corner_position(
    corner: str,
    elem_w: int,
    elem_h: int,
    canvas_w: int,
    canvas_h: int,
    margin_x: int,
    margin_y: int,
) -> Tuple[int, int]:
    """Calculate (x, y) coordinates for an element in screen corners or centers."""
    pos = corner.strip().lower()
    if "top" in pos and "left" in pos:
        return margin_x, margin_y
    if "top" in pos and "center" in pos:
        return (canvas_w - elem_w) // 2, margin_y
    if "top" in pos and "right" in pos:
        return canvas_w - margin_x - elem_w, margin_y
    if "bottom" in pos and "left" in pos:
        return margin_x, canvas_h - margin_y - elem_h
    if "bottom" in pos and "center" in pos:
        return (canvas_w - elem_w) // 2, canvas_h - margin_y - elem_h
    if "bottom" in pos and "right" in pos:
        return canvas_w - margin_x - elem_w, canvas_h - margin_y - elem_h
    # Default to Bottom-Right
    return canvas_w - margin_x - elem_w, canvas_h - margin_y - elem_h


def _calculate_title_layout(
    collection_title: str,
    title_font_family: str,
    title_font_style: str,
    title_font_size: int,
    norm_title_pos: str,
    width: int,
    height: int,
    margin: int,
    res_scale: float,
    logo_placed: bool,
    logo_rect: Optional[Tuple[int, int, int, int]],
    usable_width: int,
    playlist_x: int,
    website_rect: Optional[Tuple[int, int, int, int]] = None,
) -> Tuple[List[str], ImageFont.ImageFont, int, List[Tuple[int, int]], int]:
    """
    Calculate multiline text wrapping, font scaling, line coordinates, and bounding limit
    for the collection title. Scales down smoothly if title is long to prevent truncation or overlap.
    """
    clean_title = collection_title.strip()
    norm_title_sz = get_normalized_font_size(title_font_family, title_font_style, title_font_size)
    base_font_sz = max(18, int(norm_title_sz * res_scale))

    if norm_title_pos == "Above Playlist":
        max_w = max(int(width * 0.70), usable_width)
        start_y = int(height * 0.07)
    elif norm_title_pos == "Top-Left":
        start_x = margin
        if logo_placed and logo_rect is not None and logo_rect[0] < int(width * 0.35) and logo_rect[1] < int(height * 0.35):
            start_x = max(start_x, logo_rect[2] + int(width * 0.02))
        if website_rect is not None and website_rect[0] < int(width * 0.35) and website_rect[1] < int(height * 0.35):
            start_x = max(start_x, website_rect[2] + int(width * 0.02))
        max_w = max(int(width * 0.30), int(width * 0.70) - start_x)
        start_y = int(height * 0.06)
    else:  # Top-Center
        max_w = int(width * 0.85)
        if logo_placed and logo_rect is not None:
            lx1, ly1, lx2, ly2 = logo_rect
            if ly1 < int(height * 0.22):
                # Avoid colliding horizontally with top logos
                clearance = min(lx1, width - lx2) * 2 - int(width * 0.04)
                if clearance > int(width * 0.30):
                    max_w = min(max_w, clearance)
        if website_rect is not None:
            wx1, wy1, wx2, wy2 = website_rect
            if wy1 < int(height * 0.22):
                # Avoid colliding horizontally with top watermarks
                clearance = min(wx1, width - wx2) * 2 - int(width * 0.04)
                if clearance > int(width * 0.30):
                    max_w = min(max_w, clearance)
        start_y = int(height * 0.06)

    curr_sz = base_font_sz
    title_font = _get_font(title_font_family, title_font_style, curr_sz)
    lines = [clean_title]

    # Test if single line fits within max_w
    tb = title_font.getbbox(clean_title)
    if (tb[2] - tb[0]) > max_w:
        words = clean_title.split()
        min_sz = max(14, int(base_font_sz * 0.70))
        while curr_sz >= min_sz:
            title_font = _get_font(title_font_family, title_font_style, curr_sz)
            lines_cand: List[str] = []
            cur_line: List[str] = []
            for w in words:
                cand_text = " ".join(cur_line + [w])
                bb = title_font.getbbox(cand_text)
                if (bb[2] - bb[0]) <= max_w or not cur_line:
                    cur_line.append(w)
                else:
                    lines_cand.append(" ".join(cur_line))
                    cur_line = [w]
            if cur_line:
                lines_cand.append(" ".join(cur_line))

            if len(lines_cand) <= 2 and all((title_font.getbbox(l)[2] - title_font.getbbox(l)[0]) <= max_w for l in lines_cand):
                lines = lines_cand
                break
            curr_sz -= 2
            lines = lines_cand

        # Enforce max 2 lines with graceful word-boundary ellipsis if needed
        if len(lines) > 2:
            l1 = lines[0]
            rem_words = clean_title[len(l1):].split()
            l2 = " ".join(rem_words)
            while len(rem_words) > 1 and (title_font.getbbox(l2 + "…")[2] - title_font.getbbox(l2 + "…")[0]) > max_w:
                rem_words.pop()
                l2 = " ".join(rem_words)
            lines = [l1, l2.rstrip() + "…"]

    line_h = int(curr_sz * 1.25)
    line_coords: List[Tuple[int, int]] = []
    for idx, line_text in enumerate(lines):
        bb = title_font.getbbox(line_text)
        lw = bb[2] - bb[0]
        ly = start_y + idx * line_h
        if norm_title_pos == "Above Playlist":
            if playlist_x + lw > width - margin:
                lx = max(margin, width - margin - lw)
            else:
                lx = playlist_x
        elif norm_title_pos == "Top-Left":
            lx = margin
            if logo_placed and logo_rect is not None and logo_rect[0] < int(width * 0.35) and logo_rect[1] < int(height * 0.35):
                lx = max(lx, logo_rect[2] + int(width * 0.02))
        else:  # Top-Center
            lx = (width - lw) // 2
        line_coords.append((lx, ly))

    total_th = len(lines) * line_h
    if line_coords:
        actual_bottom = max(ly + title_font.getbbox(l)[3] for (lx, ly), l in zip(line_coords, lines))
        title_bottom_y = max(start_y + total_th, actual_bottom)
    else:
        title_bottom_y = start_y + total_th
    return lines, title_font, total_th, line_coords, title_bottom_y


@dataclass
class TrackRowLayout:
    index: int                  # 0-based track index
    col_index: int              # 0-based column index
    row_in_col: int             # 0-based row index inside column
    display_text: str           # Full formatted string: "01. HABBAT KARREEH"
    text_x: int                 # X coordinate for drawing text
    text_y: int                 # Y coordinate for drawing text
    text_width: int             # Measured pixel width of display_text
    text_height: int            # Measured pixel height of font
    highlight_rect: Tuple[int, int, int, int]  # (x, y, w, h) for active track box
    indicator_pos: Tuple[int, int, int]        # (x, y, size) for pointer/logo indicator


@dataclass
class PlaylistLayoutResult:
    effective_font_size: int
    effective_row_step: int
    panel_rect: Tuple[int, int, int, int]      # (x, y, w, h) encompassing all columns
    column_x_positions: List[int]
    column_widths: List[int]
    rows: List[TrackRowLayout]


def compute_reference_playlist_layout(
    track_titles: List[str],
    canvas_size: Tuple[int, int],              # e.g. (1920, 1080)
    cols: int = 2,
    col_gap: int = 40,
    position: str = "Left",                    # "Left", "Center", "Right"
    requested_font_size: int = 48,
    row_spacing_mult: float = 1.45,            # UI "Row spacing" spinbox
    max_title_chars: int = 0,                  # 0 = Auto (NEVER truncate!)
    title_bottom_y: int = 165,                 # Bottom Y of collection title header
    logo_rect: Optional[Tuple[int, int, int, int]] = None,  # (x, y, w, h) or (x1, y1, x2, y2)
    logo_corner: str = "Bottom-Right",
    indicator_enabled: bool = False,
    fill_mode: str = "top_to_bottom",          # "top_to_bottom" (refer 2.jpg) or "balanced"
    measure_text_fn: Optional[Callable[[str, int], Tuple[int, int]]] = None,
    track_wrap_text: bool = False,
    playlist_x_offset: int = 0,
    playlist_y_offset: int = 0,
    website_rect: Optional[Tuple[int, int, int, int]] = None,
    template: str = "Two-column",
    width_ratio: Optional[float] = None,
    title_playlist_spacing: Optional[int] = None,
) -> PlaylistLayoutResult:
    """
    Reference-accurate playlist layout solver:
    1. NEVER truncates text with '…' when max_title_chars == 0 (Auto).
    2. Increasing col_gap shifts Column 2+ to the right without shrinking Column 1.
    3. Increasing row_spacing_mult spaces rows out up to available height WITHOUT shrinking font size.
    4. Reserves safe margin above Bottom-Left/Bottom-Right logo so text never collides.
    """
    canvas_w, canvas_h = canvas_size
    res_scale = canvas_h / 1080.0
    n_tracks = len(track_titles)
    if n_tracks == 0:
        return PlaylistLayoutResult(
            effective_font_size=requested_font_size,
            effective_row_step=requested_font_size,
            panel_rect=(0, 0, 0, 0),
            column_x_positions=[],
            column_widths=[],
            rows=[],
        )

    # Fallback text measurement if callback isn't passed
    if measure_text_fn is None:
        def measure_text_fn(text: str, font_px: int) -> Tuple[int, int]:
            return (int(len(text) * font_px * 0.58), int(font_px))

    # 1. Safe Margins & Logo Collision Prevention
    margin_left = int(canvas_w * (0.50 if template == "Minimal" else 0.035))
    margin_right = int(canvas_w * 0.035)
    max_usable_width = canvas_w - margin_left - margin_right

    if title_bottom_y and title_bottom_y > 0:
        if title_playlist_spacing is not None:
            spacing_px = int(title_playlist_spacing * res_scale)
        else:
            spacing_px = int(canvas_h * 0.03)
        top_y = title_bottom_y + spacing_px
    else:
        top_y = int(canvas_h * 0.16)
    top_y += int(playlist_y_offset * res_scale)

    bottom_y = canvas_h - int(canvas_h * 0.06)

    if logo_rect is not None:
        ly1 = logo_rect[1]
        norm_logo_corner = str(logo_corner or "Bottom-Right").title()
        norm_pos = str(position or "Left").capitalize()
        if "Bottom-Left" in norm_logo_corner and norm_pos == "Left":
            bottom_y = min(bottom_y, ly1 - int(canvas_h * 0.02))
        elif "Bottom-Right" in norm_logo_corner and norm_pos == "Right":
            bottom_y = min(bottom_y, ly1 - int(canvas_h * 0.02))
        elif norm_pos == "Center" and "Bottom" in norm_logo_corner:
            bottom_y = min(bottom_y, ly1 - int(canvas_h * 0.02))

    if website_rect is not None:
        wx1, wy1, wx2, wy2 = website_rect
        if wy1 > int(canvas_h * 0.70):
            bottom_y = min(bottom_y, wy1 - int(canvas_h * 0.015))
        elif wy1 < int(canvas_h * 0.30):
            top_y = max(top_y, wy2 + int(canvas_h * 0.02))

    available_height = max(120, bottom_y - top_y)

    norm_tmpl = str(template or "").lower()
    is_multi_col = norm_tmpl in ("two-column", "two column", "2-column")

    # Column selection: respect explicit cols >= 2; auto-split if multi-column template or if single column overflows available height
    est_single_col_h = n_tracks * int(requested_font_size * res_scale * row_spacing_mult)
    would_overflow_single_col = est_single_col_h > available_height

    if cols >= 2:
        desired_cols = cols
    elif is_multi_col or would_overflow_single_col:
        if n_tracks >= 15:
            desired_cols = 3
        else:
            desired_cols = 2
    else:
        desired_cols = 1
    actual_cols = max(1, min(4, min(desired_cols, n_tracks)))

    # 2. Format Track Strings (Only truncate by character count if max_title_chars > 0)
    formatted_tracks: List[str] = []
    for idx, raw_title in enumerate(track_titles):
        clean = raw_title.strip()
        m = re.match(r"^(\d+[\.\)]\s*)(.*)$", clean)
        if m:
            raw = clean
        else:
            raw = f"{idx + 1:02d}. {clean}"
        if max_title_chars and max_title_chars > 0 and len(raw) > max_title_chars:
            raw = raw[:max_title_chars].rstrip() + "…"
        formatted_tracks.append(raw)

    # 3. Determine Rows Per Column & Split Tracks (Matching refer 2.jpg)
    font_size = max(11, int(requested_font_size * res_scale))
    norm_fill = str(fill_mode or "top_to_bottom").lower()
    columns_tracks: List[List[Tuple[int, str]]] = []
    if actual_cols == 1:
        columns_tracks.append([(i, formatted_tracks[i]) for i in range(n_tracks)])
    elif actual_cols == 2 and norm_fill == "top_to_bottom" and n_tracks >= 14:
        # refer 2.jpg style: fill Column 1 top-to-bottom first up to 14 rows
        ideal_cap = min(14, max(math.ceil(n_tracks / actual_cols), int(available_height / (font_size * 1.35))))
        col1_rows = min(ideal_cap, n_tracks - 1)
        columns_tracks.append([(i, formatted_tracks[i]) for i in range(0, col1_rows)])
        columns_tracks.append([(i, formatted_tracks[i]) for i in range(col1_rows, n_tracks)])
    else:
        # Balanced distribution across columns
        rows_per_col = math.ceil(n_tracks / actual_cols)
        for c in range(actual_cols):
            start = c * rows_per_col
            end = min(n_tracks, start + rows_per_col)
            if start < n_tracks:
                columns_tracks.append([(i, formatted_tracks[i]) for i in range(start, end)])

    actual_cols = len(columns_tracks)
    rows_in_col1 = len(columns_tracks[0]) if columns_tracks else 1
    max_rows_in_any_col = max((len(col) for col in columns_tracks), default=1)

    # 4. Sizing Rule (b): Only reduce font_size if rows_in_col1 * font_size * 1.15 > available_height (legacy mode only; independent spacing preserves explicit font sizes)
    if rows_in_col1 * font_size * 1.15 > available_height and title_playlist_spacing is None:
        font_size = max(11, int(available_height / (rows_in_col1 * 1.15)))

    # 5. Measure Intrinsic Column Widths & Sizing Rule (a): Scale font if total_width > max_usable_width
    pad_x = 12
    ind_size = int(font_size * 0.65)
    ind_offset = (ind_size + 10) if indicator_enabled else 0

    # If track_wrap_text is True, pre-wrap long titles to target wrap boundary
    wrapped_columns_tracks: List[List[Tuple[int, str]]] = []
    if track_wrap_text:
        eff_wrap_cap = int(canvas_w * float(width_ratio or 0.45))
        max_text_w = max(150, eff_wrap_cap - ind_offset - pad_x * 2)
        for col in columns_tracks:
            wrapped_col = []
            for track_idx, text in col:
                tw, th = measure_text_fn(text, font_size)
                if tw > max_text_w:
                    raw_title = track_titles[track_idx]
                    m = re.match(r"^(\d+[\.\)]\s*)(.*)$", raw_title.strip())
                    if m:
                        prefix = m.group(1)
                    else:
                        prefix = f"{track_idx + 1:02d}. "
                    words = raw_title.split()
                    l1_words = []
                    l2_words = []
                    for w_word in words:
                        test_l = prefix + " ".join(l1_words + [w_word])
                        if measure_text_fn(test_l, font_size)[0] <= max_text_w or not l1_words:
                            l1_words.append(w_word)
                        else:
                            l2_words.append(w_word)
                    l1 = prefix + " ".join(l1_words)
                    if l2_words:
                        l2 = "    " + " ".join(l2_words)
                        wrapped_col.append((track_idx, f"{l1}\n{l2}"))
                    else:
                        wrapped_col.append((track_idx, l1))
                else:
                    wrapped_col.append((track_idx, text))
            wrapped_columns_tracks.append(wrapped_col)
    else:
        wrapped_columns_tracks = columns_tracks

    def _measure_item_width(item_text: str, f_size: int) -> int:
        if "\n" in item_text:
            return max((measure_text_fn(line, f_size)[0] for line in item_text.split("\n")), default=100)
        return measure_text_fn(item_text, f_size)[0]

    def measure_columns(f_size: int) -> Tuple[List[int], int]:
        ind_reserve = (int(f_size * 0.65) + 10) if indicator_enabled else 0
        col_w_list = []
        for col in wrapped_columns_tracks:
            max_w = max((_measure_item_width(text, f_size) for _, text in col), default=100)
            col_w_list.append(max_w + pad_x * 2 + ind_reserve)
        total_w = sum(col_w_list) + max(0, actual_cols - 1) * col_gap
        return col_w_list, total_w

    col_widths, total_width = measure_columns(font_size)
    while total_width > max_usable_width and font_size > 11:
        font_size -= 1
        col_widths, total_width = measure_columns(font_size)

    # Clamp effective_row_step without reducing font_size
    desired_row_step = int(round(font_size * row_spacing_mult))
    max_lines_in_any_col = max((sum(len(text.split("\n")) for _, text in col) for col in wrapped_columns_tracks), default=1)
    if max_lines_in_any_col * font_size * row_spacing_mult > available_height:
        effective_row_step = available_height // max(1, max_lines_in_any_col)
    else:
        effective_row_step = desired_row_step
    effective_row_step = max(int(font_size * 1.15), effective_row_step)

    # 6. Compute Horizontal X Positions (Increasing col_gap moves Col 2 right!)
    norm_pos = str(position or "Left").capitalize()
    if norm_pos == "Center":
        start_x = max(margin_left, (canvas_w - total_width) // 2 + int(playlist_x_offset * res_scale))
    elif norm_pos == "Right":
        start_x = max(margin_left, canvas_w - margin_right - total_width + int(playlist_x_offset * res_scale))
    else:  # Left (Default)
        start_x = margin_left + int(playlist_x_offset * res_scale)

    col_x_positions: List[int] = []
    curr_x = start_x
    for w in col_widths:
        col_x_positions.append(curr_x)
        curr_x += w + col_gap

    # 7. Build Row Coordinates, Highlight Boxes, and Indicator Positions
    rows_out: List[TrackRowLayout] = []
    pad_y = max(4, int(font_size * 0.16))
    ind_size = int(font_size * 0.65)
    ind_offset = (ind_size + 10) if indicator_enabled else 0

    for c_idx, col in enumerate(wrapped_columns_tracks):
        col_x = col_x_positions[c_idx]
        col_w = col_widths[c_idx]
        curr_row_y = top_y
        for r_idx, (track_idx, text) in enumerate(col):
            tw = _measure_item_width(text, font_size)
            lines = text.split("\n")
            n_lines = len(lines)
            line_spacing = max(2, int(font_size * 0.25))
            th = font_size * n_lines + (n_lines - 1) * line_spacing
            row_y = curr_row_y
            text_x = col_x + pad_x + ind_offset
            text_y = row_y

            hl_w = min(col_w, tw + pad_x * 2 + ind_offset + 8) if (col_gap < 20 or actual_cols == 1 or norm_tmpl in ("cinematic", "minimal")) else col_w

            hl_rect = (
                col_x,
                row_y - pad_y,
                hl_w,
                th + pad_y * 2,
            )
            ind_pos = (
                col_x + 8,
                row_y + max(0, (font_size - ind_size) // 2),
                ind_size,
            )

            rows_out.append(
                TrackRowLayout(
                    index=track_idx,
                    col_index=c_idx,
                    row_in_col=r_idx,
                    display_text=text,
                    text_x=text_x,
                    text_y=text_y,
                    text_width=tw,
                    text_height=th,
                    highlight_rect=hl_rect,
                    indicator_pos=ind_pos,
                )
            )

            curr_row_y += effective_row_step + (n_lines - 1) * (font_size + line_spacing)

    panel_h = max_rows_in_any_col * effective_row_step + pad_y * 2
    panel_rect = (
        start_x - 12,
        top_y - pad_y - 8,
        min(total_width + 24, canvas_w - start_x),
        panel_h + 16,
    )

    return PlaylistLayoutResult(
        effective_font_size=font_size,
        effective_row_step=effective_row_step,
        panel_rect=panel_rect,
        column_x_positions=col_x_positions,
        column_widths=col_widths,
        rows=rows_out,
    )


def calculate_playlist_layout(
    track_titles: list[str],
    width: int,
    height: int,
    template: str,
    playlist_position: str,
    playlist_columns: int,
    playlist_row_spacing: float,
    playlist_width_ratio: float,
    playlist_x_offset: int,
    playlist_y_offset: int,
    track_font_family: str,
    track_font_style: str,
    track_font_size: int,
    track_wrap_text: bool,
    title_bottom_y: int = 0,
    website_rect: Optional[Tuple[int, int, int, int]] = None,
    playlist_col_spacing: Optional[int] = None,
    track_max_chars: int = 0,
    logo_rect: Optional[Tuple[int, int, int, int]] = None,
    logo_position: str = "Bottom-Right",
    indicator_enabled: bool = False,
    fill_mode: str = "top_to_bottom",
    title_playlist_spacing: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Calculate dynamic playlist geometry using the Reference-Accurate Intrinsic Layout Engine.
    Provides complete compatibility with legacy layout dictionary while eliminating text clipping.
    """
    res_scale = height / 1080.0
    if playlist_col_spacing is not None and playlist_col_spacing > 0:
        gap = max(10, int(playlist_col_spacing * res_scale))
    else:
        gap = max(24, int(width * 0.032))

    def _measure_text_via_pil(text: str, f_size: int) -> Tuple[int, int]:
        fnt = _get_font(track_font_family, track_font_style, f_size)
        bb = fnt.getbbox(text)
        return (bb[2] - bb[0], bb[3] - bb[1])

    layout_res = compute_reference_playlist_layout(
        track_titles=track_titles,
        canvas_size=(width, height),
        cols=playlist_columns,
        col_gap=gap,
        position=playlist_position,
        requested_font_size=track_font_size,
        row_spacing_mult=playlist_row_spacing,
        max_title_chars=track_max_chars,
        title_bottom_y=title_bottom_y,
        logo_rect=logo_rect,
        logo_corner=logo_position,
        indicator_enabled=indicator_enabled,
        fill_mode=fill_mode,
        measure_text_fn=_measure_text_via_pil,
        track_wrap_text=track_wrap_text,
        playlist_x_offset=playlist_x_offset,
        playlist_y_offset=playlist_y_offset,
        website_rect=website_rect,
        template=template,
        width_ratio=playlist_width_ratio,
        title_playlist_spacing=title_playlist_spacing,
    )

    row_font = _get_font(track_font_family, track_font_style, layout_res.effective_font_size)
    track_items = []
    positions: List[Tuple[int, int, int, int]] = []

    for r in layout_res.rows:
        x1, y1, w, h = r.highlight_rect
        box = (x1, y1, x1 + w, y1 + h)
        positions.append(box)
        track_items.append({
            "index": r.index,
            "box": box,
            "x": layout_res.column_x_positions[r.col_index],
            "text_x": r.text_x,
            "y": r.text_y,
            "text": r.display_text,
            "highlight_rect": r.highlight_rect,
            "indicator_pos": r.indicator_pos,
            "col_index": r.col_index,
            "row_in_col": r.row_in_col,
        })

    max_y2 = max((b[3] for b in positions), default=0)
    overflow = max_y2 > (height - int(height * 0.02))
    max_disp = sum(1 for b in positions if b[3] <= height)
    num_cols = len(layout_res.column_widths)

    return {
        "track_items": track_items,
        "positions": positions,
        "is_two_col": num_cols >= 2,
        "num_cols": num_cols,
        "row_font": row_font,
        "eff_track_size": layout_res.effective_font_size,
        "row_gap": layout_res.effective_row_step,
        "row_height": int(layout_res.effective_font_size * (2.4 if track_wrap_text else 1.45)),
        "overflow": overflow,
        "max_displayable": max_disp,
        "col_widths": layout_res.column_widths,
        "col_0_width": layout_res.column_widths[0] if layout_res.column_widths else 0,
        "col_1_width": layout_res.column_widths[1] if len(layout_res.column_widths) > 1 else 0,
        "col_gap": gap,
        "panel_rect": layout_res.panel_rect,
        "result": layout_res,
    }


def create_intro_card(
    width: int,
    height: int,
    background_path: str,
    logo_path: str | None,
    collection_title: str,
    template: str,
    out_dir: str,
    title_font_family: str = "Segoe UI",
    title_font_style: str = "Bold",
    title_font_size: int = 56,
    website_text: str = "",
    website_show: bool = True,
    website_opacity: float = 1.0,
    website_font_size: int = 20,
    website_font_family: Optional[str] = None,
    website_font_style: Optional[str] = None,
    website_color: Optional[Union[str, tuple, list]] = None,
) -> str:
    """
    Generate an intro title card image featuring the collection title and logo presentation.
    Returns the file path to intro_card.png.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if background_path and Path(background_path).is_file():
        if is_video_file(background_path):
            try:
                raw_frame = extract_video_frame(background_path, 0.0)
                bg = _cover(raw_frame, (width, height)).convert("RGBA")
            except Exception:
                bg = Image.new("RGBA", (width, height), (23, 28, 26, 255))
        else:
            bg = _cover(Image.open(background_path), (width, height)).convert("RGBA")
    else:
        bg = Image.new("RGBA", (width, height), (23, 28, 26, 255))

    # A darker, cinematic wash for the intro
    wash = Image.new("RGBA", bg.size, (0, 0, 0, 110))
    intro_bg = Image.alpha_composite(bg, wash)
    intro_bg_path = str(out / "intro_bg.png")
    intro_bg.save(intro_bg_path)

    # Dedicated transparent overlay for foreground elements (logo, title, website)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    res_scale = height / 1080.0

    # Centered Logo Presentation
    logo_bottom = int(height * 0.38)
    if logo_path and Path(logo_path).is_file():
        try:
            with Image.open(logo_path) as logo_src:
                logo = clean_logo_image(logo_src).convert("RGBA")
                max_w, max_h = int(width * 0.28), int(height * 0.22)
                logo.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                lx = (width - logo.width) // 2
                ly = int(height * 0.18)
                overlay.alpha_composite(logo, (lx, ly))
                logo_bottom = ly + logo.height
        except Exception:
            pass

    # Title safe frame bounds and intelligent multi-line fitting
    norm_title_sz = get_normalized_font_size(title_font_family, title_font_style, title_font_size)
    base_title_size = max(20, int(norm_title_sz * res_scale))

    web_text_clean = website_text.strip()
    web_op = max(0.0, min(1.0, float(website_opacity if website_opacity is not None else 1.0)))
    has_web = bool(web_text_clean and website_show and web_op > 0.0)

    max_title_w = int(width * 0.84)
    min_title_y = logo_bottom + int(height * 0.03)
    max_title_y = int(height * 0.82) if has_web else int(height * 0.88)
    available_title_h = max(60, max_title_y - min_title_y)

    curr_sz = base_title_size
    clean_col_title = collection_title.strip()
    words = clean_col_title.split()
    lines = [clean_col_title]

    while curr_sz >= 16:
        t_font = _get_font(title_font_family, title_font_style, curr_sz)
        tb = t_font.getbbox(clean_col_title)
        if (tb[2] - tb[0]) <= max_title_w:
            lines = [clean_col_title]
            line_h = int(curr_sz * 1.25)
            if line_h <= available_title_h:
                title_font = t_font
                break

        lines_cand = []
        cur_l = []
        for w in words:
            cand = " ".join(cur_l + [w])
            if (t_font.getbbox(cand)[2] - t_font.getbbox(cand)[0]) <= max_title_w or not cur_l:
                cur_l.append(w)
            else:
                lines_cand.append(" ".join(cur_l))
                cur_l = [w]
        if cur_l:
            lines_cand.append(" ".join(cur_l))

        line_h = int(curr_sz * 1.25)
        total_cand_h = len(lines_cand) * line_h
        if len(lines_cand) <= 2 and total_cand_h <= available_title_h and all((t_font.getbbox(l)[2] - t_font.getbbox(l)[0]) <= max_title_w for l in lines_cand):
            lines = lines_cand
            title_font = t_font
            break
        curr_sz -= 2
    else:
        title_font = _get_font(title_font_family, title_font_style, curr_sz)

    line_h = int(curr_sz * 1.25)
    total_th = len(lines) * line_h
    start_ty = min_title_y + max(0, (available_title_h - total_th) // 2)

    c_draw = ImageDraw.Draw(overlay, "RGBA")
    for idx, line_text in enumerate(lines):
        bb = title_font.getbbox(line_text)
        lw = bb[2] - bb[0]
        lx = max(int(width * 0.05), (width - lw) // 2)
        ly = start_ty + idx * line_h
        _draw_text_with_outline_and_shadow(
            draw=c_draw,
            xy=(lx, ly),
            text=line_text,
            font=title_font,
            fill=(255, 255, 250, 255),
            stroke_width=max(0, int(height * 0.0015)),
            stroke_fill=(0, 0, 0, 160),
            shadow=True,
            shadow_offset=(max(2, int(3 * res_scale)), max(2, int(3 * res_scale))),
            shadow_fill=(0, 0, 0, 180),
        )

    # Optional Website Address at bottom center
    web_text_clean = website_text.strip()
    web_op = max(0.0, min(1.0, float(website_opacity if website_opacity is not None else 1.0)))
    if web_text_clean and website_show and web_op > 0.0:
        web_size = max(12, int(website_font_size * res_scale))
        web_family = website_font_family or title_font_family or "Segoe UI"
        web_style = website_font_style or "Regular"
        web_font = _get_font(web_family, web_style, web_size)
        wb = web_font.getbbox(web_text_clean)
        ww = wb[2] - wb[0]
        wh = wb[3] - wb[1]
        wx = (width - ww) // 2
        wy = int(height * 0.88)
        web_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        w_draw = ImageDraw.Draw(web_layer, "RGBA")

        # Contrast-adaptive color
        if website_color is not None:
            text_rgb = _hex_to_rgb(website_color, (240, 244, 242))
        else:
            crop = intro_bg.crop((wx, wy, wx + ww, wy + wh)).convert("L")
            pixels = list(crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata())
            avg_lum = sum(pixels) / max(1, len(pixels))
            text_rgb = (35, 40, 42) if avg_lum > 140 else (240, 244, 242)

        text_alpha = max(0, min(255, int(round(255 * web_op))))
        w_draw.text((wx - wb[0], wy - wb[1]), web_text_clean, font=web_font, fill=(*text_rgb, text_alpha))
        overlay = Image.alpha_composite(overlay, web_layer)

    overlay_path = str(out / "intro_overlay.png")
    overlay.save(overlay_path)

    # Full composite card for preview and single-frame consumers
    full_card = Image.alpha_composite(intro_bg, overlay)
    intro_path = str(out / "intro_card.png")
    full_card.save(intro_path)
    return intro_path
    return intro_path


def create_composition(
    width: int,
    height: int,
    background_path: str,
    logo_path: str | None,
    collection_title: str,
    track_titles: list[str],
    template: str,
    out_dir: str,
    indicator_mode: str = "both",
    cursor_path: str | None = None,
    cursor_size: int = 32,
    preview_only_first_overlay: bool = False,
    active_track_index: int = 0,
    title_font_family: str = "Segoe UI",
    title_font_style: str = "Bold",
    title_font_size: int = 46,
    track_font_family: str = "Segoe UI",
    track_font_style: str = "Bold",
    track_font_size: int = 22,
    logo_position: str = "Bottom-Right",
    website_text: str = "",
    website_position: str = "Top-Right",
    website_font_size: int = 18,
    website_show: bool = True,
    website_opacity: float = 1.0,
    website_font_family: Optional[str] = None,
    website_font_style: Optional[str] = None,
    website_color: Optional[Union[str, tuple, list]] = None,
    playlist_position: str = "Left",
    playlist_x_offset: int = 0,
    playlist_y_offset: int = 0,
    playlist_width_ratio: float = 0.47,
    playlist_columns: int = 1,
    playlist_row_spacing: float = 1.85,
    playlist_col_spacing: Optional[int] = None,
    track_max_chars: int = 0,
    playlist_bg_opacity: float = 0.0,
    playlist_bg_color: Union[str, tuple, list] = (0, 0, 0),
    playlist_bg_radius: int = 6,
    playlist_padding: int = 8,
    track_wrap_text: bool = False,
    title_position: str = "Top-Center",
    title_margin: int = 12,
    title_show: bool = True,
    title_color: Union[str, tuple, list] = (255, 255, 248),
    title_outline_color: Union[str, tuple, list] = (0, 0, 0),
    title_outline_width: int = 2,
    title_shadow: bool = True,
    track_color: Union[str, tuple, list] = (242, 243, 231),
    track_outline_color: Union[str, tuple, list] = (0, 0, 0),
    track_outline_width: int = 1,
    track_shadow: bool = True,
    active_track_color: Optional[Union[str, tuple, list]] = None,
    highlight_style: str = "Pill",
    highlight_color: Union[str, tuple, list] = (248, 220, 139),
    highlight_bg_opacity: float = 0.25,
    logo_cleanup_mode: str = "auto",
    logo_scale: float = 1.0,
    video_start_time: float = 0.0,
    video_fit_mode: str = "fill/crop",
    video_wash_opacity: float = 0.20,
    title_playlist_spacing: Optional[int] = 40,
    title_opacity: float = 1.0,
    track_opacity: float = 1.0,
    title_softening: float = 0.0,
    track_softening: float = 0.0,
    text_opacity: Optional[float] = None,
    text_softening: Optional[float] = None,
    highlight_outline_width: int = 2,
    highlight_corner_radius: Optional[int] = None,
    highlight_target: str = "row",
    highlight_padding_x: Optional[int] = None,
    highlight_padding_y: Optional[int] = None,
    highlight_opacity: float = 1.0,
    cursor_y_offset: int = 0,
    highlight_y_offset: int = 0,
) -> tuple[str, list[str]]:
    """
    Return base composition PNG path and per-track cursor/highlight overlay PNG paths.
    Supports adjustable layout, multi-column playlists, transparent/semi-opaque backgrounds,
    active-track styling, typography outlines/shadows, and logo background cleanup.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    eff_title_op = text_opacity if text_opacity is not None else title_opacity
    eff_track_op = text_opacity if text_opacity is not None else track_opacity
    eff_title_soft = text_softening if text_softening is not None else title_softening
    eff_track_soft = text_softening if text_softening is not None else track_softening

    mode = indicator_mode.lower() if indicator_mode in INDICATOR_MODES else "both"
    show_highlight = mode in ("both", "highlight_only")
    show_cursor = mode in ("both", "cursor_only")

    # 1. Base Composition Image (with LRU-cached scaling and decoding)
    bg_is_video = bool(background_path and Path(background_path).is_file() and is_video_file(background_path))
    wash_alpha = int(255 * max(0.0, min(1.0, float(video_wash_opacity if bg_is_video else 0.20))))

    bg, fg = _get_prepared_background(
        background_path=background_path,
        width=width,
        height=height,
        video_start_time=video_start_time,
        video_fit_mode=video_fit_mode,
        wash_alpha=wash_alpha,
        bg_is_video=bg_is_video,
    )
    draw = ImageDraw.Draw(bg, "RGBA")

    # Dynamic Typography Scaling
    res_scale = height / 1080.0
    margin = int(width * 0.055)

    eff_width_ratio = max(0.25, min(0.90, float(playlist_width_ratio or 0.47)))
    usable_width = int(width * eff_width_ratio)
    if template == "Minimal":
        usable_width = int(width * 0.39)

    norm_pos = playlist_position.strip().capitalize()
    if norm_pos == "Center":
        base_px = (width - usable_width) // 2
    elif norm_pos == "Right":
        base_px = width - usable_width - margin
    else:  # Left
        base_px = int(width * (0.56 if template == "Minimal" else 0.065))
    playlist_x = base_px + int(playlist_x_offset * res_scale)

    # 2. Logo Placement & Background Cleanup (Positioned first for collision avoidance)
    logo_placed = False
    logo_rect: Optional[Tuple[int, int, int, int]] = None
    if logo_path and Path(logo_path).is_file():
        try:
            with Image.open(logo_path) as logo_src:
                raw_logo = clean_logo_image(logo_src, mode=logo_cleanup_mode)
                eff_scale = max(0.4, min(2.5, float(logo_scale or 1.0)))
                max_w = int(width * 0.13 * eff_scale)
                max_h = int(height * 0.11 * eff_scale)
                raw_logo.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                lx, ly = _calculate_corner_position(
                    logo_position, raw_logo.width, raw_logo.height, width, height, margin, int(height * 0.045)
                )
                bg.alpha_composite(raw_logo, (lx, ly))
                fg.alpha_composite(raw_logo, (lx, ly))
                logo_rect = (lx, ly, lx + raw_logo.width, ly + raw_logo.height)
                logo_placed = True
        except Exception:
            pass

    # 3. Website Address Placement on Dedicated RGBA Layer (True Porter-Duff Alpha Blend)
    web_text_clean = website_text.strip()
    web_op = max(0.0, min(1.0, float(website_opacity if website_opacity is not None else 1.0)))
    web_rect: Optional[Tuple[int, int, int, int]] = None
    if web_text_clean and website_show and web_op > 0.0:
        eff_web_size = max(10, int(website_font_size * res_scale))
        web_family = website_font_family or track_font_family or "Segoe UI"
        web_style = website_font_style or "Regular"
        web_font = _get_font(web_family, web_style, eff_web_size)
        wb = web_font.getbbox(web_text_clean)
        tw = wb[2] - wb[0]
        th = wb[3] - wb[1]

        # Ensure text stays inside frame and doesn't become clipped
        max_avail_w = max(50, width - 2 * margin)
        while tw > max_avail_w and eff_web_size > 10:
            eff_web_size -= 1
            web_font = _get_font(web_family, web_style, eff_web_size)
            wb = web_font.getbbox(web_text_clean)
            tw = wb[2] - wb[0]
            th = wb[3] - wb[1]

        margin_y = int(height * 0.045)
        wx, wy = _calculate_corner_position(
            website_position, tw, th, width, height, margin, margin_y
        )

        # Overlap Prevention: avoid collision with logo in same corner/location
        if logo_placed and logo_rect is not None:
            norm_logo_pos = logo_position.strip().lower()
            norm_web_pos = website_position.strip().lower()
            if norm_logo_pos == norm_web_pos:
                lx1, ly1, lx2, ly2 = logo_rect
                if "bottom" in norm_web_pos:
                    wy = ly1 - th - int(height * 0.015)
                    if wy < margin_y:
                        wy = ly2 + int(height * 0.015)
                else:
                    wy = ly2 + int(height * 0.015)
                    if wy + th > height - margin_y:
                        wy = ly1 - th - int(height * 0.015)

        # Boundary clamping to preserve frame safety margins
        wx = max(margin, min(wx, width - margin - tw))
        wy = max(margin_y, min(wy, height - margin_y - th))
        web_rect = (wx, wy, wx + tw, wy + th)

        # Dedicated transparent RGBA layer for linear alpha compositing
        web_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        w_draw = ImageDraw.Draw(web_layer, "RGBA")

        # Optimal contrast legibility on light and dark backgrounds without unwanted boxes or dark halos
        if website_color is not None:
            text_rgb = _hex_to_rgb(website_color, (240, 244, 242))
        else:
            crop = bg.crop(web_rect).convert("L")
            pixels = list(crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata())
            avg_lum = sum(pixels) / max(1, len(pixels))
            text_rgb = (35, 40, 42) if avg_lum > 140 else (240, 244, 242)

        text_alpha = max(0, min(255, int(round(255 * web_op))))
        w_draw.text((wx - wb[0], wy - wb[1]), web_text_clean, font=web_font, fill=(*text_rgb, text_alpha))

        # True Porter-Duff alpha blend onto base image
        bg = Image.alpha_composite(bg, web_layer)
        fg = Image.alpha_composite(fg, web_layer)
        draw = ImageDraw.Draw(bg, "RGBA")

    # 4. Collection Title Placement & Safe Frame Fitting
    col_title_clean = collection_title.strip()
    norm_title_pos = title_position.strip()
    render_title = title_show and bool(col_title_clean) and (norm_title_pos != "Hidden")
    title_bottom_y = int(height * 0.08)

    if render_title:
        title_rgb = _hex_to_rgb(title_color, (255, 255, 248))
        title_stroke_rgb = _hex_to_rgb(title_outline_color, (0, 0, 0))
        t_stroke_w = max(0, int(title_outline_width * res_scale)) if title_outline_width else 0

        title_lines, title_font, total_th, line_coords, title_bottom_y = _calculate_title_layout(
            collection_title=col_title_clean,
            title_font_family=title_font_family,
            title_font_style=title_font_style,
            title_font_size=title_font_size,
            norm_title_pos=norm_title_pos,
            width=width,
            height=height,
            margin=margin,
            res_scale=res_scale,
            logo_placed=logo_placed,
            logo_rect=logo_rect,
            usable_width=usable_width,
            playlist_x=playlist_x,
            website_rect=web_rect,
        )

        title_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        t_draw = ImageDraw.Draw(title_layer, "RGBA")

        t_alpha = max(0, min(255, int(round(255 * eff_title_op))))
        t_stroke_alpha = max(0, min(255, int(round(120 * eff_title_op))))
        t_shadow_alpha = max(0, min(255, int(round(140 * eff_title_op))))

        if playlist_bg_opacity > 0.1 and line_coords:
            min_tx = min(c[0] for c in line_coords)
            min_ty = min(c[1] for c in line_coords)
            max_tx = max(c[0] + title_font.getbbox(l)[2] for c, l in zip(line_coords, title_lines))
            max_ty = min_ty + total_th
            bg_rgb = _hex_to_rgb(playlist_bg_color, (0, 0, 0))
            bg_alpha = int(255 * min(1.0, playlist_bg_opacity * 0.7))
            t_draw.rounded_rectangle(
                (min_tx - 16, min_ty - 6, max_tx + 16, max_ty + 10),
                radius=max(3, int(playlist_bg_radius * res_scale)),
                fill=(*bg_rgb, bg_alpha),
            )
            title_bottom_y = max(title_bottom_y, max_ty + 10)

        for (lx, ly), line_txt in zip(line_coords, title_lines):
            _draw_text_with_outline_and_shadow(
                draw=t_draw,
                xy=(lx, ly),
                text=line_txt,
                font=title_font,
                fill=(*title_rgb, t_alpha),
                stroke_width=t_stroke_w,
                stroke_fill=(*title_stroke_rgb, t_stroke_alpha),
                shadow=title_shadow,
                shadow_offset=(max(1, int(2 * res_scale)), max(1, int(2 * res_scale))),
                shadow_fill=(0, 0, 0, t_shadow_alpha),
            )

        if eff_title_soft > 0:
            title_layer = title_layer.filter(ImageFilter.GaussianBlur(radius=eff_title_soft * res_scale))

        bg = Image.alpha_composite(bg, title_layer)
        fg = Image.alpha_composite(fg, title_layer)
        draw = ImageDraw.Draw(bg, "RGBA")

    # 5. Dynamic Playlist Geometry & Fit-to-Frame Auto-Column Placement
    should_title_space = render_title and (norm_title_pos == "Above Playlist" or (title_playlist_spacing is not None and norm_title_pos in ("Top-Center", "Top-Left")))
    layout_info = calculate_playlist_layout(
        track_titles=track_titles,
        width=width,
        height=height,
        template=template,
        playlist_position=playlist_position,
        playlist_columns=playlist_columns,
        playlist_row_spacing=playlist_row_spacing,
        playlist_width_ratio=playlist_width_ratio,
        playlist_x_offset=playlist_x_offset,
        playlist_y_offset=playlist_y_offset,
        track_font_family=track_font_family,
        track_font_style=track_font_style,
        track_font_size=track_font_size,
        track_wrap_text=track_wrap_text,
        title_bottom_y=title_bottom_y if should_title_space else 0,
        title_playlist_spacing=title_playlist_spacing,
        website_rect=web_rect,
        playlist_col_spacing=playlist_col_spacing,
        track_max_chars=track_max_chars,
        logo_rect=logo_rect,
        logo_position=logo_position,
        indicator_enabled=(show_cursor or show_highlight),
    )

    track_items = layout_info["track_items"]
    positions = layout_info["positions"]
    is_two_col = layout_info["is_two_col"]
    row_font = layout_info["row_font"]
    eff_track_size = layout_info["eff_track_size"]

    # 6. Playlist Track Layout & Base Rendering
    base = bg.copy()
    base_draw = ImageDraw.Draw(base, "RGBA")

    track_rgb = _hex_to_rgb(track_color, (242, 243, 231))
    track_stroke_rgb = _hex_to_rgb(track_outline_color, (0, 0, 0))
    t_outline_w = max(0, int(track_outline_width * res_scale)) if track_outline_width else 0
    bg_panel_rgb = _hex_to_rgb(playlist_bg_color, (0, 0, 0))
    bg_panel_alpha = int(255 * max(0.0, min(1.0, float(playlist_bg_opacity or 0.0))))

    # Draw translucent panel/row backing if requested
    if bg_panel_alpha > 0:
        panel_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        p_draw = ImageDraw.Draw(panel_layer, "RGBA")
        for item in track_items:
            p_draw.rounded_rectangle(
                item["box"],
                radius=max(2, int(playlist_bg_radius * res_scale)),
                fill=(*bg_panel_rgb, bg_panel_alpha),
                outline=(255, 255, 255, 18) if bg_panel_alpha > 80 else None,
                width=1,
            )
        base = Image.alpha_composite(base, panel_layer)
        fg = Image.alpha_composite(fg, panel_layer)
        base_draw = ImageDraw.Draw(base, "RGBA")

    has_overlays = (mode != "neither") and (show_highlight or show_cursor) and bool(track_items)

    # If neither cursor nor highlight is requested, render tracks on base and return 0 overlays
    if not has_overlays:
        tracks_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        tr_draw = ImageDraw.Draw(tracks_layer, "RGBA")
        tr_alpha = max(0, min(255, int(round(245 * eff_track_op))))
        tr_stroke_alpha = max(0, min(255, int(round(120 * eff_track_op))))
        tr_shadow_alpha = max(0, min(255, int(round(140 * eff_track_op))))
        for item in track_items:
            _draw_text_with_outline_and_shadow(
                draw=tr_draw,
                xy=(item.get("text_x", item["x"]), item["y"]),
                text=item["text"],
                font=row_font,
                fill=(*track_rgb, tr_alpha),
                stroke_width=t_outline_w,
                stroke_fill=(*track_stroke_rgb, tr_stroke_alpha),
                shadow=track_shadow,
                shadow_offset=(max(1, int(1 * res_scale)), max(1, int(1 * res_scale))),
                shadow_fill=(0, 0, 0, tr_shadow_alpha),
            )
        if eff_track_soft > 0:
            tracks_layer = tracks_layer.filter(ImageFilter.GaussianBlur(radius=eff_track_soft * res_scale))
        base = Image.alpha_composite(base, tracks_layer)
        fg = Image.alpha_composite(fg, tracks_layer)
        fg_path = str(out / "composition_fg.png")
        fg.save(fg_path)
        base_path = str(out / "composition.png")
        base.save(base_path)
        return base_path, []

    # When overlays are enabled, save base without playlist text to avoid duplicate/ghosted rendering
    fg_path = str(out / "composition_fg.png")
    fg.save(fg_path)
    base_path = str(out / "composition.png")
    base.save(base_path)

    # 7. Prepare Custom Cursor asset if enabled
    custom_cursor_img: Optional[Image.Image] = None
    target_cursor_dim = max(12, int(cursor_size * res_scale))

    if show_cursor and cursor_path and Path(cursor_path).is_file():
        try:
            custom_cursor_img = load_cursor_image(cursor_path, target_cursor_dim)
        except Exception:
            custom_cursor_img = None

    # 8. Generate Per-Track Overlays (Highlight, Cursor & Razor-Sharp Typography)
    overlays: list[str] = []
    active_idx = max(0, min(len(track_items) - 1, active_track_index)) if track_items else 0
    indices_to_render = [active_idx] if (preview_only_first_overlay and track_items) else range(len(track_items))

    hl_rgb = _hex_to_rgb(highlight_color, (248, 220, 139))
    hl_alpha = int(255 * max(0.05, min(1.0, float(highlight_bg_opacity or 0.25))))
    norm_hl_style = highlight_style.strip().title()

    for i in indices_to_render:
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay, "RGBA")
        active_item = track_items[i]
        x1, y1, x2, y2 = active_item["box"]

        # Calculate exact text visual vertical center for active track item
        cursor_ref_x = active_item.get("text_x", x1)
        item_text = active_item["text"]
        first_line = item_text.split("\n")[0] if "\n" in item_text else item_text
        tb_active = od.textbbox((cursor_ref_x, active_item["y"]), first_line, font=row_font)
        text_visual_cy = (tb_active[1] + tb_active[3]) // 2

        # Apply resolution-scaled vertical offset adjustments
        eff_hl_y_off = int(round(highlight_y_offset * res_scale))
        eff_cur_y_off = int(round(cursor_y_offset * res_scale))
        hl_cy = text_visual_cy + eff_hl_y_off
        cur_cy = text_visual_cy + eff_cur_y_off

        # Moving highlight
        if show_highlight:
            # Vertically center the row highlight box symmetrically around the active text + offset
            row_h = y2 - y1
            half_h = row_h // 2
            hl_box = (x1, hl_cy - half_h, x2, hl_cy - half_h + row_h)

            # Support text-tight highlight bounding
            if str(highlight_target or "row").lower().strip() == "text":
                pad_x = highlight_padding_x if highlight_padding_x is not None else int(18 * res_scale)
                pad_y = highlight_padding_y if highlight_padding_y is not None else int(6 * res_scale)
                tb_all = od.textbbox((cursor_ref_x, active_item["y"]), item_text, font=row_font) if "\n" in item_text else tb_active
                half_th = (tb_all[3] - tb_all[1]) // 2
                hl_box = (
                    max(margin, tb_all[0] - pad_x),
                    max(0, hl_cy - half_th - pad_y),
                    min(width - margin, tb_all[2] + pad_x),
                    min(height, hl_cy + half_th + pad_y),
                )

            eff_outline_w = max(1, int(round(highlight_outline_width * res_scale))) if highlight_outline_width else max(1, int(width * 0.0015))
            if highlight_corner_radius is not None and highlight_corner_radius == 0:
                eff_radius = 0
            elif highlight_corner_radius is not None:
                eff_radius = max(0, int(round(highlight_corner_radius * res_scale)))
            else:
                eff_radius = max(2, int(eff_track_size * 0.18))

            stroke_a = max(0, min(255, int(round(255 * (highlight_opacity if highlight_opacity is not None else 1.0)))))
            fill_a = int(255 * max(0.0, min(1.0, float(highlight_bg_opacity or 0.0))))

            if norm_hl_style == "Accent Bar":
                bar_w = max(4, int(width * 0.0035))
                od.rounded_rectangle(
                    (x1, hl_box[1], x1 + bar_w, hl_box[3]),
                    radius=max(1, bar_w // 2),
                    fill=(*hl_rgb, stroke_a),
                )
                od.rounded_rectangle(hl_box, radius=eff_radius, fill=(*hl_rgb, max(15, fill_a // 2)))

            elif norm_hl_style == "Outline":
                # Crisp border outline only - completely transparent interior without inner shading/tint
                if eff_radius == 0:
                    od.rectangle(
                        hl_box,
                        outline=(*hl_rgb, stroke_a),
                        fill=None,
                        width=eff_outline_w,
                    )
                else:
                    od.rounded_rectangle(
                        hl_box,
                        radius=eff_radius,
                        outline=(*hl_rgb, stroke_a),
                        fill=None,
                        width=eff_outline_w,
                    )

            elif norm_hl_style == "Underline":
                item_tx = active_item.get("text_x", x1)
                tb = od.textbbox((item_tx, active_item["y"]), active_item["text"], font=row_font)
                line_y = tb[3] + max(3, int(4 * res_scale)) + eff_hl_y_off
                line_h = max(2, eff_outline_w)
                od.rounded_rectangle(
                    (item_tx, line_y, min(x2, tb[2] + int(width * 0.008)), line_y + line_h),
                    radius=1 if eff_radius > 0 else 0,
                    fill=(*hl_rgb, stroke_a),
                )

            else:  # "Pill" (default)
                if eff_radius == 0:
                    od.rectangle(
                        hl_box,
                        outline=(*hl_rgb, stroke_a),
                        fill=(*hl_rgb, fill_a),
                        width=eff_outline_w,
                    )
                else:
                    od.rounded_rectangle(
                        hl_box,
                        radius=eff_radius,
                        outline=(*hl_rgb, stroke_a),
                        fill=(*hl_rgb, fill_a),
                        width=eff_outline_w,
                    )

        # Cursor
        if show_cursor:
            cy = cur_cy
            gap = max(4, int(width * 0.006))
            cur_dim = target_cursor_dim if custom_cursor_img is None else custom_cursor_img.size[0]

            # If highlight surrounds text, position cursor cleanly to the left of the highlight box boundary to avoid crossing
            if show_highlight and (str(highlight_target or "row").lower().strip() == "text"):
                cx = max(4, hl_box[0] - cur_dim - gap)
            else:
                cx = max(4, cursor_ref_x - cur_dim - gap)

            if custom_cursor_img is not None:
                cw, ch = custom_cursor_img.size
                overlay.alpha_composite(custom_cursor_img, (cx, cy - ch // 2))
            else:
                arrow_w = target_cursor_dim
                arrow_h = target_cursor_dim
                arrow = [
                    (cx, cy - arrow_h // 2),
                    (cx + arrow_w, cy),
                    (cx, cy + arrow_h // 2),
                ]
                od.polygon(arrow, fill=(*hl_rgb, 255))

        # Render full tracklist on overlay on isolated text layer
        active_rgb = _hex_to_rgb(active_track_color, track_rgb) if active_track_color else track_rgb
        tr_active_alpha = int(round(255 * eff_track_op))
        tr_inactive_alpha = int(round(245 * eff_track_op))
        tr_stroke_alpha = int(round(120 * eff_track_op))
        tr_shadow_alpha = int(round(140 * eff_track_op))

        text_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        td_draw = ImageDraw.Draw(text_layer, "RGBA")

        for j, item in enumerate(track_items):
            is_active = (j == i)
            # Active track glyph fill is visually consistent with inactive tracks unless active_track_color is explicitly configured.
            # Highlight color styles the row indicator (Pill/Accent Bar/Outline/Underline) and cursor, never the text font.
            text_fill = (*active_rgb, tr_active_alpha) if is_active else (*track_rgb, tr_inactive_alpha)

            _draw_text_with_outline_and_shadow(
                draw=td_draw,
                xy=(item.get("text_x", item["x"]), item["y"]),
                text=item["text"],
                font=row_font,
                fill=text_fill,
                stroke_width=t_outline_w,
                stroke_fill=(*track_stroke_rgb, tr_stroke_alpha),
                shadow=track_shadow,
                shadow_offset=(max(1, int(1 * res_scale)), max(1, int(1 * res_scale))),
                shadow_fill=(0, 0, 0, tr_shadow_alpha),
            )

        if eff_track_soft > 0:
            text_layer = text_layer.filter(ImageFilter.GaussianBlur(radius=eff_track_soft * res_scale))

        overlay = Image.alpha_composite(overlay, text_layer)

        op = str(out / f"cursor_{i:03d}.png")
        overlay.save(op)
        overlays.append(op)

    return base_path, overlays
