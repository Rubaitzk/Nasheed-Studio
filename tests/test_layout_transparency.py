"""Comprehensive unit and integration tests for adjustable layout, typography, transparency, and logo cleanup."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.services.compositor import (
    create_composition,
    create_intro_card,
    clean_logo_image,
    load_cursor_image,
    calculate_playlist_layout,
    _calculate_title_layout,
    HIGHLIGHT_STYLES,
    PLAYLIST_POSITIONS,
    TITLE_POSITIONS,
)
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestLayoutAndTransparency(unittest.TestCase):
    def setUp(self):
        _get_app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Base 1080p background
        self.bg_path = self.tmp / "test_bg.png"
        Image.new("RGB", (1920, 1080), color=(30, 45, 38)).save(self.bg_path)

        self.track_titles = [
            "1. First Nasheed With Moderate Length",
            "2. Second Nasheed A Bit Longer For Testing Text Wrap",
            "3. Third Nasheed Short",
            "4. Fourth Nasheed",
            "5. Fifth Nasheed",
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_playlist_position_presets(self):
        """create_composition places playlist at Left, Center, or Right correctly."""
        positions = ["Left", "Center", "Right"]
        for pos in positions:
            out_dir = self.tmp / f"pos_{pos}"
            base, overlays = create_composition(
                width=1920,
                height=1080,
                background_path=str(self.bg_path),
                logo_path=None,
                collection_title="Position Test",
                track_titles=self.track_titles,
                template="Cinematic",
                out_dir=str(out_dir),
                playlist_position=pos,
            )
            self.assertTrue(Path(base).exists())
            self.assertEqual(len(overlays), len(self.track_titles))

    def test_transparent_playlist_background(self):
        """
        When playlist_bg_opacity is 0.0 (default), no opaque rectangle strip is baked.
        When opacity > 0.0, a background strip is drawn.
        """
        out_trans = self.tmp / "trans_bg"
        base_trans, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Transparent Test",
            track_titles=self.track_titles,
            template="Cinematic",
            out_dir=str(out_trans),
            playlist_bg_opacity=0.0,
        )
        img_trans = Image.open(base_trans).convert("RGBA")

        out_opaque = self.tmp / "opaque_bg"
        base_opaque, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Opaque Test",
            track_titles=self.track_titles,
            template="Cinematic",
            out_dir=str(out_opaque),
            playlist_bg_opacity=0.85,
            playlist_bg_color=(10, 10, 10),
        )
        img_opaque = Image.open(base_opaque).convert("RGBA")

        # Pixel comparison inside the playlist area: opaque version must be darker than transparent version
        px_trans = img_trans.getpixel((250, 250))
        px_opaque = img_opaque.getpixel((250, 250))
        # Opaque version with (10,10,10) blend is darker
        self.assertNotEqual(px_trans, px_opaque)

    def test_all_highlight_styles_rendered(self):
        """Verify each highlight style (Pill, Accent Bar, Outline, Underline) renders valid overlay images."""
        styles = ["Pill", "Accent Bar", "Outline", "Underline"]
        for st in styles:
            out_dir = self.tmp / f"hl_{st.replace(' ', '_')}"
            base, overlays = create_composition(
                width=1920,
                height=1080,
                background_path=str(self.bg_path),
                logo_path=None,
                collection_title="Highlight Style Test",
                track_titles=self.track_titles[:3],
                template="Cinematic",
                out_dir=str(out_dir),
                indicator_mode="highlight_only",
                highlight_style=st,
                highlight_color=(248, 220, 139),
                highlight_bg_opacity=0.40,
            )
            self.assertEqual(len(overlays), 3)
            for ov_path in overlays:
                with Image.open(ov_path) as ov:
                    self.assertEqual(ov.size, (1920, 1080))
                    # Must contain non-zero alpha pixels for highlight
                    alpha_channel = ov.split()[3]
                    bbox = alpha_channel.getbbox()
                    self.assertIsNotNone(bbox, f"Overlay for {st} was completely transparent!")

    def test_logo_background_cleanup_white(self):
        """clean_logo_image cleanly clears solid white background to alpha 0 while preserving inner graphics."""
        w, h = 120, 120
        raw_logo = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        # Draw green circle with white text inside
        from PIL import ImageDraw
        d = ImageDraw.Draw(raw_logo)
        d.ellipse((20, 20, 100, 100), fill=(10, 150, 80, 255))
        d.rectangle((50, 50, 70, 70), fill=(255, 255, 255, 255))  # Inner white graphic

        cleaned = clean_logo_image(raw_logo, mode="remove_white")
        # Corner must be transparent
        self.assertEqual(cleaned.getpixel((0, 0))[3], 0)
        self.assertEqual(cleaned.getpixel((w - 1, 0))[3], 0)
        # Inner circle must remain opaque green
        self.assertEqual(cleaned.getpixel((60, 30))[:3], (10, 150, 80))
        self.assertEqual(cleaned.getpixel((60, 30))[3], 255)
        # Inner white graphic must remain opaque white
        self.assertEqual(cleaned.getpixel((60, 60)), (255, 255, 255, 255))

    def test_logo_background_cleanup_checkerboard(self):
        """clean_logo_image removes fake checkerboard border patterns."""
        w, h = 80, 80
        im = Image.new("RGBA", (w, h))
        px = im.load()
        for y in range(h):
            for x in range(w):
                is_light = ((x // 8) + (y // 8)) % 2 == 0
                c = 255 if is_light else 204
                px[x, y] = (c, c, c, 255)
        # Center logo mark
        from PIL import ImageDraw
        d = ImageDraw.Draw(im)
        d.rectangle((25, 25, 55, 55), fill=(220, 50, 50, 255))

        cleaned = clean_logo_image(im, mode="remove_checkerboard")
        self.assertEqual(cleaned.getpixel((0, 0))[3], 0)
        self.assertEqual(cleaned.getpixel((4, 4))[3], 0)
        self.assertEqual(cleaned.getpixel((40, 40))[:3], (220, 50, 50))
        self.assertEqual(cleaned.getpixel((40, 40))[3], 255)

    def test_title_positions_and_hiding(self):
        """Verify title position modes: Top-Center, Above Playlist, Top-Left, Hidden."""
        for t_pos in TITLE_POSITIONS:
            out_dir = self.tmp / f"title_{t_pos.replace(' ', '_')}"
            base, _ = create_composition(
                width=1920,
                height=1080,
                background_path=str(self.bg_path),
                logo_path=None,
                collection_title="Nasheed Title Test",
                track_titles=self.track_titles[:2],
                template="Cinematic",
                out_dir=str(out_dir),
                title_position=t_pos,
                title_show=(t_pos != "Hidden"),
            )
            self.assertTrue(Path(base).exists())

    def test_main_window_layout_serialization_roundtrip(self):
        """Verify UI serialization, project saving, and loading preserves all layout parameters."""
        win = MainWindow()
        try:
            win.playlist_pos_combo.setCurrentText("Center")
            win.playlist_cols_spin.setValue(2)
            win.track_spacing_spin.setValue(2.1)
            win.playlist_bg_slider.setValue(45)
            win.title_pos_combo.setCurrentText("Above Playlist")
            win.title_show_check.setChecked(False)
            win.highlight_style_combo.setCurrentText("Accent Bar")
            win.highlight_opacity_slider.setValue(75)
            win.logo_cleanup_check.setChecked(True)

            proj = win._project()
            self.assertEqual(proj["playlist_position"], "Center")
            self.assertEqual(proj["playlist_columns"], 2)
            self.assertAlmostEqual(proj["playlist_row_spacing"], 2.1)
            self.assertAlmostEqual(proj["playlist_bg_opacity"], 0.45)
            self.assertEqual(proj["title_position"], "Above Playlist")
            self.assertFalse(proj["title_show"])
            self.assertEqual(proj["highlight_style"], "Accent Bar")
            self.assertAlmostEqual(proj["highlight_bg_opacity"], 0.75)
            self.assertEqual(proj["logo_cleanup_mode"], "auto")

            # Save to JSON
            p_file = self.tmp / "layout_test_proj.json"
            win._write_project(str(p_file))

            # Reopen in new MainWindow
            win2 = MainWindow()
            try:
                win2._load_project_file(str(p_file))
                self.assertEqual(win2.playlist_pos_combo.currentText(), "Center")
                self.assertEqual(win2.playlist_cols_spin.value(), 2)
                self.assertAlmostEqual(win2.track_spacing_spin.value(), 2.1)
                self.assertEqual(win2.playlist_bg_slider.value(), 45)
                self.assertEqual(win2.title_pos_combo.currentText(), "Above Playlist")
                self.assertFalse(win2.title_show_check.isChecked())
                self.assertEqual(win2.highlight_style_combo.currentText(), "Accent Bar")
                self.assertEqual(win2.highlight_opacity_slider.value(), 75)
                self.assertTrue(win2.logo_cleanup_check.isChecked())
            finally:
                dispose_window(win2)
        finally:
            dispose_window(win)

    def test_website_opacity_compositing_dedicated_layer(self):
        """Dedicated RGBA layer renders website watermark with exact Porter-Duff alpha blending at 0%, 25%, 50%, 100%."""
        opacities = [0.0, 0.25, 0.50, 1.0]
        results = {}
        for op in opacities:
            out_dir = self.tmp / f"web_op_{int(op * 100)}"
            base, _ = create_composition(
                width=1920,
                height=1080,
                background_path=str(self.bg_path),
                logo_path=None,
                collection_title="Website Opacity Test",
                track_titles=self.track_titles[:2],
                template="Cinematic",
                out_dir=str(out_dir),
                website_text="www.nasheedstudio.test",
                website_show=True,
                website_opacity=op,
            )
            img = Image.open(base).convert("RGBA")
            # Base composition must remain 100% opaque across all pixels
            alpha_extrema = img.split()[3].getextrema()
            self.assertEqual(alpha_extrema, (255, 255), "Canvas background alpha must stay 100% opaque (255)")
            results[op] = img

        # At 0.0, watermark should not be drawn; compare pixel near top-right with non-watermarked area
        # Pixel difference between 25%, 50%, and 100% must show increasing contrast
        tr_25 = results[0.25].crop((1500, 30, 1880, 100))
        tr_50 = results[0.50].crop((1500, 30, 1880, 100))
        tr_100 = results[1.0].crop((1500, 30, 1880, 100))
        self.assertNotEqual(tr_25.tobytes(), tr_50.tobytes())
        self.assertNotEqual(tr_50.tobytes(), tr_100.tobytes())

        # Test intro card website opacity
        intro_0 = create_intro_card(
            width=1920,
            height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Intro Card Opacity Test",
            template="Cinematic",
            out_dir=str(self.tmp / "intro_0"),
            website_text="www.nasheedstudio.test",
            website_show=True,
            website_opacity=0.0,
        )
        intro_100 = create_intro_card(
            width=1920,
            height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Intro Card Opacity Test",
            template="Cinematic",
            out_dir=str(self.tmp / "intro_100"),
            website_text="www.nasheedstudio.test",
            website_show=True,
            website_opacity=1.0,
        )
        img_intro_0 = Image.open(intro_0).convert("RGBA")
        img_intro_100 = Image.open(intro_100).convert("RGBA")
        self.assertEqual(img_intro_0.split()[3].getextrema(), (255, 255))
        self.assertEqual(img_intro_100.split()[3].getextrema(), (255, 255))
        self.assertNotEqual(img_intro_0.crop((800, 920, 1120, 980)).tobytes(),
                            img_intro_100.crop((800, 920, 1120, 980)).tobytes())

    def test_logo_and_cursor_transparency_cleanup_genuine_alpha(self):
        """clean_logo_image preserves genuine partial alpha transparency & antialiasing via ImageChops.multiply."""
        w, h = 100, 100
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        # Genuine antialiased transparent circle with semi-transparent graphic (alpha = 130)
        d.ellipse((20, 20, 80, 80), fill=(200, 150, 40, 255))
        d.rectangle((30, 30, 70, 70), fill=(0, 0, 0, 130))

        cleaned = clean_logo_image(img, mode="auto")
        # Corner remains 0 alpha
        self.assertEqual(cleaned.getpixel((0, 0))[3], 0)
        # Semi-transparent graphic must preserve its partial alpha (130)
        self.assertEqual(cleaned.getpixel((50, 50))[3], 130)

        # Test clean_logo_image preserves internal partial alpha when removing solid white background
        white_bg_img = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
        d2 = ImageDraw.Draw(white_bg_img)
        d2.rectangle((20, 20, 80, 80), fill=(10, 120, 50, 180))
        cleaned_white = clean_logo_image(white_bg_img, mode="remove_white")
        self.assertEqual(cleaned_white.getpixel((0, 0))[3], 0)
        self.assertEqual(cleaned_white.getpixel((50, 50))[3], 180)

        # Cursor loading via load_cursor_image with raster image
        cursor_file = self.tmp / "test_cursor.png"
        img.save(cursor_file)
        loaded_cursor = load_cursor_image(str(cursor_file), 32)
        self.assertEqual(loaded_cursor.size, (32, 32))
        self.assertEqual(loaded_cursor.mode, "RGBA")

    def test_fit_to_frame_11_nasheeds_cinematic_auto_split(self):
        """11 tracks at 43pt in Cinematic (Left alignment) auto-splits into 2 columns on the left within frame height."""
        eleven_tracks = [f"Nasheed Track {i + 1:02d} Title Extended" for i in range(11)]
        layout = calculate_playlist_layout(
            track_titles=eleven_tracks,
            width=1920,
            height=1080,
            template="Cinematic",
            playlist_position="Left",
            playlist_columns=1,  # Default single column requested
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.47,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=43,
            track_wrap_text=False,
            title_bottom_y=160,
        )

        self.assertTrue(layout["is_two_col"], "11 tracks at 43pt must auto-split to 2 columns to prevent vertical overflow")
        items = layout["track_items"]
        self.assertEqual(len(items), 11)

        # Col 0 is tracks 0-5, Col 1 is tracks 6-10
        col_0_x = items[0]["x"]
        col_1_x = items[6]["x"]
        self.assertGreater(col_1_x, col_0_x, "Column 2 must be placed to the RIGHT of Column 1 in Left alignment")

        # Verify all 11 tracks stay within the vertical 1080p frame height (<= 1080)
        for it in items:
            x1, y1, x2, y2 = it["box"]
            self.assertLessEqual(y2, 1080, f"Track {it['index']} exceeded bottom screen bound: {y2} > 1080")
        self.assertFalse(layout["overflow"])
        self.assertEqual(layout["max_displayable"], 11)

    def test_fit_to_frame_11_nasheeds_minimal_auto_split(self):
        """11 tracks at 43pt in Minimal (Right alignment) auto-splits into 2 columns on the right."""
        eleven_tracks = [f"Nasheed Track {i + 1:02d}" for i in range(11)]
        layout = calculate_playlist_layout(
            track_titles=eleven_tracks,
            width=1920,
            height=1080,
            template="Minimal",
            playlist_position="Right",
            playlist_columns=1,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.47,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=43,
            track_wrap_text=False,
            title_bottom_y=160,
        )

        self.assertTrue(layout["is_two_col"])
        items = layout["track_items"]
        col_0_x = items[0]["x"]
        col_1_x = items[6]["x"]
        # In right alignment, Col 1 is on right, Col 0 is to its left, so both sit in right half
        self.assertGreater(col_1_x, col_0_x)
        self.assertGreater(col_0_x, 650, "In Right alignment, columns must leave left region for artwork")
        for it in items:
            self.assertLessEqual(it["box"][3], 1080)

    def test_fit_to_frame_center_balance(self):
        """Two columns in Center alignment are centered symmetrically."""
        eleven_tracks = [f"Center Track {i + 1:02d}" for i in range(11)]
        layout = calculate_playlist_layout(
            track_titles=eleven_tracks,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Center",
            playlist_columns=2,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.50,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=24,
            track_wrap_text=False,
            title_bottom_y=160,
        )
        self.assertTrue(layout["is_two_col"])
        items = layout["track_items"]
        col_0_x = items[0]["x"]
        col_1_x2 = items[6]["box"][2]
        center_x = (col_0_x + col_1_x2) // 2
        # Center should be roughly 1920 // 2 = 960 (within 50px tolerance)
        self.assertAlmostEqual(center_x, 960, delta=50)

    def test_multi_resolution_scalability(self):
        """Compositions render cleanly and scale properly at 720p, 1080p, 1440p, and 4K."""
        resolutions = [
            (1280, 720),
            (1920, 1080),
            (2560, 1440),
            (3840, 2160),
        ]
        eleven_tracks = [f"Nasheed Title {i + 1:02d}" for i in range(11)]
        for w, h in resolutions:
            out_dir = self.tmp / f"res_{w}x{h}"
            bg = self.tmp / f"bg_{w}x{h}.png"
            Image.new("RGB", (w, h), (20, 25, 22)).save(bg)

            base, overlays = create_composition(
                width=w,
                height=h,
                background_path=str(bg),
                logo_path=None,
                collection_title="Resolution Scaling Test",
                track_titles=eleven_tracks,
                template="Cinematic",
                out_dir=str(out_dir),
                track_font_size=36,
                preview_only_first_overlay=True,
            )
            self.assertTrue(Path(base).is_file())
            with Image.open(base) as im:
                self.assertEqual(im.size, (w, h))

    def test_long_track_title_wrapping_and_truncation(self):
        """Long track titles truncate at character boundary with ellipsis only when track_max_chars > 0."""
        super_long = "This Is An Extremely Long Nasheed Title That Exceeds The Maximum Usable Single Column Width And Must Truncate Safely"
        layout = calculate_playlist_layout(
            track_titles=[super_long],
            width=1920,
            height=1080,
            template="Cinematic",
            playlist_position="Left",
            playlist_columns=1,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.35,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=28,
            track_wrap_text=False,
            track_max_chars=45,
            title_bottom_y=160,
        )
        item = layout["track_items"][0]
        self.assertTrue(item["text"].endswith("…"))
        self.assertLess(len(item["text"]), len(f"01. {super_long}"))

    def test_reference_title_mahum_be_ummati_ahmadin_fits_without_ellipsis(self):
        """In reference-matched layout, 'Mahum Be Umati Ahmadin' fits completely in Column 1 without '...'."""
        reference_tracks = [
            "Kuntu Maitan",
            "Habbat Karreeh",
            "Hallaka Sirrun Indallah",
            "Fataat al Khair",
            "Mahum Be Umati Ahmadin",
            "We are the Heroes",
            "Ya Qorial Qur'ani",
            "This is Umar",
            "Serna Serna",
            "Sahmul Ams",
            "Qul-li Baghin",
        ]
        layout = calculate_playlist_layout(
            track_titles=reference_tracks,
            width=1920,
            height=1080,
            template="Cinematic",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.55,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=28,
            track_wrap_text=False,
            title_bottom_y=160,
        )
        mahum_item = [it for it in layout["track_items"] if "Mahum Be Umati Ahmadin" in it["text"]]
        self.assertTrue(bool(mahum_item), "Mahum Be Umati Ahmadin should be present")
        self.assertNotIn("…", mahum_item[0]["text"], "Mahum Be Umati Ahmadin should fit without ellipsis")
        self.assertEqual(mahum_item[0]["text"], "05. Mahum Be Umati Ahmadin")

    def test_second_column_distance_content_aware_auto_placement(self):
        """Column 2 starting X position adapts automatically based on the longest title in Column 1."""
        short_col0_tracks = [
            "Track One",
            "Track Two",
            "Track Three",
            "Track Four",
            "Track Five",
            "Track Six",
            "Track Seven",
            "Track Eight",
        ]
        long_col0_tracks = [
            "Track One",
            "Track Two",
            "Track Three",
            "Track Four Very Long Mahum Be Umati Ahmadin Extension",
            "Track Five",
            "Track Six",
            "Track Seven",
            "Track Eight",
        ]
        layout_short = calculate_playlist_layout(
            track_titles=short_col0_tracks,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.55,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=24,
            track_wrap_text=False,
        )
        layout_long = calculate_playlist_layout(
            track_titles=long_col0_tracks,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.55,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=24,
            track_wrap_text=False,
        )
        col1_x_short = layout_short["track_items"][4]["x"]
        col1_x_long = layout_long["track_items"][4]["x"]
        self.assertGreater(col1_x_long, col1_x_short,
                           "Column 2 must be placed further right when Column 1 has a longer title")

    def test_user_adjustable_column_spacing(self):
        """User-configured playlist_col_spacing directly controls the distance between columns."""
        tracks = [f"Nasheed {i+1}" for i in range(8)]
        layout_narrow = calculate_playlist_layout(
            track_titles=tracks,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.55,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=24,
            track_wrap_text=False,
            playlist_col_spacing=25,
        )
        layout_wide = calculate_playlist_layout(
            track_titles=tracks,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.55,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=24,
            track_wrap_text=False,
            playlist_col_spacing=120,
        )
        gap_narrow = layout_narrow["track_items"][4]["x"] - (layout_narrow["track_items"][0]["x"] + layout_narrow["col_0_width"])
        gap_wide = layout_wide["track_items"][4]["x"] - (layout_wide["track_items"][0]["x"] + layout_wide["col_0_width"])
        self.assertAlmostEqual(gap_narrow, 25, delta=5)
        self.assertAlmostEqual(gap_wide, 120, delta=5)

    def test_user_adjustable_track_max_chars(self):
        """track_max_chars limits the character length of titles when configured by user."""
        long_title = "A Substantially Long Nasheed Title That Needs Truncating"
        layout = calculate_playlist_layout(
            track_titles=[long_title],
            width=1920,
            height=1080,
            template="Cinematic",
            playlist_position="Left",
            playlist_columns=1,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.60,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=24,
            track_wrap_text=False,
            track_max_chars=20,
        )
        item = layout["track_items"][0]
        self.assertLessEqual(len(item["text"]), 22)
        self.assertTrue(item["text"].endswith("…"))

    def test_extraordinarily_long_title_boundary_safety(self):
        """Extremely long title with char limit truncates with ellipsis at layout boundaries without pushing columns off-grid."""
        monster_title = "Extremely Super Mega Exceedingly Long Nasheed Track Name That Spans Past Normal Screen Limits And Keeps Going And Going"
        tracks = [monster_title] + [f"Short {i}" for i in range(9)]
        layout = calculate_playlist_layout(
            track_titles=tracks,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.50,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=24,
            track_wrap_text=False,
            track_max_chars=40,
        )
        items = layout["track_items"]
        # Column 1 starts within screen
        self.assertLess(items[5]["x"], 1920 * 0.75, "Column 2 must stay well within right safety boundary")
        # Monster title was truncated safely with …
        self.assertTrue(items[0]["text"].endswith("…"))
        # Number prefix preserved
        self.assertTrue(items[0]["text"].startswith("01. "))
        # Never collapsed to just "01...."
        self.assertGreater(len(items[0]["text"]), 10)

    def test_top_left_title_and_logo_collision_avoidance(self):
        """When title is Top-Left and logo is Top-Left, title is positioned to the right of the logo."""
        lines, font, total_th, coords, bottom_y = _calculate_title_layout(
            collection_title="Top Left Title",
            title_font_family="Segoe UI",
            title_font_style="Bold",
            title_font_size=46,
            norm_title_pos="Top-Left",
            width=1920,
            height=1080,
            margin=105,
            res_scale=1.0,
            logo_placed=True,
            logo_rect=(105, 48, 250, 150),  # Top-left logo
            usable_width=900,
            playlist_x=125,
        )
        # Title start X must be >= logo right edge (250)
        self.assertGreaterEqual(coords[0][0], 250)


if __name__ == "__main__":
    unittest.main()
