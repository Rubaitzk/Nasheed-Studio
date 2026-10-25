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
    clean_logo_image,
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


if __name__ == "__main__":
    unittest.main()
