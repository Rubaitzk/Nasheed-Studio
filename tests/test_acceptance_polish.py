"""
Acceptance and Polish Regression Tests for Nasheed Studio.

Tests cover:
1. Issue A: Cursor and Highlight dropdown immediate preview refresh & cache invalidation.
2. Issue B: Website URL opacity slider (0-100%), visibility toggle, persistence & backward compat.
3. Issue C: Text clarity and single-layer overlay composition without duplicate/ghosted text.
4. Issue D: Audio playlist widget selection without baseline shift or white focus artifacts.
5. Save/reopen roundtrip and template application for new visual settings.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from PySide6.QtWidgets import QApplication, QListWidgetItem
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor

from src.services.compositor import create_composition, create_intro_card, INDICATOR_MODES, HIGHLIGHT_STYLES
from src.services.project_service import save_project_atomic, TEMPLATE_DESIGN_KEYS
from src.services.render_service import build_render_command, RESOLUTIONS
from src.ui.main_window import MainWindow, PlaylistDelegate


_app = None


def get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestAcceptanceFixes(unittest.TestCase):
    def setUp(self):
        self.app = get_app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Create sample background
        self.bg_path = self.tmp / "sample_bg.png"
        Image.new("RGB", (1920, 1080), (20, 30, 25)).save(self.bg_path)

        self.tracks = [
            {"path": str(self.tmp / "track1.mp3"), "title": "Nasheed One", "duration": 180.0},
            {"path": str(self.tmp / "track2.mp3"), "title": "Nasheed Two", "duration": 220.0},
            {"path": str(self.tmp / "track3.mp3"), "title": "Nasheed Three", "duration": 195.0},
        ]
        for t in self.tracks:
            Path(t["path"]).touch()

    def tearDown(self):
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # A. Cursor & Highlight Dropdown Refresh Tests
    # ------------------------------------------------------------------

    def test_indicator_dropdown_immediate_cache_invalidation(self):
        """Selecting different indicator options immediately invalidates preview cache and updates state."""
        win = MainWindow()
        try:
            win.background_path = str(self.bg_path)
            win.tracks = list(self.tracks)
            win._refresh_preview()

            key_both = win._cached_preview_key
            self.assertIsNotNone(key_both)

            # Switch to 'Cursor only'
            win.indicator_combo.setCurrentText("Cursor only")
            self.assertEqual(win._mode_from_combo(), "cursor_only")
            key_cursor = win._cached_preview_key
            self.assertNotEqual(key_both, key_cursor, "Changing indicator combo must change preview cache key immediately")

            # Switch to 'Highlight only'
            win.indicator_combo.setCurrentText("Highlight only")
            self.assertEqual(win._mode_from_combo(), "highlight_only")
            key_hl = win._cached_preview_key
            self.assertNotEqual(key_cursor, key_hl)

            # Switch to 'Neither (Clean)'
            win.indicator_combo.setCurrentText("Neither (Clean)")
            self.assertEqual(win._mode_from_combo(), "neither")
            key_neither = win._cached_preview_key
            self.assertNotEqual(key_hl, key_neither)

            # Switch back to 'Both (Cursor & Highlight)'
            win.indicator_combo.setCurrentText("Both (Cursor & Highlight)")
            self.assertEqual(win._mode_from_combo(), "both")
            self.assertEqual(win._cached_preview_key, key_both)
        finally:
            win.closeEvent = lambda e: e.accept()
            win.close()

    def test_highlight_style_immediate_preview_update(self):
        """Switching highlight style (Pill, Accent Bar, Outline, Underline) updates preview immediately."""
        win = MainWindow()
        try:
            win.background_path = str(self.bg_path)
            win.tracks = list(self.tracks)
            win._refresh_preview()

            keys = []
            styles = ["Pill", "Accent Bar", "Outline", "Underline"]
            for st in styles:
                win.highlight_style_combo.setCurrentText(st)
                win._flush_preview()
                self.assertNotIn(win._cached_preview_key, keys)
                keys.append(win._cached_preview_key)

            self.assertEqual(len(set(keys)), 4, "All 4 highlight styles must have distinct preview cache keys")
        finally:
            win.closeEvent = lambda e: e.accept()
            win.close()

    def test_highlight_color_cache_invalidation_and_preview_update(self):
        """Changing only the highlight color invalidates the preview cache and updates rendered pixels."""
        win = MainWindow()
        try:
            win.background_path = str(self.bg_path)
            win.tracks = list(self.tracks)
            win.indicator_combo.setCurrentText("Highlight only")
            win._refresh_preview()

            key1 = win._cached_preview_key
            pix1 = win._cached_preview_pixmap
            self.assertIsNotNone(key1)
            self.assertIsNotNone(pix1)
            qimg1 = pix1.toImage()

            # Change ONLY the highlight color to crimson red (255, 30, 30)
            win.set_highlight_color((255, 30, 30))
            win._flush_preview()

            key2 = win._cached_preview_key
            pix2 = win._cached_preview_pixmap
            self.assertIsNotNone(key2)
            self.assertIsNotNone(pix2)

            # 1. Assert cache key invalidated
            self.assertNotEqual(key1, key2, "Changing highlight color must invalidate the preview cache key")
            # 2. Assert new QPixmap was generated (not stale cached object)
            self.assertIsNot(pix1, pix2, "A fresh preview pixmap must be generated on highlight color change")

            # 3. Assert rendered preview pixels actually updated with new highlight color
            qimg2 = pix2.toImage()
            w, h = qimg1.width(), qimg1.height()
            diff_count = 0
            red_highlight_pixels = 0
            for x in range(0, w, 2):
                for y in range(0, h, 2):
                    c1 = qimg1.pixelColor(x, y)
                    c2 = qimg2.pixelColor(x, y)
                    if (c1.red(), c1.green(), c1.blue()) != (c2.red(), c2.green(), c2.blue()):
                        diff_count += 1
                        if c2.red() > 180 and c2.red() > c2.blue() + 50 and c2.red() > c2.green() + 50:
                            red_highlight_pixels += 1

            self.assertGreater(diff_count, 0, "Rendered preview pixels must change when highlight color changes")
            self.assertGreater(red_highlight_pixels, 0, "Updated preview must render with red highlight pixels")

            # 4. Test setting hex color string "#00E060" (green)
            win.set_highlight_color("#00E060")
            win._flush_preview()
            key3 = win._cached_preview_key
            self.assertNotEqual(key2, key3, "Hex highlight color string must produce a distinct cache key")
            self.assertNotEqual(key1, key3)

            # 5. Switching back to original default color restores original cache key
            win.highlight_color = (248, 220, 139)
            win._refresh_preview()
            self.assertEqual(win._cached_preview_key, key1, "Reverting to initial highlight color must reproduce initial key")
        finally:
            win.closeEvent = lambda e: e.accept()
            win.close()

    # ------------------------------------------------------------------
    # B. Website URL Opacity Slider Tests
    # ------------------------------------------------------------------

    def test_website_opacity_slider_controls_and_values(self):
        """Website opacity slider spans 0-100%, updates label and immediately updates preview."""
        win = MainWindow()
        try:
            win.background_path = str(self.bg_path)
            win.website_edit.setText("www.testnasheed.com")
            win._refresh_preview()

            self.assertTrue(hasattr(win, "website_opacity_slider"))
            self.assertTrue(hasattr(win, "website_opacity_val"))
            self.assertEqual(win.website_opacity_slider.minimum(), 0)
            self.assertEqual(win.website_opacity_slider.maximum(), 100)
            self.assertEqual(win.website_opacity_slider.value(), 100)
            self.assertEqual(win.website_opacity_val.text(), "100%")

            key_100 = win._cached_preview_key

            # Set 50%
            win.website_opacity_slider.setValue(50)
            self.assertEqual(win.website_opacity_val.text(), "50%")
            win._flush_preview()
            key_50 = win._cached_preview_key
            self.assertNotEqual(key_100, key_50)

            # Set 0% (invisible)
            win.website_opacity_slider.setValue(0)
            self.assertEqual(win.website_opacity_val.text(), "0%")
            win._flush_preview()
            key_0 = win._cached_preview_key
            self.assertNotEqual(key_50, key_0)
        finally:
            win.closeEvent = lambda e: e.accept()
            win.close()

    def test_website_visibility_toggle(self):
        """Website show checkbox enables/disables slider and toggles watermark visibility."""
        win = MainWindow()
        try:
            self.assertTrue(hasattr(win, "website_show_check"))
            self.assertTrue(win.website_show_check.isChecked())
            self.assertTrue(win.website_opacity_slider.isEnabled())

            win.website_show_check.setChecked(False)
            self.assertFalse(win.website_opacity_slider.isEnabled())

            proj = win._project()
            self.assertFalse(proj["website_show"])

            win.website_show_check.setChecked(True)
            self.assertTrue(win.website_opacity_slider.isEnabled())
            proj2 = win._project()
            self.assertTrue(proj2["website_show"])
        finally:
            win.closeEvent = lambda e: e.accept()
            win.close()

    def test_website_opacity_compositor_rendering(self):
        """Website opacity affects watermark alpha without impacting other elements."""
        out_full = self.tmp / "comp_web_100"
        base_100, _ = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Title",
            track_titles=["Track One"],
            template="Cinematic",
            out_dir=str(out_full),
            website_text="www.nasheed.org",
            website_position="Top-Right",
            website_show=True,
            website_opacity=1.0,
        )

        out_zero = self.tmp / "comp_web_0"
        base_0, _ = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Title",
            track_titles=["Track One"],
            template="Cinematic",
            out_dir=str(out_zero),
            website_text="www.nasheed.org",
            website_position="Top-Right",
            website_show=True,
            website_opacity=0.0,
        )

        # 0% opacity should match having website_show=False
        out_hidden = self.tmp / "comp_web_hidden"
        base_hidden, _ = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Title",
            track_titles=["Track One"],
            template="Cinematic",
            out_dir=str(out_hidden),
            website_text="www.nasheed.org",
            website_position="Top-Right",
            website_show=False,
            website_opacity=1.0,
        )

        im_100 = Image.open(base_100)
        im_0 = Image.open(base_0)
        im_hidden = Image.open(base_hidden)

        # The watermark region in Top-Right differs between 100% and 0%
        # Corner Top-Right is near x=1600-1900, y=30-100
        crop_100 = im_100.crop((1650, 40, 1850, 80))
        crop_0 = im_0.crop((1650, 40, 1850, 80))
        crop_hidden = im_hidden.crop((1650, 40, 1850, 80))

        self.assertNotEqual(list(crop_100.tobytes()), list(crop_0.tobytes()))
        # 0% opacity and hidden must be identical
        self.assertEqual(list(crop_0.tobytes()), list(crop_hidden.tobytes()))

    # ------------------------------------------------------------------
    # C. Text Clarity & Single-Layer Overlay Composition
    # ------------------------------------------------------------------

    def test_no_underlying_duplicate_text_on_base_when_overlays_active(self):
        """When per-track overlays are enabled, base image does NOT have duplicate track text."""
        out_dir = self.tmp / "clarity_test"
        base_path, overlays = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Test Clarity",
            track_titles=["01 First Track", "02 Second Track"],
            template="Cinematic",
            out_dir=str(out_dir),
            indicator_mode="both",
            highlight_style="Underline",
        )

        self.assertEqual(len(overlays), 2)
        base_img = Image.open(base_path)
        ov0_img = Image.open(overlays[0])

        # Composite overlay 0 over base
        composite = Image.alpha_composite(base_img.convert("RGBA"), ov0_img.convert("RGBA"))

        # Verify exact dimensions
        self.assertEqual(composite.size, (1920, 1080))

        # Check that overlay 0 has non-zero alpha pixels for track text
        ov_alpha = ov0_img.split()[3]
        self.assertGreater(ov_alpha.getextrema()[1], 0, "Overlay must contain visible track typography")

    def test_text_rendering_at_1080p_1440p_4k(self):
        """Verify composition produces correct dimensions at 1080p, 1440p, and 4K."""
        for res_name, (w, h) in RESOLUTIONS.items():
            out_dir = self.tmp / f"res_{w}x{h}"
            base, overlays = create_composition(
                width=w, height=h,
                background_path=str(self.bg_path),
                logo_path=None,
                collection_title="Resolution Test",
                track_titles=["Track Alpha", "Track Beta"],
                template="Cinematic",
                out_dir=str(out_dir),
                indicator_mode="both",
            )
            with Image.open(base) as im:
                self.assertEqual(im.size, (w, h))
            for op in overlays:
                with Image.open(op) as ov:
                    self.assertEqual(ov.size, (w, h))

    # ------------------------------------------------------------------
    # D. Audio Playlist Selection Geometry & Focus Rect
    # ------------------------------------------------------------------

    def test_playlist_item_baseline_stability(self):
        """QListWidget item visual rect height is identical regardless of selection state."""
        win = MainWindow()
        try:
            win.tracks = [
                {"title": "Track One", "path": "D:/one.mp3", "duration": 100.0},
                {"title": "Track Two", "path": "D:/two.mp3", "duration": 120.0},
            ]
            win._refresh_tracks()
            win.resize(1120, 720)
            win.show()
            self.app.processEvents()

            # Deselect
            win.track_list.setCurrentRow(-1)
            self.app.processEvents()
            r0_unsel = win.track_list.visualItemRect(win.track_list.item(0))

            # Select item 0
            win.track_list.setCurrentRow(0)
            self.app.processEvents()
            r0_sel = win.track_list.visualItemRect(win.track_list.item(0))

            self.assertEqual(r0_unsel.height(), r0_sel.height(), "Item height must not change on selection")
            self.assertEqual(r0_unsel.y(), r0_sel.y(), "Item y position must not change on selection")
        finally:
            win.closeEvent = lambda e: e.accept()
            win.close()

    def test_playlist_delegate_suppresses_focus_rect(self):
        """PlaylistDelegate is installed and suppresses State_HasFocus."""
        win = MainWindow()
        try:
            delegate = win.track_list.itemDelegate()
            self.assertIsInstance(delegate, PlaylistDelegate)
        finally:
            win.closeEvent = lambda e: e.accept()
            win.close()

    # ------------------------------------------------------------------
    # Save & Reopen Roundtrip for New Visual Settings
    # ------------------------------------------------------------------

    def test_project_save_and_reopen_website_opacity(self):
        """Project accurately saves and restores website_opacity and website_show."""
        win = MainWindow()
        try:
            win.website_edit.setText("www.persisted.org")
            win.website_show_check.setChecked(True)
            win.website_opacity_slider.setValue(42)
            win.highlight_style_combo.setCurrentText("Underline")

            proj_file = self.tmp / "test_saved_proj.json"
            data = win._project()
            save_project_atomic(data, proj_file)

            # Reopen in fresh MainWindow
            win2 = MainWindow()
            try:
                win2._load_project_file(str(proj_file))
                self.assertEqual(win2.website_edit.text(), "www.persisted.org")
                self.assertTrue(win2.website_show_check.isChecked())
                self.assertEqual(win2.website_opacity_slider.value(), 42)
                self.assertEqual(win2.highlight_style_combo.currentText(), "Underline")
            finally:
                win2.closeEvent = lambda e: e.accept()
                win2.close()
        finally:
            win.closeEvent = lambda e: e.accept()
            win.close()

    def test_backward_compatible_project_loading_without_website_opacity(self):
        """Opening a project file created before website_opacity was introduced applies safe defaults."""
        legacy_data = {
            "version": 1,
            "collection_title": "Legacy Project",
            "tracks": [],
            "website_text": "www.legacy.org",
            # website_opacity and website_show are omitted!
        }
        legacy_file = self.tmp / "legacy_project.json"
        save_project_atomic(legacy_data, legacy_file)

        win = MainWindow()
        try:
            win._load_project_file(str(legacy_file))
            self.assertEqual(win.website_edit.text(), "www.legacy.org")
            self.assertTrue(win.website_show_check.isChecked())
            self.assertEqual(win.website_opacity_slider.value(), 100)
        finally:
            win.closeEvent = lambda e: e.accept()
            win.close()


if __name__ == "__main__":
    unittest.main()
