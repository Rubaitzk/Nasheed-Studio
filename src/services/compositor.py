"""Creates a clean base composition and transparent per-track cursor/highlight overlays."""
from __future__ import annotations

from collections import deque
import os
from pathlib import Path
from typing import Optional, Tuple, Union
from PIL import Image, ImageDraw, ImageFont, ImageOps

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
    stroke_fill: tuple = (0, 0, 0, 180),
    shadow: bool = False,
    shadow_offset: tuple[int, int] = (2, 2),
    shadow_fill: tuple = (0, 0, 0, 160),
) -> None:
    """Draw text with optional subtle drop-shadow and crisp outline stroke for legibility."""
    x, y = xy
    if shadow:
        sx, sy = shadow_offset
        draw.text((x + sx, y + sy), text, font=font, fill=shadow_fill)
    draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)


def clean_logo_image(img: Image.Image, mode: str = "auto") -> Image.Image:
    """
    Remove solid white or checkerboard backgrounds from logo images while preserving inner graphics.
    Uses edge-connected flood-fill so white text or internal highlights are never erased.
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
        # Already has transparent corners
        return rgba

    def is_white_bg(r: int, g: int, b: int) -> bool:
        return r >= 232 and g >= 232 and b >= 232 and abs(r - g) <= 14 and abs(g - b) <= 14

    def is_checker_bg(r: int, g: int, b: int) -> bool:
        is_grey = (180 <= r <= 222 and 180 <= g <= 222 and 180 <= b <= 222 and abs(r - g) <= 8 and abs(g - b) <= 8)
        is_white = (r >= 232 and g >= 232 and b >= 232 and abs(r - g) <= 12 and abs(g - b) <= 12)
        return is_white or is_grey

    is_bg_fn = is_white_bg
    if mode == "remove_checkerboard":
        is_bg_fn = is_checker_bg
    elif mode == "auto":
        # Detect if corners alternate as checkerboard or solid white
        grey_corners = sum(1 for r, g, b, _ in corners if 180 <= r <= 222 and abs(r - g) <= 8)
        white_corners = sum(1 for r, g, b, _ in corners if is_white_bg(r, g, b))
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
            if is_bg_fn(r, g, b) and (x, y) not in visited:
                q.append((x, y))
                visited.add((x, y))

    for y in range(h):
        for x in (0, w - 1):
            if (x, y) not in visited:
                r, g, b, a = px[x, y]
                if is_bg_fn(r, g, b):
                    q.append((x, y))
                    visited.add((x, y))

    while q:
        cx, cy = q.popleft()
        m_px[cx, cy] = 0
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                r, g, b, a = px[nx, ny]
                if is_bg_fn(r, g, b):
                    visited.add((nx, ny))
                    q.append((nx, ny))

    rgba.putalpha(mask)
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


def load_cursor_image(cursor_path: str, target_dim: int) -> Image.Image:
    """Load, validate, and resize a custom SVG or raster cursor into an RGBA PIL Image."""
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
                src_rgba = src.convert("RGBA")
                return ImageOps.contain(src_rgba, (target_dim, target_dim), method=Image.Resampling.LANCZOS)
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
                logo = logo_src.convert("RGBA")
                max_w, max_h = int(width * 0.24), int(height * 0.22)
                logo.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                lx = (width - logo.width) // 2
                ly = int(height * 0.20)
                bg.alpha_composite(logo, (lx, ly))
                logo_bottom = ly + logo.height
        except Exception:
            pass

    # Decorative Rule / Header Backing
    card_w = int(width * 0.72)
    card_h = int(height * 0.22)
    card_x = (width - card_w) // 2
    card_y = logo_bottom + int(height * 0.04)

    draw.rounded_rectangle(
        (card_x, card_y, card_x + card_w, card_y + card_h),
        radius=int(height * 0.015),
        fill=(0, 0, 0, 80),
        outline=(255, 255, 255, 30),
        width=max(1, int(width * 0.001)),
    )

    # Centered Collection Title
    title_bbox = draw.textbbox((0, 0), collection_title, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    title_h = title_bbox[3] - title_bbox[1]
    tx = (width - title_w) // 2
    ty = card_y + (card_h - title_h) // 2
    draw.text(
        (tx, ty),
        collection_title,
        font=title_font,
        fill=(255, 255, 250, 255),
        stroke_width=max(1, int(height * 0.002)),
        stroke_fill=(0, 0, 0, 210),
    )

    # Optional Website Address at bottom center
    if website_text.strip():
        web_size = max(12, int(20 * res_scale))
        web_font = _get_font("Segoe UI", "Regular", web_size)
        wb = draw.textbbox((0, 0), website_text.strip(), font=web_font)
        ww = wb[2] - wb[0]
        wx = (width - ww) // 2
        wy = int(height * 0.88)
        draw.text((wx, wy), website_text.strip(), font=web_font, fill=(220, 228, 222, 200))

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
    playlist_position: str = "Left",
    playlist_x_offset: int = 0,
    playlist_y_offset: int = 0,
    playlist_width_ratio: float = 0.47,
    playlist_columns: int = 1,
    playlist_row_spacing: float = 1.85,
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

    eff_title_size = max(14, int(title_font_size * res_scale))
    eff_track_size = max(10, int(track_font_size * res_scale))

    title_font = _get_font(title_font_family, title_font_style, eff_title_size)
    row_font = _get_font(track_font_family, track_font_style, eff_track_size)

    # Dynamic row geometry based on track font size
    spacing_mult = max(1.2, float(playlist_row_spacing or 1.85))
    row_gap = int(eff_track_size * spacing_mult)
    row_height = int(eff_track_size * 1.50)

    # 2. Determine Columns and Playlist Geometry
    is_two_col = (template == "Two-column") or (playlist_columns == 2)
    eff_width_ratio = max(0.25, min(0.90, float(playlist_width_ratio or 0.47)))
    usable_width = int(width * eff_width_ratio)
    if template == "Minimal":
        usable_width = int(width * 0.39)

    # Playlist X / Y Placement
    norm_pos = playlist_position.strip().capitalize()
    if norm_pos == "Center":
        base_px = (width - usable_width) // 2
    elif norm_pos == "Right":
        base_px = width - usable_width - margin
    else:  # Left
        base_px = int(width * (0.56 if template == "Minimal" else 0.075))

    playlist_x = base_px + int(playlist_x_offset * res_scale)
    playlist_y = int(height * (0.25 if template == "Minimal" else 0.19)) + int(playlist_y_offset * res_scale)

    if is_two_col:
        col_gap = int(width * 0.04)
        single_col_w = (usable_width - col_gap) // 2
    else:
        single_col_w = usable_width

    # 3. Collection Title Placement & Typography
    col_title_clean = collection_title.strip()
    norm_title_pos = title_position.strip()
    render_title = title_show and bool(col_title_clean) and (norm_title_pos != "Hidden")

    if render_title:
        title_rgb = _hex_to_rgb(title_color, (255, 255, 248))
        title_stroke_rgb = _hex_to_rgb(title_outline_color, (0, 0, 0))
        t_stroke_w = max(0, int(title_outline_width * res_scale)) if title_outline_width else 0

        tb = draw.textbbox((0, 0), col_title_clean, font=title_font)
        tw = tb[2] - tb[0]
        th = tb[3] - tb[1]

        if norm_title_pos == "Above Playlist":
            tx = playlist_x
            ty = max(int(height * 0.03), playlist_y - th - int(title_margin * res_scale) - 15)
        elif norm_title_pos == "Top-Left":
            tx = margin
            ty = int(height * 0.045)
        else:  # "Top-Center" (default)
            tx = (width - tw) // 2
            ty = int(height * 0.045)

        # Header backing: draw only if not completely transparent
        if playlist_bg_opacity > 0.1:
            header_h = max(int(height * 0.08), th + 16)
            bg_rgb = _hex_to_rgb(playlist_bg_color, (0, 0, 0))
            bg_alpha = int(255 * min(1.0, playlist_bg_opacity * 0.7))
            draw.rounded_rectangle(
                (tx - 16, ty - 6, tx + tw + 16, ty + th + 10),
                radius=max(3, int(playlist_bg_radius * res_scale)),
                fill=(*bg_rgb, bg_alpha),
            )

        _draw_text_with_outline_and_shadow(
            draw=draw,
            xy=(tx, ty),
            text=col_title_clean,
            font=title_font,
            fill=(*title_rgb, 255),
            stroke_width=t_stroke_w if t_stroke_w > 0 else max(1, int(height * 0.0015)),
            stroke_fill=(*title_stroke_rgb, 180),
            shadow=title_shadow,
            shadow_offset=(max(1, int(2 * res_scale)), max(1, int(2 * res_scale))),
            shadow_fill=(0, 0, 0, 160),
        )

    # 4. Logo Placement & Background Cleanup
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

    # 5. Website Address Placement & Overlap Prevention
    web_text_clean = website_text.strip()
    if web_text_clean:
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

        # Overlap Prevention: Check collision with logo
        if logo_placed and logo_rect is not None:
            norm_logo_pos = logo_position.strip().lower()
            norm_web_pos = website_position.strip().lower()
            if norm_logo_pos == norm_web_pos:
                lx1, ly1, lx2, ly2 = logo_rect
                if "bottom" in norm_web_pos:
                    wy = ly1 - total_h - int(height * 0.015)
                else:
                    wy = ly2 + int(height * 0.015)

        draw.rounded_rectangle(
            (wx, wy, wx + total_w, wy + total_h),
            radius=max(3, int(eff_web_size * 0.3)),
            fill=(0, 0, 0, 110),
            outline=(255, 255, 255, 25),
            width=1,
        )
        draw.text(
            (wx + pill_pad_x, wy + pill_pad_y),
            web_text_clean,
            font=web_font,
            fill=(238, 244, 239, 235),
            stroke_width=1,
            stroke_fill=(0, 0, 0, 140),
        )

    # 6. Playlist Track Layout & Base Rendering
    base = bg.copy()
    base_draw = ImageDraw.Draw(base, "RGBA")
    positions: list[tuple[int, int, int, int]] = []

    track_rgb = _hex_to_rgb(track_color, (242, 243, 231))
    track_stroke_rgb = _hex_to_rgb(track_outline_color, (0, 0, 0))
    t_outline_w = max(0, int(track_outline_width * res_scale)) if track_outline_width else 0
    bg_panel_rgb = _hex_to_rgb(playlist_bg_color, (0, 0, 0))
    bg_panel_alpha = int(255 * max(0.0, min(1.0, float(playlist_bg_opacity or 0.0))))

    per_col = (len(track_titles) + 1) // 2 if is_two_col else len(track_titles)

    for i, title in enumerate(track_titles):
        if is_two_col:
            col, row = divmod(i, per_col)
            x = playlist_x + col * (single_col_w + int(width * 0.04))
            w_col = single_col_w
        else:
            col, row = 0, i
            x = playlist_x
            w_col = usable_width

        y = playlist_y + row * row_gap
        box = (x, y - int(eff_track_size * 0.15), x + w_col, y + row_height)
        positions.append(box)

        # Draw translucent panel/row backing if requested
        if bg_panel_alpha > 0:
            base_draw.rounded_rectangle(
                box,
                radius=max(2, int(playlist_bg_radius * res_scale)),
                fill=(*bg_panel_rgb, bg_panel_alpha),
                outline=(255, 255, 255, 18) if bg_panel_alpha > 80 else None,
                width=1,
            )

        # Track text formatting
        raw_text = f"{i + 1:02d}. {title}"
        display_text = raw_text
        if not track_wrap_text:
            # Ellipsize if text exceeds available column width
            max_text_w = w_col - int(width * 0.015)
            bb = base_draw.textbbox((0, 0), display_text, font=row_font)
            if (bb[2] - bb[0]) > max_text_w:
                while len(display_text) > 5:
                    display_text = display_text[:-2]
                    bb = base_draw.textbbox((0, 0), display_text + "…", font=row_font)
                    if (bb[2] - bb[0]) <= max_text_w:
                        display_text += "…"
                        break

        _draw_text_with_outline_and_shadow(
            draw=base_draw,
            xy=(x + int(width * 0.006), y),
            text=display_text,
            font=row_font,
            fill=(*track_rgb, 245),
            stroke_width=t_outline_w if t_outline_w > 0 else 1,
            stroke_fill=(*track_stroke_rgb, 140),
            shadow=track_shadow,
            shadow_offset=(max(1, int(1 * res_scale)), max(1, int(1 * res_scale))),
            shadow_fill=(0, 0, 0, 160),
        )

    base_path = str(out / "composition.png")
    base.save(base_path)

    # If neither cursor nor highlight is requested, return base with 0 overlays
    if mode == "neither" or (not show_highlight and not show_cursor):
        return base_path, []

    # 7. Prepare Custom Cursor asset if enabled
    custom_cursor_img: Optional[Image.Image] = None
    target_cursor_dim = max(12, int(cursor_size * res_scale))

    if show_cursor and cursor_path and Path(cursor_path).is_file():
        try:
            custom_cursor_img = load_cursor_image(cursor_path, target_cursor_dim)
        except Exception:
            custom_cursor_img = None

    # 8. Generate Per-Track Overlays (Highlight & Cursor)
    overlays: list[str] = []
    indices_to_render = [0] if (preview_only_first_overlay and positions) else range(len(positions))

    hl_rgb = _hex_to_rgb(highlight_color, (248, 220, 139))
    hl_alpha = int(255 * max(0.05, min(1.0, float(highlight_bg_opacity or 0.25))))
    norm_hl_style = highlight_style.strip().title()

    for i in indices_to_render:
        box = positions[i]
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay, "RGBA")
        x1, y1, x2, y2 = box

        # Moving highlight
        if show_highlight:
            pad_x = int(width * 0.006)
            hl_box = (x1 - pad_x, y1 - int(eff_track_size * 0.2), x2, y2 + int(eff_track_size * 0.1))

            if norm_hl_style == "Accent Bar":
                # Clean vertical bar on left edge
                bar_w = max(4, int(width * 0.0035))
                od.rounded_rectangle(
                    (x1 - pad_x, y1 - int(eff_track_size * 0.1), x1 - pad_x + bar_w, y2 + int(eff_track_size * 0.05)),
                    radius=max(1, bar_w // 2),
                    fill=(*hl_rgb, 255),
                )
                # Subtle row tint
                od.rounded_rectangle(hl_box, radius=max(2, int(eff_track_size * 0.18)), fill=(*hl_rgb, hl_alpha // 2))

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
                # Bottom indicator line
                line_h = max(2, int(height * 0.003))
                od.rounded_rectangle(
                    (x1 - pad_x, y2, x2, y2 + line_h),
                    radius=1,
                    fill=(*hl_rgb, 255),
                )

            else:  # "Pill" (default)
                od.rounded_rectangle(
                    hl_box,
                    radius=max(2, int(eff_track_size * 0.18)),
                    outline=(*hl_rgb, 255),
                    fill=(*hl_rgb, hl_alpha),
                    width=max(2, int(width * 0.0015)),
                )

            # Re-draw the active track title in high-contrast active color on the overlay
            # so active title stands out prominently even with a 100% transparent background!
            raw_title = f"{i + 1:02d}. {track_titles[i]}"
            disp_title = raw_title
            w_avail = (x2 - x1) - int(width * 0.015)
            bb = od.textbbox((0, 0), disp_title, font=row_font)
            if (bb[2] - bb[0]) > w_avail:
                while len(disp_title) > 5:
                    disp_title = disp_title[:-2]
                    bb = od.textbbox((0, 0), disp_title + "…", font=row_font)
                    if (bb[2] - bb[0]) <= w_avail:
                        disp_title += "…"
                        break

            _draw_text_with_outline_and_shadow(
                draw=od,
                xy=(x1 + int(width * 0.006), (y1 + y2 - row_height) // 2 + int(eff_track_size * 0.15)),
                text=disp_title,
                font=row_font,
                fill=(*hl_rgb, 255),
                stroke_width=max(1, t_outline_w),
                stroke_fill=(0, 0, 0, 200),
                shadow=True,
                shadow_offset=(max(1, int(1 * res_scale)), max(1, int(1 * res_scale))),
                shadow_fill=(0, 0, 0, 180),
            )

        # Cursor
        if show_cursor:
            cy = (y1 + y2) // 2
            if custom_cursor_img is not None:
                cw, ch = custom_cursor_img.size
                cx = max(4, x1 - cw - int(width * 0.006))
                overlay.alpha_composite(custom_cursor_img, (cx, cy - ch // 2))
            else:
                arrow_w = target_cursor_dim
                arrow_h = target_cursor_dim
                arrow_x = max(4, x1 - int(width * 0.018))
                arrow = [
                    (arrow_x, cy - arrow_h // 2),
                    (arrow_x + arrow_w, cy),
                    (arrow_x, cy + arrow_h // 2),
                ]
                od.polygon(arrow, fill=(*hl_rgb, 255))

        op = str(out / f"cursor_{i:03d}.png")
        overlay.save(op)
        overlays.append(op)

    return base_path, overlays
