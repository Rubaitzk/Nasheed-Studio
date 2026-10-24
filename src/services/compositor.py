"""Creates a clean base composition and transparent per-track cursor overlays."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


def _font(size: int, bold: bool = False):
    candidates = []
    if __import__("os").name == "nt":
        candidates = [r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
                      r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf"]
    else:
        candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def create_composition(width: int, height: int, background_path: str, logo_path: str | None,
                       collection_title: str, track_titles: list[str], template: str, out_dir: str):
    """Return base PNG path and cursor overlay PNG paths, one per track."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if background_path:
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
    draw.rounded_rectangle((margin, int(height * 0.045), width - margin, int(height * 0.14)),
                           radius=int(height * 0.012), fill=(0, 0, 0, 48))
    title_bbox = draw.textbbox((0, 0), collection_title, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    draw.text(((width - title_w) / 2, int(height * 0.065)), collection_title, font=title_font,
              fill=(255, 255, 248, 255), stroke_width=max(1, int(height * 0.0015)), stroke_fill=(0, 0, 0, 180))
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
    overlays = []
    for i, box in enumerate(positions):
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay, "RGBA")
        x1, y1, x2, y2 = box
        # The active row is outlined and gets a visible arrow cursor at its left edge.
        od.rounded_rectangle((x1 - int(width * .006), y1 - int(row_size * .2), x2, y2 + int(row_size * .1)),
                             radius=max(2, int(row_size * .15)), outline=(248, 220, 139, 255),
                             fill=(255, 211, 92, 42), width=max(2, int(width * .0015)))
        arrow_x = max(4, x1 - int(width * .018))
        cy = (y1 + y2) // 2
        arrow = [(arrow_x, cy - int(row_size * .45)), (arrow_x + int(row_size * .7), cy), (arrow_x, cy + int(row_size * .45))]
        od.polygon(arrow, fill=(255, 222, 126, 255))
        op = str(out / f"cursor_{i:03d}.png")
        overlay.save(op)
        overlays.append(op)
    return base_path, overlays
