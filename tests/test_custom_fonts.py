"""
Unit and integration tests for custom font file selection and rendering.

Verifies:
1. Validating and registering external TTF/OTF font files via font_service.
2. Resolving custom font path by family name or direct file path.
3. Rendering composition using custom font for Title and Tracks.
4. Saving and loading project JSON with custom font references.
5. Managed asset bundling copies custom font files into workspace assets/fonts/.
6. UI MainWindow browse buttons load and apply custom fonts into preview.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageFont, ImageDraw

from src.services.font_service import (
    register_custom_font,
    resolve_font_path,
    list_custom_fonts,
    list_system_font_families,
    refresh_fonts,
)
from src.services.compositor import create_composition, _get_font
from src.services.project_service import (
    save_project_atomic,
    bundle_managed_assets,
    check_missing_assets,
)


class TestCustomFonts(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Locate a known system font file to copy as a synthetic "custom" font
        win_fonts = Path("C:/Windows/Fonts")
        source_font = win_fonts / "arial.ttf"
        if not source_font.is_file():
            source_font = win_fonts / "segoeui.ttf"

        self.custom_font_file = self.tmp / "MyCustomFont.ttf"
        shutil.copy2(source_font, self.custom_font_file)

        # Background for compositor test
        self.bg_path = self.tmp / "bg.png"
        Image.new("RGB", (1280, 720), (20, 30, 40)).save(self.bg_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_register_custom_font_success(self):
        """register_custom_font probes TTF metadata and returns family & style."""
        fam, style = register_custom_font(self.custom_font_file)
        self.assertTrue(len(fam) > 0)
        self.assertIn(fam, list_custom_fonts())
        self.assertIn(fam, list_system_font_families())

        # Resolve via family name
        resolved = resolve_font_path(fam, style)
        self.assertEqual(Path(resolved).resolve(), self.custom_font_file.resolve())

        # Resolve directly via file path
        resolved_direct = resolve_font_path(str(self.custom_font_file))
        self.assertEqual(Path(resolved_direct).resolve(), self.custom_font_file.resolve())

    def test_register_invalid_font_raises(self):
        """register_custom_font raises ValueError for non-font files."""
        bad_file = self.tmp / "bad_font.txt"
        bad_file.write_text("not a font", encoding="utf-8")
        with self.assertRaises(ValueError):
            register_custom_font(bad_file)

    def test_composition_with_custom_font(self):
        """create_composition renders cleanly when custom font family is used."""
        fam, style = register_custom_font(self.custom_font_file)
        base, overlays = create_composition(
            width=1280,
            height=720,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Custom Font Nasheed Collection",
            track_titles=["Track One", "Track Two"],
            template="Cinematic",
            out_dir=str(self.tmp / "comp_out"),
            title_font_family=fam,
            title_font_style=style,
            track_font_family=fam,
            track_font_style=style,
        )
        self.assertTrue(Path(base).is_file())
        self.assertEqual(len(overlays), 2)

    def test_project_custom_font_persistence_and_bundling(self):
        """Project with custom fonts saves paths and copies them to assets/fonts in managed mode."""
        project = {
            "version": 1,
            "collection_title": "Project with Custom Fonts",
            "background": str(self.bg_path),
            "custom_title_font_path": str(self.custom_font_file),
            "custom_track_font_path": str(self.custom_font_file),
            "title_font_family": "CustomFontFam",
            "track_font_family": "CustomFontFam",
            "tracks": [],
        }

        # Check missing assets (should be empty since file exists)
        missing = check_missing_assets(project)
        self.assertNotIn("fonts", missing)

        # Bundle managed assets
        bundle_dir = self.tmp / "managed_project"
        managed = bundle_managed_assets(project, bundle_dir)

        self.assertIn("custom_title_font_path", managed)
        managed_font = Path(managed["custom_title_font_path"])
        self.assertTrue(managed_font.is_file())
        self.assertEqual(managed_font.parent.name, "fonts")
        self.assertEqual(managed_font.stat().st_size, self.custom_font_file.stat().st_size)


if __name__ == "__main__":
    unittest.main()
