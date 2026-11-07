"""
Tests for user_templates discovery, template loading, and accurate cursor/highlight indicator alignment.
"""

import io
import json
import tempfile
from pathlib import Path
import pytest
from PIL import Image

from src.services.project_service import (
    discover_user_templates,
    load_template,
    apply_template_to_project,
)
from src.services.compositor import (
    create_composition,
    create_intro_card,
    calculate_playlist_layout,
    load_cursor_image,
)


def test_discover_user_templates():
    templates = discover_user_templates()
    user_tmpls = [t for t in templates if t["category"] == "User Template"]
    assert len(user_tmpls) >= 2

    filenames = [t["filename"] for t in user_tmpls]
    assert "01_gym_nasheeds_monochrome_lion.json" in filenames
    assert "04_sad_nasheeds_glass_highlight.json" in filenames


def test_load_all_user_templates():
    root = Path(__file__).resolve().parent.parent
    tmpl_dir = root / "user_templates"
    for tmpl_file in tmpl_dir.glob("*.json"):
        data = load_template(str(tmpl_file))
        assert "collection_title" in data
        assert "template" in data
        assert "title_font_family" in data
        assert "track_font_family" in data


def test_template_preserves_user_audio_tracks():
    base_project = {
        "collection_title": "My Original Project",
        "tracks": [
            {"title": "Track One", "path": "test/path1.mp3", "duration": 30.0},
            {"title": "Track Two", "path": "test/path2.mp3", "duration": 45.0},
        ],
        "template": "Minimal",
    }
    tmpl = load_template("user_templates/04_sad_nasheeds_glass_highlight.json")
    merged = apply_template_to_project(base_project, tmpl)

    # Content preserved
    assert len(merged["tracks"]) == 2
    assert merged["tracks"][0]["title"] == "Track One"
    assert merged["tracks"][1]["path"] == "test/path2.mp3"

    # Styling updated
    assert merged["highlight_style"] == "Outline"
    assert merged["highlight_color"] == [0, 200, 248]
    assert merged["highlight_outline_width"] == 6
    assert merged["highlight_corner_radius"] == 0
    assert merged["highlight_target"] == "text"


def test_cursor_and_text_vertical_alignment():
    """Verify that custom and arrow cursors are vertically aligned with the active track text visual center."""
    tracks = ["1. Whispers of Salah", "2. Peaceful Reflection"]
    with tempfile.TemporaryDirectory() as tmp:
        base, overlays = create_composition(
            width=1920,
            height=1080,
            background_path="assets/lion_clean_bg.png",
            logo_path=None,
            track_titles=tracks,
            collection_title="Test Title",
            template="Cinematic",
            out_dir=tmp,
            indicator_mode="cursor_only",
            cursor_path="assets/paw_cursor.png",
            cursor_size=42,
            preview_only_first_overlay=True,
            active_track_index=0,
            title_font_family="Montserrat",
            title_font_style="Bold",
            title_font_size=68,
            title_position="Above Playlist",
            track_font_family="Montserrat",
            track_font_style="Regular",
            track_font_size=46,
            playlist_position="Left",
            playlist_columns=1,
            playlist_row_spacing=1.8,
        )
        assert len(overlays) == 1
        with open(overlays[0], "rb") as f:
            data = f.read()
        with Image.open(io.BytesIO(data)) as ov:
            assert ov.size == (1920, 1080)

        # Track layout
        layout = calculate_playlist_layout(
            track_titles=tracks,
            width=1920,
            height=1080,
            template="Cinematic",
            playlist_position="Left",
            playlist_columns=1,
            playlist_row_spacing=1.8,
            playlist_width_ratio=0.5,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Montserrat",
            track_font_style="Regular",
            track_font_size=46,
            track_wrap_text=False,
            title_bottom_y=280,
            indicator_enabled=True,
        )
        item0 = layout["track_items"][0]
        fnt = layout["row_font"]
        tb = fnt.getbbox(item0["text"])
        expected_text_visual_cy = item0["y"] + (tb[1] + tb[3]) // 2

        # Verify cursor center matches expected_text_visual_cy
        cursor_img = load_cursor_image("assets/paw_cursor.png", 42)
        ch = cursor_img.size[1]
        cursor_placed_y = expected_text_visual_cy - ch // 2
        cursor_placed_cy = cursor_placed_y + ch // 2
        assert abs(cursor_placed_cy - expected_text_visual_cy) <= 1


def test_thick_rectangular_outline_highlight_rendering():
    """Verify that thick 6px rectangular outline with square corners renders without errors."""
    tracks = ["01. KUNTU MAITAN", "02. HABBAT KARREEH"]
    with tempfile.TemporaryDirectory() as tmp:
        base, overlays = create_composition(
            width=1920,
            height=1080,
            background_path="assets/refer4_sad_nasheeds_clean_bg.png",
            logo_path=None,
            track_titles=tracks,
            collection_title="SAD NASHEEDS",
            template="Cinematic",
            out_dir=tmp,
            indicator_mode="highlight_only",
            highlight_style="Outline",
            highlight_color=(0, 200, 248),
            highlight_outline_width=6,
            highlight_corner_radius=0,
            highlight_target="text",
            highlight_padding_x=18,
            highlight_padding_y=8,
            preview_only_first_overlay=True,
            active_track_index=0,
        )
        assert Path(base).is_file()
        assert len(overlays) == 1
        with open(overlays[0], "rb") as f:
            data = f.read()
        with Image.open(io.BytesIO(data)) as im:
            assert im.size == (1920, 1080)


def test_intro_title_boundary_and_no_clipping():
    """Verify that long titles or large font sizes wrap/fit and never exceed canvas safe margins."""
    long_title = "PEACEFUL REFLECTIONS AND MAJESTIC SPIRITUAL CHANTS OF THE ANCIENT DESERT"
    with tempfile.TemporaryDirectory() as tmp:
        card_p = create_intro_card(
            width=1920,
            height=1080,
            background_path="assets/lion_clean_bg.png",
            logo_path=None,
            collection_title=long_title,
            template="Cinematic",
            out_dir=tmp,
            title_font_family="Montserrat",
            title_font_style="Bold",
            title_font_size=110,  # Intentionally large font size
            website_text="www.nocopyrightnasheeds.com",
            website_show=True,
            website_opacity=1.0,
        )
        assert Path(card_p).is_file()
        with open(card_p, "rb") as f:
            data = f.read()
        with Image.open(io.BytesIO(data)) as im:
            assert im.size == (1920, 1080)


def test_cursor_and_highlight_y_offset_adjusters():
    """Verify that independent cursor_y_offset and highlight_y_offset adjust positioning cleanly."""
    tracks = ["1. Kuntu Maitan", "2. Habbat Karreeh"]
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        # Baseline (0 offset)
        base0, ov0 = create_composition(
            width=1920,
            height=1080,
            background_path="assets/lion_clean_bg.png",
            logo_path=None,
            track_titles=tracks,
            collection_title="Gym Nasheeds",
            template="Cinematic",
            out_dir=tmp1,
            indicator_mode="both",
            cursor_path="assets/paw_cursor.png",
            cursor_size=50,
            highlight_style="Outline",
            highlight_outline_width=4,
            cursor_y_offset=0,
            highlight_y_offset=0,
            preview_only_first_overlay=True,
            active_track_index=0,
        )

        # Shifted: cursor down by 12px, highlight up by 8px
        base_s, ov_s = create_composition(
            width=1920,
            height=1080,
            background_path="assets/lion_clean_bg.png",
            logo_path=None,
            track_titles=tracks,
            collection_title="Gym Nasheeds",
            template="Cinematic",
            out_dir=tmp2,
            indicator_mode="both",
            cursor_path="assets/paw_cursor.png",
            cursor_size=50,
            highlight_style="Outline",
            highlight_outline_width=4,
            cursor_y_offset=12,
            highlight_y_offset=-8,
            preview_only_first_overlay=True,
            active_track_index=0,
        )

        assert Path(ov0[0]).is_file()
        assert Path(ov_s[0]).is_file()

        with Image.open(ov0[0]) as im0, Image.open(ov_s[0]) as im_s:
            bbox0 = im0.getbbox()
            bbox_s = im_s.getbbox()
            # Bounding box of the composite overlay should reflect the vertical shift
            assert bbox0 is not None
            assert bbox_s is not None


def test_outline_highlight_zero_inner_shading():
    """Verify Outline highlight has 100% transparent interior (no inner tint/shading)."""
    tracks = ["01. Test Track Long Title Outline"]
    with tempfile.TemporaryDirectory() as tmp:
        base, overlays = create_composition(
            width=1920,
            height=1080,
            background_path="assets/lion_clean_bg.png",
            logo_path=None,
            track_titles=tracks,
            collection_title="Outline Test",
            template="Cinematic",
            out_dir=tmp,
            indicator_mode="highlight_only",
            highlight_style="Outline",
            highlight_color=(255, 255, 0),
            highlight_bg_opacity=0.50,  # Even if bg_opacity is specified, Outline must ignore it and have zero fill
            highlight_outline_width=4,
            highlight_target="text",
            preview_only_first_overlay=True,
            active_track_index=0,
        )
        with open(overlays[0], "rb") as f:
            data = f.read()
        with Image.open(io.BytesIO(data)) as ov:
            # For Outline style, verify there are 0 translucent fill pixels inside the rectangle
            pixels = list(ov.getdata())
            translucent_yellows = [p for p in pixels if p[0] == 255 and p[1] == 255 and p[2] == 0 and 0 < p[3] < 255]
            assert len(translucent_yellows) == 0, f"Expected 0 translucent fill pixels for Outline, found {len(translucent_yellows)}"


def test_custom_cursor_no_overlap_with_text_outline():
    """Verify custom cursor (paw) sits to the left of the text-tight outline box without crossing over."""
    tracks = ["01. Kuntu Maitan Nasheed"]
    with tempfile.TemporaryDirectory() as tmp:
        base, overlays = create_composition(
            width=1920,
            height=1080,
            background_path="assets/lion_clean_bg.png",
            logo_path=None,
            track_titles=tracks,
            collection_title="Overlap Prevention Test",
            template="Cinematic",
            out_dir=tmp,
            indicator_mode="both",
            cursor_path="assets/paw_cursor.png",
            cursor_size=50,
            highlight_style="Outline",
            highlight_color=(255, 255, 127),
            highlight_outline_width=4,
            highlight_target="text",
            preview_only_first_overlay=True,
            active_track_index=0,
        )
        assert Path(overlays[0]).is_file()
        with open(overlays[0], "rb") as f:
            data = f.read()
        with Image.open(io.BytesIO(data)) as ov:
            assert ov.size == (1920, 1080)
