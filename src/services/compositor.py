"""Creates a clean base composition and transparent per-track cursor/highlight overlays."""
from __future__ import annotations

from collections import deque
import os
from pathlib import Path
from typing import Optional, Tuple, Union, List, Dict, Any
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageChops

from src.services.font_service import resolve_font_path

INDICATOR_MODES = ["both", "cursor_only", "highlight_only", "neither"]
CORNER_POSITIONS = ["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right"]
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


def _get_font(family: str = "Segoe UI", style: str = "Regular", size: int = 20) -> ImageFont.ImageFont:
    """Resolve and load a TTF/OTF font for Pillow, falling back to default if unavailable."""
    path = resolve_font_path(family, style)
    if path and Path(path).is_file():
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


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
    """Calculate (x, y) coordinates for an element in one of the 4 screen corners."""
    pos = corner.strip().lower()
    if "top" in pos and "left" in pos:
        return margin_x, margin_y
    if "top" in pos and "right" in pos:
        return canvas_w - margin_x - elem_w, margin_y
    if "bottom" in pos and "left" in pos:
        return margin_x, canvas_h - margin_y - elem_h
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
) -> Tuple[List[str], ImageFont.ImageFont, int, List[Tuple[int, int]], int]:
    """
    Calculate multiline text wrapping, font scaling, line coordinates, and bounding limit
    for the collection title. Scales down smoothly if title is long to prevent truncation or overlap.
    """
    clean_title = collection_title.strip()
    base_font_sz = max(18, int(title_font_size * res_scale))

    if norm_title_pos == "Above Playlist":
        max_w = max(int(width * 0.25), usable_width)
        start_y = int(height * 0.07)
    elif norm_title_pos == "Top-Left":
        start_x = margin
        if logo_placed and logo_rect is not None and logo_rect[0] < int(width * 0.35) and logo_rect[1] < int(height * 0.35):
            start_x = max(start_x, logo_rect[2] + int(width * 0.02))
        max_w = max(int(width * 0.30), int(width * 0.70) - start_x)
        start_y = int(height * 0.06)
    else:  # Top-Center
        max_w = int(width * 0.70)
        if logo_placed and logo_rect is not None:
            lx1, ly1, lx2, ly2 = logo_rect
            if ly1 < int(height * 0.22):
                # Avoid colliding horizontally with top logos
                clearance = min(lx1, width - lx2) * 2 - int(width * 0.04)
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
            lx = playlist_x
        elif norm_title_pos == "Top-Left":
            lx = margin
            if logo_placed and logo_rect is not None and logo_rect[0] < int(width * 0.35) and logo_rect[1] < int(height * 0.35):
                lx = max(lx, logo_rect[2] + int(width * 0.02))
        else:  # Top-Center
            lx = (width - lw) // 2
        line_coords.append((lx, ly))

    total_th = len(lines) * line_h
    title_bottom_y = start_y + total_th
    return lines, title_font, total_th, line_coords, title_bottom_y


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
) -> Dict[str, Any]:
    """
    Calculate dynamic playlist geometry with fit-to-frame auto-compaction, multi-column splitting,
    and automatic content-aware column spacing based on the longest title.
    If titles exceed allowable boundaries, dynamically fits them with graceful truncation without
    breaking grid alignment.
    """
    res_scale = height / 1080.0
    margin = int(width * 0.055)
    bottom_limit = int(height * 0.93)

    if website_rect is not None and website_rect[1] > int(height * 0.70):
        bottom_limit = min(bottom_limit, website_rect[1] - int(height * 0.015))

    base_y = int(height * (0.16 if template == "Minimal" else 0.17))
    if title_bottom_y > 0:
        base_y = max(base_y, title_bottom_y + int(height * 0.035))
    playlist_y = base_y + int(playlist_y_offset * res_scale)
    avail_h = max(80, bottom_limit - playlist_y)

    n_tracks = len(track_titles)
    if n_tracks == 0:
        row_font = _get_font(track_font_family, track_font_style, max(12, int(track_font_size * res_scale)))
        return {
            "track_items": [],
            "positions": [],
            "is_two_col": False,
            "row_font": row_font,
            "eff_track_size": max(12, int(track_font_size * res_scale)),
            "row_gap": int(max(12, int(track_font_size * res_scale)) * 1.85),
            "row_height": int(max(12, int(track_font_size * res_scale)) * 1.45),
            "overflow": False,
            "max_displayable": 0,
            "col_0_width": 0,
            "col_1_width": 0,
            "col_gap": 0,
        }

    # Dynamic Column Count Selection (1, 2, 3, or 4 columns)
    norm_template = str(template or "").lower()
    base_eff_sz = max(12, int(track_font_size * res_scale))
    init_spacing = max(1.0, float(playlist_row_spacing or 1.85))
    init_gap = int(base_eff_sz * init_spacing)
    row_h_mult = 2.4 if track_wrap_text else 1.45
    init_row_h = int(base_eff_sz * row_h_mult)

    eff_width_ratio = max(0.25, min(0.95, float(playlist_width_ratio or 0.47)))
    usable_width = int(width * eff_width_ratio)
    if template == "Minimal" and (playlist_width_ratio is None or abs(float(playlist_width_ratio) - 0.47) < 0.01):
        usable_width = int(width * 0.39)

    norm_pos = playlist_position.strip().capitalize()
    if playlist_col_spacing is not None and playlist_col_spacing > 0:
        col_gap = max(10, int(playlist_col_spacing * res_scale))
    else:
        col_gap = max(24, int(width * 0.032))

    if norm_pos == "Center":
        max_total_w = min(int(width * 0.90), usable_width)
    elif norm_pos == "Right":
        right_edge = width - margin + int(playlist_x_offset * res_scale)
        min_left = max(margin, right_edge - usable_width)
        max_total_w = right_edge - min_left
    else:  # Left
        base_left = int(width * (0.50 if template == "Minimal" else 0.065)) + int(playlist_x_offset * res_scale)
        max_total_w = min(usable_width, width - margin - base_left)

    min_single_col_w = max(int(width * 0.12), int(base_eff_sz * 5))
    min_3_col_w = 3 * min_single_col_w + 2 * col_gap

    is_multi_col_template = norm_template in ("two-column", "two column", "2-column")
    if playlist_columns >= 2:
        desired_cols = playlist_columns
    else:
        # Check if single column fits vertically without overflowing (only for non-two-column templates)
        needed_h_1 = (n_tracks - 1) * int(base_eff_sz * 1.25) + init_row_h
        if not is_multi_col_template and n_tracks <= 8 and needed_h_1 <= avail_h:
            desired_cols = 1
        else:
            # Multi-column required: evaluate 2 vs 3 columns
            per_col_2 = (n_tracks + 1) // 2
            needed_h_2 = (per_col_2 - 1) * int(base_eff_sz * 1.25) + init_row_h
            can_fit_3_horiz = (max_total_w >= min_3_col_w)

            if needed_h_2 > avail_h and can_fit_3_horiz:
                desired_cols = 3
            elif can_fit_3_horiz and (n_tracks >= 15 or (n_tracks >= 12 and (eff_width_ratio >= 0.60 or norm_pos == "Center" or is_multi_col_template))):
                desired_cols = 3
            else:
                desired_cols = 2

    num_cols = max(1, min(4, min(desired_cols, n_tracks)))
    per_col = (n_tracks + num_cols - 1) // num_cols

    # Compute optimal font size, vertical spacing, and horizontal title fitting
    eff_track_size = max(12, int(track_font_size * res_scale))
    spacing = float(playlist_row_spacing or 1.85)
    min_readable_sz = max(11, int(track_font_size * 0.70 * res_scale))

    # 1. Vertical space optimization
    while spacing > 1.20:
        rg = int(eff_track_size * spacing)
        rh = int(eff_track_size * row_h_mult)
        if (per_col - 1) * rg + rh <= avail_h:
            break
        spacing -= 0.05

    while eff_track_size > min_readable_sz:
        rg = int(eff_track_size * max(1.18, spacing))
        rh = int(eff_track_size * row_h_mult)
        if (per_col - 1) * rg + rh <= avail_h:
            break
        eff_track_size -= 1
        spacing = max(1.18, spacing - 0.03)

    # 2. Horizontal title measurement & preservation
    def _measure_cols(fnt, sz):
        ipad = int(width * 0.014) + int(sz * 0.45)
        needed = []
        for c in range(num_cols):
            s_idx = c * per_col
            e_idx = min((c + 1) * per_col, n_tracks)
            cands = []
            for idx in range(s_idx, e_idx):
                raw = f"{idx + 1:02d}. {track_titles[idx]}"
                if track_max_chars > 0 and len(raw) > track_max_chars:
                    raw = raw[:track_max_chars].rstrip() + "…"
                cands.append(raw)
            if cands:
                max_w = max((fnt.getbbox(cand)[2] - fnt.getbbox(cand)[0] for cand in cands), default=100)
            else:
                max_w = 100
            min_w = max(int(width * 0.12), int(sz * 5))
            needed.append(max(min_w, max_w + ipad * 2))
        return needed, ipad

    cur_font = _get_font(track_font_family, track_font_style, eff_track_size)
    col_needed_w, ind_pad = _measure_cols(cur_font, eff_track_size)
    total_needed_w = sum(col_needed_w) + (num_cols - 1) * col_gap

    # If titles slightly exceed available width, gently scale down font size so complete titles fit:
    while total_needed_w > max_total_w and eff_track_size > min_readable_sz:
        eff_track_size -= 1
        cur_font = _get_font(track_font_family, track_font_style, eff_track_size)
        col_needed_w, ind_pad = _measure_cols(cur_font, eff_track_size)
        total_needed_w = sum(col_needed_w) + (num_cols - 1) * col_gap

    row_font = cur_font
    row_gap = int(eff_track_size * max(1.18, spacing))
    row_height = int(eff_track_size * row_h_mult)

    # 3. Determine actual column widths
    if total_needed_w <= max_total_w:
        col_actual_w = list(col_needed_w)
    else:
        # Extraordinarily long titles exceed boundary: clamp per-column to fair share so no columns are pushed off-grid
        avail_content_w = max_total_w - (num_cols - 1) * col_gap
        fair_share = avail_content_w // num_cols
        col_actual_w = [min(w, fair_share) for w in col_needed_w]

    # 4. Calculate Column X Positions for all columns
    col_x = [0] * num_cols
    if norm_pos == "Center":
        total_w = sum(col_actual_w) + (num_cols - 1) * col_gap
        start_x = (width - total_w) // 2 + int(playlist_x_offset * res_scale)
        col_x[0] = start_x
        for c in range(1, num_cols):
            col_x[c] = col_x[c - 1] + col_actual_w[c - 1] + col_gap
    elif norm_pos == "Right":
        col_x[num_cols - 1] = right_edge - col_actual_w[num_cols - 1]
        for c in range(num_cols - 2, -1, -1):
            col_x[c] = col_x[c + 1] - col_gap - col_actual_w[c]
    else:  # Left
        col_x[0] = base_left
        for c in range(1, num_cols):
            col_x[c] = col_x[c - 1] + col_actual_w[c - 1] + col_gap

    # 5. Build Track Items with Multi-line Wrapping & Word-boundary Ellipsis
    track_items = []
    positions: List[Tuple[int, int, int, int]] = []

    for i, title in enumerate(track_titles):
        col = i // per_col
        row = i % per_col
        x = col_x[col]
        curr_w = col_actual_w[col]
        y = playlist_y + row * row_gap
        box = (x, y - int(eff_track_size * 0.15), x + curr_w, y + row_height)
        positions.append(box)

        prefix = f"{i + 1:02d}. "
        raw_text = f"{prefix}{title}"
        if track_max_chars > 0 and len(raw_text) > track_max_chars:
            raw_text = raw_text[:track_max_chars].rstrip() + "…"

        max_text_w = curr_w - ind_pad
        bb = row_font.getbbox(raw_text)
        text_w = bb[2] - bb[0]

        if text_w <= max_text_w:
            display_text = raw_text
        elif track_wrap_text:
            words = title.split()
            line1_words = []
            line2_words = []
            for w_word in words:
                test_l = prefix + " ".join(line1_words + [w_word])
                if (row_font.getbbox(test_l)[2] - row_font.getbbox(test_l)[0]) <= max_text_w or not line1_words:
                    line1_words.append(w_word)
                else:
                    line2_words.append(w_word)
            line1 = prefix + " ".join(line1_words)
            indent = "    "
            if line2_words:
                line2 = indent + " ".join(line2_words)
                if (row_font.getbbox(line2)[2] - row_font.getbbox(line2)[0]) > max_text_w:
                    while len(line2_words) > 1:
                        line2_words.pop()
                        line2 = indent + " ".join(line2_words) + "…"
                        if (row_font.getbbox(line2)[2] - row_font.getbbox(line2)[0]) <= max_text_w:
                            break
                display_text = f"{line1}\n{line2}"
            else:
                display_text = line1
        else:
            words = title.split()
            candidate = raw_text
            while len(words) > 1:
                words.pop()
                candidate = prefix + " ".join(words) + "…"
                if (row_font.getbbox(candidate)[2] - row_font.getbbox(candidate)[0]) <= max_text_w:
                    break
            if (row_font.getbbox(candidate)[2] - row_font.getbbox(candidate)[0]) > max_text_w:
                cand_title = title
                while len(cand_title) > 2:
                    cand_title = cand_title[:-1].rstrip()
                    candidate = prefix + cand_title + "…"
                    if (row_font.getbbox(candidate)[2] - row_font.getbbox(candidate)[0]) <= max_text_w:
                        break
            display_text = candidate

        track_items.append({
            "index": i,
            "box": box,
            "x": x,
            "y": y,
            "text": display_text,
        })

    max_y2 = max((b[3] for b in positions), default=0)
    overflow = max_y2 > (height - int(height * 0.02))
    max_disp = sum(1 for b in positions if b[3] <= height)

    return {
        "track_items": track_items,
        "positions": positions,
        "is_two_col": num_cols >= 2,
        "num_cols": num_cols,
        "row_font": row_font,
        "eff_track_size": eff_track_size,
        "row_gap": row_gap,
        "row_height": row_height,
        "overflow": overflow,
        "max_displayable": max_disp,
        "col_widths": col_actual_w,
        "col_0_width": col_actual_w[0] if col_actual_w else 0,
        "col_1_width": col_actual_w[1] if len(col_actual_w) > 1 else 0,
        "col_gap": col_gap,
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
) -> str:
    """
    Generate an intro title card image featuring the collection title and logo presentation.
    Returns the file path to intro_card.png.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if background_path and Path(background_path).is_file():
        bg = _cover(Image.open(background_path), (width, height)).convert("RGBA")
    else:
        bg = Image.new("RGBA", (width, height), (23, 28, 26, 255))

    # A darker, cinematic wash for the intro
    wash = Image.new("RGBA", bg.size, (0, 0, 0, 110))
    bg = Image.alpha_composite(bg, wash)
    draw = ImageDraw.Draw(bg, "RGBA")

    res_scale = height / 1080.0
    eff_title_size = max(22, int(title_font_size * res_scale * 1.15))
    title_font = _get_font(title_font_family, title_font_style, eff_title_size)

    # Centered Logo Presentation
    logo_bottom = int(height * 0.42)
    if logo_path and Path(logo_path).is_file():
        try:
            with Image.open(logo_path) as logo_src:
                logo = clean_logo_image(logo_src).convert("RGBA")
                max_w, max_h = int(width * 0.24), int(height * 0.22)
                logo.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                lx = (width - logo.width) // 2
                ly = int(height * 0.20)
                bg.alpha_composite(logo, (lx, ly))
                logo_bottom = ly + logo.height
        except Exception:
            pass

    # Decorative Rule / Header Backing & Title on Dedicated Alpha Layer
    card_w = int(width * 0.72)
    card_h = int(height * 0.22)
    card_x = (width - card_w) // 2
    card_y = logo_bottom + int(height * 0.04)

    card_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(card_layer, "RGBA")

    c_draw.rounded_rectangle(
        (card_x, card_y, card_x + card_w, card_y + card_h),
        radius=int(height * 0.015),
        fill=(0, 0, 0, 80),
        outline=(255, 255, 255, 30),
        width=max(1, int(width * 0.001)),
    )

    # Centered Collection Title
    title_bbox = c_draw.textbbox((0, 0), collection_title, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    title_h = title_bbox[3] - title_bbox[1]
    tx = (width - title_w) // 2
    ty = card_y + (card_h - title_h) // 2
    _draw_text_with_outline_and_shadow(
        draw=c_draw,
        xy=(tx, ty),
        text=collection_title,
        font=title_font,
        fill=(255, 255, 250, 255),
        stroke_width=max(0, int(height * 0.0015)),
        stroke_fill=(0, 0, 0, 120),
        shadow=True,
        shadow_offset=(max(1, int(2 * res_scale)), max(1, int(2 * res_scale))),
        shadow_fill=(0, 0, 0, 140),
    )
    bg = Image.alpha_composite(bg, card_layer)

    # Optional Website Address at bottom center
    web_op = max(0.0, min(1.0, float(website_opacity if website_opacity is not None else 1.0)))
    if website_text.strip() and website_show and web_op > 0.0:
        web_size = max(12, int(20 * res_scale))
        web_font = _get_font("Segoe UI", "Regular", web_size)
        wb = draw.textbbox((0, 0), website_text.strip(), font=web_font)
        ww = wb[2] - wb[0]
        wx = (width - ww) // 2
        wy = int(height * 0.88)
        web_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        w_draw = ImageDraw.Draw(web_layer, "RGBA")
        w_draw.text((wx, wy), website_text.strip(), font=web_font, fill=(220, 228, 222, int(200 * web_op)))
        bg = Image.alpha_composite(bg, web_layer)

    intro_path = str(out / "intro_card.png")
    bg.save(intro_path)
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
) -> tuple[str, list[str]]:
    """
    Return base composition PNG path and per-track cursor/highlight overlay PNG paths.
    Supports adjustable layout, multi-column playlists, transparent/semi-opaque backgrounds,
    active-track styling, typography outlines/shadows, and logo background cleanup.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    mode = indicator_mode.lower() if indicator_mode in INDICATOR_MODES else "both"
    show_highlight = mode in ("both", "highlight_only")
    show_cursor = mode in ("both", "cursor_only")

    # 1. Base Composition Image
    if background_path and Path(background_path).is_file():
        bg = _cover(Image.open(background_path), (width, height)).convert("RGBA")
    else:
        bg = Image.new("RGBA", (width, height), (23, 28, 26, 255))

    # A subtle dark wash protects text legibility over diverse backgrounds
    wash = Image.new("RGBA", bg.size, (0, 0, 0, 50))
    bg = Image.alpha_composite(bg, wash)
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
        web_font = _get_font("Segoe UI", "Regular", eff_web_size)
        wb = draw.textbbox((0, 0), web_text_clean, font=web_font)
        tw = wb[2] - wb[0]
        th = wb[3] - wb[1]
        pill_pad_x = int(eff_web_size * 0.45)
        pill_pad_y = int(eff_web_size * 0.25)
        total_w = tw + pill_pad_x * 2
        total_h = th + pill_pad_y * 2

        wx, wy = _calculate_corner_position(
            website_position, total_w, total_h, width, height, margin, int(height * 0.045)
        )

        # Overlap Prevention: avoid collision with logo in same corner
        if logo_placed and logo_rect is not None:
            norm_logo_pos = logo_position.strip().lower()
            norm_web_pos = website_position.strip().lower()
            if norm_logo_pos == norm_web_pos:
                lx1, ly1, lx2, ly2 = logo_rect
                if "bottom" in norm_web_pos:
                    wy = ly1 - total_h - int(height * 0.015)
                else:
                    wy = ly2 + int(height * 0.015)

        web_rect = (wx, wy, wx + total_w, wy + total_h)

        web_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        w_draw = ImageDraw.Draw(web_layer, "RGBA")
        pill_fill_a = int(120 * web_op)
        pill_outline_a = int(35 * web_op)
        w_draw.rounded_rectangle(
            web_rect,
            radius=max(3, int(eff_web_size * 0.3)),
            fill=(0, 0, 0, pill_fill_a),
            outline=(255, 255, 255, pill_outline_a),
            width=1,
        )
        _draw_text_with_outline_and_shadow(
            draw=w_draw,
            xy=(wx + pill_pad_x, wy + pill_pad_y),
            text=web_text_clean,
            font=web_font,
            fill=(238, 244, 239, int(245 * web_op)),
            stroke_width=1,
            stroke_fill=(0, 0, 0, int(140 * web_op)),
            shadow=True,
            shadow_offset=(1, 1),
            shadow_fill=(0, 0, 0, int(150 * web_op)),
        )
        bg = Image.alpha_composite(bg, web_layer)
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
        )

        title_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        t_draw = ImageDraw.Draw(title_layer, "RGBA")

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

        for (lx, ly), line_txt in zip(line_coords, title_lines):
            _draw_text_with_outline_and_shadow(
                draw=t_draw,
                xy=(lx, ly),
                text=line_txt,
                font=title_font,
                fill=(*title_rgb, 255),
                stroke_width=t_stroke_w,
                stroke_fill=(*title_stroke_rgb, 120),
                shadow=title_shadow,
                shadow_offset=(max(1, int(2 * res_scale)), max(1, int(2 * res_scale))),
                shadow_fill=(0, 0, 0, 140),
            )

        bg = Image.alpha_composite(bg, title_layer)
        draw = ImageDraw.Draw(bg, "RGBA")

    # 5. Dynamic Playlist Geometry & Fit-to-Frame Auto-Column Placement
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
        title_bottom_y=title_bottom_y if (render_title and norm_title_pos == "Above Playlist") else 0,
        website_rect=web_rect,
        playlist_col_spacing=playlist_col_spacing,
        track_max_chars=track_max_chars,
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
        base_draw = ImageDraw.Draw(base, "RGBA")

    has_overlays = (mode != "neither") and (show_highlight or show_cursor) and bool(track_items)

    # If neither cursor nor highlight is requested, render tracks on base and return 0 overlays
    if not has_overlays:
        tracks_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        tr_draw = ImageDraw.Draw(tracks_layer, "RGBA")
        for item in track_items:
            _draw_text_with_outline_and_shadow(
                draw=tr_draw,
                xy=(item["x"] + int(width * 0.006), item["y"]),
                text=item["text"],
                font=row_font,
                fill=(*track_rgb, 245),
                stroke_width=t_outline_w,
                stroke_fill=(*track_stroke_rgb, 120),
                shadow=track_shadow,
                shadow_offset=(max(1, int(1 * res_scale)), max(1, int(1 * res_scale))),
                shadow_fill=(0, 0, 0, 140),
            )
        base = Image.alpha_composite(base, tracks_layer)
        base_path = str(out / "composition.png")
        base.save(base_path)
        return base_path, []

    # When overlays are enabled, save base without playlist text to avoid duplicate/ghosted rendering
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

        # Moving highlight
        if show_highlight:
            pad_x = int(width * 0.006)
            hl_box = (x1 - pad_x, y1, x2, y2)

            if norm_hl_style == "Accent Bar":
                # Clean vertical bar on left edge
                bar_w = max(4, int(width * 0.0035))
                od.rounded_rectangle(
                    (x1 - pad_x, y1, x1 - pad_x + bar_w, y2),
                    radius=max(1, bar_w // 2),
                    fill=(*hl_rgb, 255),
                )
                # Subtle row tint
                od.rounded_rectangle(hl_box, radius=max(2, int(eff_track_size * 0.18)), fill=(*hl_rgb, max(15, hl_alpha // 2)))

            elif norm_hl_style == "Outline":
                # Crisp border outline only
                od.rounded_rectangle(
                    hl_box,
                    radius=max(2, int(eff_track_size * 0.18)),
                    outline=(*hl_rgb, 255),
                    fill=(*hl_rgb, 0),
                    width=max(2, int(width * 0.0015)),
                )

            elif norm_hl_style == "Underline":
                # Bottom indicator line positioned cleanly under active track baseline
                tb = od.textbbox((active_item["x"] + int(width * 0.006), active_item["y"]), active_item["text"], font=row_font)
                line_y = tb[3] + max(3, int(4 * res_scale))
                line_h = max(2, int(height * 0.0025))
                od.rounded_rectangle(
                    (x1, line_y, min(x2, tb[2] + int(width * 0.015)), line_y + line_h),
                    radius=1,
                    fill=(*hl_rgb, 255),
                )

            else:  # "Pill" (default)
                od.rounded_rectangle(
                    hl_box,
                    radius=max(2, int(eff_track_size * 0.18)),
                    outline=(*hl_rgb, 255),
                    fill=(*hl_rgb, hl_alpha),
                    width=max(1, int(width * 0.0015)),
                )

        # Cursor
        if show_cursor:
            cy = (y1 + y2) // 2
            if custom_cursor_img is not None:
                cw, ch = custom_cursor_img.size
                cx = max(4, x1 - cw - int(width * 0.008))
                overlay.alpha_composite(custom_cursor_img, (cx, cy - ch // 2))
            else:
                arrow_w = target_cursor_dim
                arrow_h = target_cursor_dim
                arrow_x = max(4, x1 - int(width * 0.016) - arrow_w)
                arrow = [
                    (arrow_x, cy - arrow_h // 2),
                    (arrow_x + arrow_w, cy),
                    (arrow_x, cy + arrow_h // 2),
                ]
                od.polygon(arrow, fill=(*hl_rgb, 255))

        # Render full tracklist on overlay in a single crisp pass
        active_rgb = _hex_to_rgb(active_track_color, track_rgb) if active_track_color else track_rgb
        for j, item in enumerate(track_items):
            is_active = (j == i)
            # Active track glyph fill is visually consistent with inactive tracks unless active_track_color is explicitly configured.
            # Highlight color styles the row indicator (Pill/Accent Bar/Outline/Underline) and cursor, never the text font.
            text_fill = (*active_rgb, 255) if is_active else (*track_rgb, 245)

            _draw_text_with_outline_and_shadow(
                draw=od,
                xy=(item["x"] + int(width * 0.006), item["y"]),
                text=item["text"],
                font=row_font,
                fill=text_fill,
                stroke_width=t_outline_w,
                stroke_fill=(*track_stroke_rgb, 120),
                shadow=track_shadow,
                shadow_offset=(max(1, int(1 * res_scale)), max(1, int(1 * res_scale))),
                shadow_fill=(0, 0, 0, 140),
            )

        op = str(out / f"cursor_{i:03d}.png")
        overlay.save(op)
        overlays.append(op)

    return base_path, overlays
