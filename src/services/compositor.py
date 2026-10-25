"""Creates a clean base composition and transparent per-track cursor/highlight overlays."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps

INDICATOR_MODES = ["both", "cursor_only", "highlight_only", "neither"]


def _font(size: int, bold: bool = False):
    candidates = []
    if os.name == "nt":
        candidates = [
            r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
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
                # Contain within target_dim x target_dim preserving aspect ratio
                return ImageOps.contain(src_rgba, (target_dim, target_dim), method=Image.Resampling.LANCZOS)
        except Exception as exc:
            raise ValueError(f"Could not decode cursor image {cursor_path}: {exc}")

    raise ValueError(f"Unsupported cursor file format: {suffix}. Supported formats: SVG, PNG, JPG, WEBP, BMP.")


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
) -> tuple[str, list[str]]:
    """
    Return base composition PNG path and per-track cursor/highlight overlay PNG paths.

    If indicator_mode == 'neither', an empty list of overlays is returned.
    If preview_only_first_overlay is True, only the first track overlay is written to disk.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    mode = indicator_mode.lower() if indicator_mode in INDICATOR_MODES else "both"
    show_highlight = mode in ("both", "highlight_only")
    show_cursor = mode in ("both", "cursor_only")

    # 1. Base Composition
    if background_path and Path(background_path).is_file():
        bg = _cover(Image.open(background_path), (width, height)).convert("RGBA")
    else:
        bg = Image.new("RGBA", (width, height), (23, 28, 26, 255))

    # A restrained dark wash ensures text remains legible on varied images.
    wash = Image.new("RGBA", bg.size, (0, 0, 0, 65))
    bg = Image.alpha_composite(bg, wash)
    draw = ImageDraw.Draw(bg, "RGBA")

    margin = int(width * 0.055)
    title_size = int(height * 0.043)
    row_size = int(height * (0.024 if len(track_titles) <= 12 else 0.018))
    row_gap = int(row_size * 1.75)
    row_height = int(row_size * 1.45)
    is_two_col = template == "Two-column"
    playlist_x = int(width * (0.56 if template == "Minimal" else 0.075))
    playlist_y = int(height * (0.25 if template == "Minimal" else 0.19))
    usable_width = int(width * (0.39 if template == "Minimal" else 0.47))
    if is_two_col:
        playlist_x = int(width * 0.06)
        playlist_y = int(height * 0.22)
        usable_width = int(width * 0.42)

    title_font = _font(title_size, True)
    row_font = _font(row_size, True)

    # Header backing subtly separates title from bright backgrounds.
    draw.rounded_rectangle(
        (margin, int(height * 0.045), width - margin, int(height * 0.14)),
        radius=int(height * 0.012),
        fill=(0, 0, 0, 48),
    )
    title_bbox = draw.textbbox((0, 0), collection_title, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    draw.text(
        ((width - title_w) / 2, int(height * 0.065)),
        collection_title,
        font=title_font,
        fill=(255, 255, 248, 255),
        stroke_width=max(1, int(height * 0.0015)),
        stroke_fill=(0, 0, 0, 180),
    )

    if logo_path and Path(logo_path).is_file():
        logo = Image.open(logo_path).convert("RGBA")
        max_w, max_h = int(width * 0.13), int(height * 0.11)
        logo.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        pos = (width - margin - logo.width, height - margin - logo.height)
        bg.alpha_composite(logo, pos)

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
        box = (x, y - int(row_size * 0.15), x + usable_width, y + row_height)
        positions.append(box)
        # Dark translucent strip keeps the list readable without dominating the art.
        base_draw.rounded_rectangle(box, radius=max(2, int(row_size * 0.12)), fill=(0, 0, 0, 92))
        base_draw.text((x + int(width * 0.006), y), text, font=row_font, fill=(242, 243, 231, 245))

    base_path = str(out / "composition.png")
    base.save(base_path)

    # If neither cursor nor highlight is requested, return base with 0 overlays
    if mode == "neither" or (not show_highlight and not show_cursor):
        return base_path, []

    # 2. Prepare Cursor asset if enabled
    custom_cursor_img: Optional[Image.Image] = None
    res_scale = height / 1080.0
    target_cursor_dim = max(12, int(cursor_size * res_scale))

    if show_cursor and cursor_path and Path(cursor_path).is_file():
        try:
            custom_cursor_img = load_cursor_image(cursor_path, target_cursor_dim)
        except Exception:
            custom_cursor_img = None

    # 3. Generate Overlays
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
                (x1 - int(width * 0.006), y1 - int(row_size * 0.2), x2, y2 + int(row_size * 0.1)),
                radius=max(2, int(row_size * 0.15)),
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
