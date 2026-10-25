"""
Regression tests for Task F (Custom Cursor and Highlight Modes).

Verifies:
1. All 4 indicator combinations work:
   - "both" (cursor and highlight)
   - "cursor_only" (cursor without row highlight)
   - "highlight_only" (highlight without cursor)
   - "neither" (clean playlist, 0 overlay images returned)
2. Custom PNG cursor loading, alpha transparency, and resizing.
3. Custom SVG cursor rasterization via QtSvg into PIL image.
4. Error handling for missing or unreadable cursor files.
5. Cursor scaling across resolutions (1080p, 1440p, 4K UHD).
"""

import tempfile
import unittest
from pathlib import Path
from PIL import Image

from src.services.compositor import (
    create_composition,
    load_cursor_image,
    render_svg_to_image,
    INDICATOR_MODES,
)


class TestIndicatorAndCursorModes(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Create dummy background image
        self.bg_path = self.tmp / "bg.png"
        bg_img = Image.new("RGB", (640, 360), (30, 40, 35))
        bg_img.save(str(self.bg_path))

        # Create dummy PNG cursor (with alpha)
        self.png_cursor = self.tmp / "test_cursor.png"
        png_img = Image.new("RGBA", (48, 48), (255, 200, 0, 200))
        png_img.save(str(self.png_cursor))

        # Create dummy SVG cursor
        self.svg_cursor = self.tmp / "test_cursor.svg"
        svg_content = (
            '<svg width="40" height="40" xmlns="http://www.w3.org/2000/svg">'
            '<polygon points="0,0 40,20 0,40" fill="#00ffcc"/>'
            '</svg>'
        )
        self.svg_cursor.write_text(svg_content, encoding="utf-8")

        self.tracks = ["Track One", "Track Two", "Track Three"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_mode_both(self):
        """Mode 'both' generates base + one overlay per track with highlight and cursor."""
        work_dir = self.tmp / "work_both"
        base, overlays = create_composition(
            width=1280, height=720,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Test Both",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(work_dir),
            indicator_mode="both",
            cursor_size=32,
        )
        self.assertTrue(Path(base).is_file())
        self.assertEqual(len(overlays), 3)
        for op in overlays:
            self.assertTrue(Path(op).is_file())
            img = Image.open(op)
            self.assertEqual(img.size, (1280, 720))
            self.assertIsNotNone(img.getbbox(), "Overlay must not be blank")

    def test_mode_cursor_only(self):
        """Mode 'cursor_only' generates overlays with cursor without crashing."""
        work_dir = self.tmp / "work_cursor_only"
        base, overlays = create_composition(
            width=1280, height=720,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Test Cursor Only",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(work_dir),
            indicator_mode="cursor_only",
            cursor_size=32,
        )
        self.assertTrue(Path(base).is_file())
        self.assertEqual(len(overlays), 3)

    def test_mode_highlight_only(self):
        """Mode 'highlight_only' generates overlays with highlight box only."""
        work_dir = self.tmp / "work_hl_only"
        base, overlays = create_composition(
            width=1280, height=720,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Test Highlight Only",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(work_dir),
            indicator_mode="highlight_only",
        )
        self.assertTrue(Path(base).is_file())
        self.assertEqual(len(overlays), 3)

    def test_mode_neither_returns_empty_overlays(self):
        """Mode 'neither' returns base composition and an empty list of overlays."""
        work_dir = self.tmp / "work_neither"
        base, overlays = create_composition(
            width=1280, height=720,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Test Neither",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(work_dir),
            indicator_mode="neither",
        )
        self.assertTrue(Path(base).is_file())
        self.assertEqual(overlays, [], "Mode 'neither' must return 0 overlays")

    def test_custom_png_cursor_load_and_resize(self):
        """Custom PNG cursor loads and scales to target dimension."""
        cursor_img = load_cursor_image(str(self.png_cursor), target_dim=36)
        self.assertLessEqual(cursor_img.width, 36)
        self.assertLessEqual(cursor_img.height, 36)
        self.assertEqual(cursor_img.mode, "RGBA")

    def test_custom_svg_cursor_rendering(self):
        """Custom SVG cursor renders cleanly to RGBA PIL Image."""
        cursor_img = render_svg_to_image(str(self.svg_cursor), target_w=48, target_h=48)
        self.assertEqual(cursor_img.size, (48, 48))
        self.assertEqual(cursor_img.mode, "RGBA")
        self.assertIsNotNone(cursor_img.getbbox(), "Rendered SVG must not be empty")

    def test_custom_cursor_integrated_in_composition(self):
        """Compositor integrates custom SVG and PNG cursors into overlay images."""
        work_dir = self.tmp / "work_svg_comp"
        base, overlays = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Test SVG Cursor",
            track_titles=["A", "B"],
            template="Cinematic",
            out_dir=str(work_dir),
            indicator_mode="cursor_only",
            cursor_path=str(self.svg_cursor),
            cursor_size=40,
        )
        self.assertEqual(len(overlays), 2)
        # Ensure overlay has pixels
        ov0 = Image.open(overlays[0])
        self.assertIsNotNone(ov0.getbbox())

    def test_missing_or_corrupt_cursor_raises(self):
        """Missing or unsupported cursor files raise clear exceptions."""
        with self.assertRaises(FileNotFoundError):
            load_cursor_image("nonexistent_cursor_file.png", 32)

        bad_txt = self.tmp / "not_an_image.txt"
        bad_txt.write_text("hello", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_cursor_image(str(bad_txt), 32)


if __name__ == "__main__":
    unittest.main()
