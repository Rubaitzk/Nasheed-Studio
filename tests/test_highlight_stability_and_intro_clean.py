import pytest
from pathlib import Path
from PIL import Image
import numpy as np
from src.services.compositor import create_composition, create_intro_card


def test_highlight_vertical_centering_stability_across_descenders(tmp_path):
    """
    Verify that track highlights do NOT shift upwards on tracks lacking descenders
    (e.g. '04. boci boci tarka remix' vs '06. alex morgan islamic nasheed peaceful').
    The vertical center and highlight height must be stable across all tracks.
    """
    tracks = [
        "04. boci boci tarka remix",
        "05. desifreemusic islamic music 240169",
        "06. alex morgan islamic nasheed peaceful",
    ]

    base_png, overlay_pngs = create_composition(
        track_titles=tracks,
        width=1920,
        height=1080,
        background_path="",
        logo_path=None,
        collection_title="Nasheed Collection",
        out_dir=str(tmp_path / "overlays"),
        template="Two-column",
        playlist_columns=2,
        highlight_style="Outline",
        highlight_color="#00FFCC",
        highlight_target="row",
        indicator_mode="highlight_only",
        track_font_family="Segoe UI",
        track_font_size=38,
        preview_only_first_overlay=False,
    )

    assert len(overlay_pngs) == 3

    # Inspect the vertical bounding box of the highlight color in each overlay
    highlight_y_ranges = []
    for ov_path in overlay_pngs:
        ov = Image.open(ov_path).convert("RGBA")
        arr = np.array(ov)
        # Highlight is colored #00FFCC (R < 50, G > 200, B > 180, A > 100)
        mask = (arr[:, :, 0] < 50) & (arr[:, :, 1] > 200) & (arr[:, :, 2] > 180) & (arr[:, :, 3] > 100)
        y_indices = np.where(mask.any(axis=1))[0]
        assert len(y_indices) > 0, "Highlight pixels must be present"
        ymin = int(y_indices.min())
        ymax = int(y_indices.max())
        highlight_y_ranges.append((ymin, ymax, ymax - ymin + 1))

    # All 3 tracks must have identical highlight box height
    h0 = highlight_y_ranges[0][2]
    h1 = highlight_y_ranges[1][2]
    h2 = highlight_y_ranges[2][2]
    assert h0 == h1 == h2, f"Highlight heights must be identical: {h0}, {h1}, {h2}"

    # Track 0 (Col 0, Row 0) and Track 2 (Col 1, Row 0) must align at identical vertical positions
    assert highlight_y_ranges[0][0] == highlight_y_ranges[2][0], (
        f"Row 0 across columns must align at same Y: {highlight_y_ranges[0][0]} vs {highlight_y_ranges[2][0]}"
    )


def test_highlight_text_target_height_stability(tmp_path):
    """
    Verify that when highlight_target == 'text', the height of the highlight box
    does not shrink on tracks without descenders.
    """
    tracks = [
        "04. boci boci tarka remix",
        "06. alex morgan islamic nasheed peaceful",
    ]

    _, overlay_pngs = create_composition(
        track_titles=tracks,
        width=1920,
        height=1080,
        background_path="",
        logo_path=None,
        collection_title="Nasheed Collection",
        out_dir=str(tmp_path / "text_overlays"),
        template="Two-column",
        playlist_columns=2,
        highlight_style="Pill",
        highlight_color="#FF44AA",
        highlight_target="text",
        indicator_mode="highlight_only",
        track_font_family="Segoe UI",
        track_font_size=38,
        preview_only_first_overlay=False,
    )

    h_ranges = []
    for ov_path in overlay_pngs:
        ov = Image.open(ov_path).convert("RGBA")
        arr = np.array(ov)
        # Highlight is colored #FF44AA (R > 200, G < 100, B > 120, A > 100)
        mask = (arr[:, :, 0] > 200) & (arr[:, :, 1] < 100) & (arr[:, :, 2] > 120) & (arr[:, :, 3] > 100)
        y_indices = np.where(mask.any(axis=1))[0]
        assert len(y_indices) > 0, "Highlight pixels must be present"
        ymin = int(y_indices.min())
        ymax = int(y_indices.max())
        h_ranges.append(ymax - ymin + 1)

    # Text highlight heights must be identical regardless of descenders
    assert h_ranges[0] == h_ranges[1], f"Text highlight box heights must be identical: {h_ranges}"


def test_intro_screen_no_accent_divider_line(tmp_path):
    """
    Verify that create_intro_card no longer renders the accent divider line below the logo.
    """
    bg = Image.new("RGB", (1920, 1080), color=(20, 25, 30))
    bg_p = tmp_path / "bg.png"
    bg.save(bg_p)

    logo = Image.new("RGBA", (200, 200), color=(255, 255, 255, 255))
    logo_p = tmp_path / "logo.png"
    logo.save(logo_p)

    card_p = create_intro_card(
        width=1920,
        height=1080,
        background_path=str(bg_p),
        logo_path=str(logo_p),
        collection_title="Test Collection Title",
        template="Cinematic",
        out_dir=str(tmp_path / "intro"),
        logo_show=True,
    )

    assert Path(card_p).is_file()
    card_img = Image.open(card_p).convert("RGBA")

    # In previous implementation, the line was drawn with color (248, 220, 139) around card_w * 0.22 width
    # Check pixels in the area between logo bottom and title top:
    # There should be NO horizontal line of gold pixels (r in [235..255], g in [210..230], b in [130..150])
    w, h = card_img.size
    mid_x = w // 2
    gold_pixels = 0
    for y in range(int(h * 0.2), int(h * 0.5)):
        r, g, b, a = card_img.getpixel((mid_x, y))
        if 235 <= r <= 255 and 210 <= g <= 230 and 130 <= b <= 150:
            gold_pixels += 1

    assert gold_pixels == 0, f"Expected 0 gold divider line pixels, found {gold_pixels}"
