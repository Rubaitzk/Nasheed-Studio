"""Creates a clean base composition and transparent per-track cursor/highlight overlays."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageOps

from src.services.font_service import resolve_font_path

INDICATOR_MODES = ["both", "cursor_only", "highlight_only", "neither"]
CORNER_POSITIONS = ["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right"]


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
) -> tuple[str, list[str]]:
    """
    Return base composition PNG path and per-track cursor/highlight overlay PNG paths.
    Accurately scales typography, respects logo and website corner positions,
    and automatically shifts elements to prevent logo-website collision.
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

    # A restrained dark wash ensures text remains legible on varied images.
    wash = Image.new("RGBA", bg.size, (0, 0, 0, 65))
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
    row_gap = int(eff_track_size * 1.85)
    row_height = int(eff_track_size * 1.50)

    is_two_col = template == "Two-column"
    playlist_x = int(width * (0.56 if template == "Minimal" else 0.075))
    playlist_y = int(height * (0.25 if template == "Minimal" else 0.19))
    usable_width = int(width * (0.39 if template == "Minimal" else 0.47))
    if is_two_col:
        playlist_x = int(width * 0.06)
        playlist_y = int(height * 0.22)
        usable_width = int(width * 0.42)

    # Header backing subtly separates title from bright backgrounds.
    header_h = max(int(height * 0.095), int(eff_title_size * 1.8))
    draw.rounded_rectangle(
        (margin, int(height * 0.045), width - margin, int(height * 0.045) + header_h),
        radius=int(height * 0.012),
        fill=(0, 0, 0, 48),
    )
    title_bbox = draw.textbbox((0, 0), collection_title, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    draw.text(
        ((width - title_w) / 2, int(height * 0.045) + (header_h - (title_bbox[3] - title_bbox[1])) / 2),
        collection_title,
        font=title_font,
        fill=(255, 255, 248, 255),
        stroke_width=max(1, int(height * 0.0015)),
        stroke_fill=(0, 0, 0, 180),
    )

    # 2. Logo Placement & Sizing
    logo_placed = False
    logo_rect: Optional[Tuple[int, int, int, int]] = None
    if logo_path and Path(logo_path).is_file():
        try:
            with Image.open(logo_path) as logo_src:
                logo = logo_src.convert("RGBA")
                max_w, max_h = int(width * 0.13), int(height * 0.11)
                logo.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                lx, ly = _calculate_corner_position(
                    logo_position, logo.width, logo.height, width, height, margin, int(height * 0.045)
                )
                bg.alpha_composite(logo, (lx, ly))
                logo_rect = (lx, ly, lx + logo.width, ly + logo.height)
                logo_placed = True
        except Exception:
            pass

    # 3. Website Address Placement & Overlap Prevention
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
                # In Bottom corners: shift website ABOVE logo
                if "bottom" in norm_web_pos:
                    wy = ly1 - total_h - int(height * 0.015)
                # In Top corners: shift website BELOW logo
                else:
                    wy = ly2 + int(height * 0.015)

        # Draw website watermark pill & text
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

    base = bg.copy()
    base_draw = ImageDraw.Draw(base, "RGBA")
    positions: list[tuple[int, int, int, int]] = []

    for i, title in enumerate(track_titles):
        col = 0
        row = i
        if is_two_col:
            per_col = (len(track_titles) + 1) // 2
            col, row = divmod(i, per_col)
        x = playlist_x + col * int(width * 0.46)
        y = playlist_y + row * row_gap
        text = f"{i + 1:02d}. {title}"
        box = (x, y - int(eff_track_size * 0.15), x + usable_width, y + row_height)
        positions.append(box)
        # Dark translucent strip keeps the list readable without dominating the art.
        base_draw.rounded_rectangle(box, radius=max(2, int(eff_track_size * 0.15)), fill=(0, 0, 0, 92))
        base_draw.text((x + int(width * 0.006), y), text, font=row_font, fill=(242, 243, 231, 245))

    base_path = str(out / "composition.png")
    base.save(base_path)

    # If neither cursor nor highlight is requested, return base with 0 overlays
    if mode == "neither" or (not show_highlight and not show_cursor):
        return base_path, []

    # 4. Prepare Cursor asset if enabled
    custom_cursor_img: Optional[Image.Image] = None
    target_cursor_dim = max(12, int(cursor_size * res_scale))

    if show_cursor and cursor_path and Path(cursor_path).is_file():
        try:
            custom_cursor_img = load_cursor_image(cursor_path, target_cursor_dim)
        except Exception:
            custom_cursor_img = None

    # 5. Generate Overlays
    overlays: list[str] = []
    indices_to_render = [0] if (preview_only_first_overlay and positions) else range(len(positions))

    for i in indices_to_render:
        box = positions[i]
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay, "RGBA")
        x1, y1, x2, y2 = box

        # Moving highlight
        if show_highlight:
            od.rounded_rectangle(
                (x1 - int(width * 0.006), y1 - int(eff_track_size * 0.2), x2, y2 + int(eff_track_size * 0.1)),
                radius=max(2, int(eff_track_size * 0.18)),
                outline=(248, 220, 139, 255),
                fill=(255, 211, 92, 42),
                width=max(2, int(width * 0.0015)),
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
                od.polygon(arrow, fill=(255, 222, 126, 255))

        op = str(out / f"cursor_{i:03d}.png")
        overlay.save(op)
        overlays.append(op)

    return base_path, overlays
