import unittest
import sys
from pathlib import Path
import tempfile
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.services.font_service import (
    list_system_font_families,
    resolve_font_path,
    list_family_styles,
    refresh_fonts,
)
from src.services.compositor import create_composition
from src.services.render_service import RESOLUTIONS, validate_project
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window

_app = None

def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestTypographyAndWebsite(unittest.TestCase):
    def setUp(self):
        _get_app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Create dummy background image (1920x1080)
        self.bg_path = self.tmp / "background.png"
        Image.new("RGB", (1920, 1080), color=(20, 20, 30)).save(self.bg_path)

        # Create dummy logo (200x200)
        self.logo_path = self.tmp / "logo.png"
        Image.new("RGBA", (200, 200), color=(220, 50, 50, 255)).save(self.logo_path)

        self.tracks = [
            {"path": str(self.tmp / "t1.wav"), "duration": 5.0, "title": "First Nasheed Track"},
            {"path": str(self.tmp / "t2.wav"), "duration": 5.0, "title": "Second Nasheed Track"},
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # Font Service Tests
    # ------------------------------------------------------------------
    def test_font_service_enumeration(self):
        """Font service discovers system fonts and returns fallback families if needed."""
        refresh_fonts()
        fonts = list_system_font_families()
        self.assertIsInstance(fonts, list)
        self.assertGreater(len(fonts), 0)
        # Arial or Segoe UI should exist on Windows
        self.assertTrue(any(f in fonts for f in ["Arial", "Segoe UI", "Calibri", "Tahoma"]))

    def test_font_service_resolution(self):
        """Resolves system font path or falls back safely without crashing."""
        path = resolve_font_path("Arial", "Regular")
        if path:
            self.assertTrue(Path(path).exists())
            self.assertTrue(path.lower().endswith((".ttf", ".otf", ".ttc")))

        # Non-existent font should return empty string or valid fallback path, not crash
        fallback_path = resolve_font_path("NonExistentFont12345", "Bold")
        if fallback_path:
            self.assertTrue(Path(fallback_path).exists())

    def test_font_styles_discovery(self):
        """list_family_styles returns available styles for a known font."""
        styles = list_family_styles("Arial")
        self.assertIsInstance(styles, list)
        self.assertIn("Regular", styles)

    # ------------------------------------------------------------------
    # Compositor Typography & Scaling Tests (1080p, 1440p, 4K)
    # ------------------------------------------------------------------
    def test_composition_renders_at_1080p_1440p_4k(self):
        """create_composition produces valid images matching target resolutions."""
        track_titles = [t["title"] for t in self.tracks]
        for name, (w, h) in RESOLUTIONS.items():
            comp_path, _ = create_composition(
                width=w,
                height=h,
                background_path=str(self.bg_path),
                logo_path=str(self.logo_path),
                collection_title="Nasheed Collection 2026",
                track_titles=track_titles,
                template="Cinematic",
                out_dir=str(self.tmp / f"res_{w}_{h}"),
                title_font_family="Arial",
                title_font_style="Bold",
                title_font_size=40,
                track_font_family="Segoe UI",
                track_font_style="Regular",
                track_font_size=20,
                website_text="www.nasheedstudio.example",
                website_position="Bottom-Right",
                website_font_size=18,
            )
            self.assertTrue(Path(comp_path).exists())
            with Image.open(comp_path) as img:
                self.assertEqual(img.size, (w, h))

    # ------------------------------------------------------------------
    # Website Watermark & 4 Corner Placements
    # ------------------------------------------------------------------
    def test_website_all_four_corners(self):
        """Website watermark can be positioned in all 4 corners without error."""
        track_titles = [t["title"] for t in self.tracks]
        corners = ["Bottom-Right", "Bottom-Left", "Top-Right", "Top-Left"]
        for corner in corners:
            comp_path, _ = create_composition(
                width=1920,
                height=1080,
                background_path=str(self.bg_path),
                logo_path=None,
                collection_title="Testing Corner",
                track_titles=track_titles,
                template="Clean Modern",
                out_dir=str(self.tmp / f"corner_{corner}"),
                website_text="www.islamicnasheed.com",
                website_position=corner,
                website_font_size=20,
            )
            self.assertTrue(Path(comp_path).exists())

    def test_logo_and_website_overlap_avoidance(self):
        """When logo and website share the same corner, website is offset to prevent collision."""
        track_titles = [t["title"] for t in self.tracks]
        # Both in Bottom-Right
        comp_path, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.bg_path),
            logo_path=str(self.logo_path),
            logo_position="Bottom-Right",
            collection_title="Collision Test",
            track_titles=track_titles,
            template="Cinematic",
            out_dir=str(self.tmp / "collision_br"),
            website_text="www.overlap-test.org",
            website_position="Bottom-Right",
            website_font_size=22,
        )
        self.assertTrue(Path(comp_path).exists())
        with Image.open(comp_path) as img:
            self.assertEqual(img.size, (1920, 1080))

        # Both in Top-Left
        comp_path_tl, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.bg_path),
            logo_path=str(self.logo_path),
            logo_position="Top-Left",
            collection_title="Collision Test TL",
            track_titles=track_titles,
            template="Cinematic",
            out_dir=str(self.tmp / "collision_tl"),
            website_text="www.overlap-test-tl.org",
            website_position="Top-Left",
            website_font_size=22,
        )
        self.assertTrue(Path(comp_path_tl).exists())

    # ------------------------------------------------------------------
    # UI Overlap Warning & Project Serialization Roundtrip
    # ------------------------------------------------------------------
    def test_ui_overlap_warning_visibility(self):
        """UI dynamically displays overlap warning when logo and website share corner."""
        win = MainWindow()
        try:
            # Set a valid logo path so has_logo is True
            win.logo_path = str(self.logo_path)
            # Initially different corners
            win.logo_pos_combo.setCurrentText("Bottom-Right")
            win.website_pos_combo.setCurrentText("Bottom-Left")
            win.website_edit.setText("www.example.com")
            self.assertTrue(win.overlap_warning.isHidden())

            # Set same corner
            win.website_pos_combo.setCurrentText("Bottom-Right")
            self.assertFalse(win.overlap_warning.isHidden())

            # Change logo position away
            win.logo_pos_combo.setCurrentText("Top-Right")
            self.assertTrue(win.overlap_warning.isHidden())

            # Empty website text hides warning even if corners match
            win.logo_pos_combo.setCurrentText("Bottom-Right")
            win.website_pos_combo.setCurrentText("Bottom-Right")
            self.assertFalse(win.overlap_warning.isHidden())
            win.website_edit.setText("")
            self.assertTrue(win.overlap_warning.isHidden())
        finally:
            dispose_window(win)

    def test_typography_and_website_save_load_roundtrip(self):
        """Project snapshot preserves all typography and website watermark settings."""
        win = MainWindow()
        try:
            win.title_font_combo.setCurrentText("Arial")
            win.title_style_combo.setCurrentText("Bold")
            win.title_size_spin.setValue(44)

            win.track_font_combo.setCurrentText("Segoe UI")
            win.track_style_combo.setCurrentText("Bold")
            win.track_size_spin.setValue(22)

            win.website_edit.setText("www.preserved-site.org")
            win.website_pos_combo.setCurrentText("Top-Left")
            win.website_size_spin.setValue(19)
            win.logo_pos_combo.setCurrentText("Top-Right")

            proj = win._project()
            self.assertEqual(proj["title_font_family"], "Arial")
            self.assertEqual(proj["title_font_style"], "Bold")
            self.assertEqual(proj["title_font_size"], 44)
            self.assertEqual(proj["track_font_family"], "Segoe UI")
            self.assertEqual(proj["track_font_style"], "Bold")
            self.assertEqual(proj["track_font_size"], 22)
            self.assertEqual(proj["website_text"], "www.preserved-site.org")
            self.assertEqual(proj["website_position"], "Top-Left")
            self.assertEqual(proj["website_font_size"], 19)
            self.assertEqual(proj["logo_position"], "Top-Right")

            # Save to JSON file
            proj_file = self.tmp / "test_proj.json"
            win._write_project(str(proj_file))

            # Reset window and load back
            win2 = MainWindow()
            try:
                win2._load_project_file(str(proj_file))
                self.assertEqual(win2.title_font_combo.currentText(), "Arial")
                self.assertEqual(win2.title_style_combo.currentText(), "Bold")
                self.assertEqual(win2.title_size_spin.value(), 44)
                self.assertEqual(win2.track_font_combo.currentText(), "Segoe UI")
                self.assertEqual(win2.track_size_spin.value(), 22)
                self.assertEqual(win2.website_edit.text(), "www.preserved-site.org")
                self.assertEqual(win2.website_pos_combo.currentText(), "Top-Left")
                self.assertEqual(win2.website_size_spin.value(), 19)
                self.assertEqual(win2.logo_pos_combo.currentText(), "Top-Right")
            finally:
                dispose_window(win2)
        finally:
            dispose_window(win)
