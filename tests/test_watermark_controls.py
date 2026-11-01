import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.services.compositor import create_composition
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window

_app = None

def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestWatermarkControls(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Background image (dark gray)
        self.bg_path = self.tmp / "bg.png"
        Image.new("RGB", (640, 360), (30, 35, 40)).save(str(self.bg_path))

        self.tracks = ["01. Sample Track"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_watermark_default_and_explicit_colors(self):
        """Watermark respects default auto-contrast and explicit color settings."""
        # 1. Default (None)
        w_def = self.tmp / "w_def"
        base_def, _ = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(w_def),
            website_text="www.nasheedstudio.com",
            website_color=None,
        )
        self.assertTrue(Path(base_def).is_file())

        # 2. Explicit Cyan Color (#00FFCC)
        w_cyan = self.tmp / "w_cyan"
        base_cyan, _ = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(w_cyan),
            website_text="www.nasheedstudio.com",
            website_color="#00FFCC",
            website_position="Top-Right",
        )
        im_cyan = Image.open(base_cyan)
        crop_cyan = im_cyan.crop((1400, 0, 1920, 200))

        # Check for cyan pixels (high green & blue, low red)
        found_cyan = False
        for x in range(crop_cyan.width):
            for y in range(crop_cyan.height):
                r, g, b = crop_cyan.getpixel((x, y))[:3]
                if r < 50 and g > 200 and b > 180:
                    found_cyan = True
                    break
            if found_cyan:
                break
        self.assertTrue(found_cyan, "Explicit cyan watermark color must be rendered")

        # 3. Invalid color fallback safety
        w_inv = self.tmp / "w_inv"
        base_inv, _ = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(w_inv),
            website_text="www.nasheedstudio.com",
            website_color="invalid_garbage_color",
        )
        self.assertTrue(Path(base_inv).is_file(), "Invalid color string must not crash render")

    def test_watermark_offsets_positive_and_negative(self):
        """Watermark X and Y offsets move the watermark accurately."""
        # Top-Right corner: baseline (0, 0)
        offsets = [(0, 0), (-60, 0), (0, 40), (0, -20)]
        bboxes = []

        for ox, oy in offsets:
            work = self.tmp / f"work_web_{ox}_{oy}"
            base_p, _ = create_composition(
                width=1920, height=1080,
                background_path=str(self.bg_path),
                logo_path=None,
                collection_title="Nasheed Collection",
                track_titles=self.tracks,
                template="Cinematic",
                out_dir=str(work),
                website_text="WATERMARK_TEST",
                website_position="Top-Right",
                website_color="#FF0000", # Pure red for easy isolation
                website_x_offset=ox,
                website_y_offset=oy,
            )
            im = Image.open(base_p)
            crop = im.crop((1200, 0, 1920, 300))
            mask = Image.new("L", crop.size)
            for x in range(crop.width):
                for y in range(crop.height):
                    r, g, b = crop.getpixel((x, y))[:3]
                    if r > 180 and g < 50 and b < 50:
                        mask.putpixel((x, y), 255)
            bb = mask.getbbox()
            self.assertIsNotNone(bb)
            bboxes.append((1200 + bb[0], bb[1]))

        base_x, base_y = bboxes[0]

        # Shift X by -60 (moves left)
        self.assertEqual(bboxes[1][0] - base_x, -60)
        self.assertEqual(bboxes[1][1], base_y)

        # Shift Y by +40 (moves down)
        self.assertEqual(bboxes[2][0], base_x)
        self.assertEqual(bboxes[2][1] - base_y, 40)

        # Shift Y by -20 (moves up)
        self.assertEqual(bboxes[3][0], base_x)
        self.assertEqual(bboxes[3][1] - base_y, -20)


class TestWatermarkUIControls(unittest.TestCase):

    def setUp(self):
        _get_app()
        self.win = MainWindow()
        self.win.resize(1120, 720)
        self.win.show()
        _get_app().processEvents()
        self.win.hide()

    def tearDown(self):
        dispose_window(self.win)

    def test_watermark_ui_controls_exist_and_default_state(self):
        self.assertTrue(hasattr(self.win, "website_color_btn"))
        self.assertTrue(hasattr(self.win, "website_color_reset_btn"))
        self.assertTrue(hasattr(self.win, "website_x_offset_spin"))
        self.assertTrue(hasattr(self.win, "website_y_offset_spin"))

        self.assertIsNone(self.win.website_color)
        self.assertIn("Auto", self.win.website_color_btn.text())
        self.assertEqual(self.win.website_x_offset_spin.value(), 0)
        self.assertEqual(self.win.website_y_offset_spin.value(), 0)

    def test_watermark_color_change_and_reset(self):
        # Set color
        self.win.set_website_color((0, 255, 200))
        self.assertEqual(self.win.website_color, (0, 255, 200))
        self.assertIn("#00FFC8", self.win.website_color_btn.text().upper())

        # Reset color to Auto
        self.win.reset_website_color()
        self.assertIsNone(self.win.website_color)
        self.assertIn("Auto", self.win.website_color_btn.text())

    def test_watermark_persistence_and_undo_redo(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            p = f.name
        try:
            self.win.set_website_color((255, 180, 0))
            self.win.website_x_offset_spin.setValue(-45)
            self.win.website_y_offset_spin.setValue(30)
            self.win._commit_undo_snapshot()

            proj = self.win._project()
            self.assertEqual(proj["website_color"], (255, 180, 0))
            self.assertEqual(proj["website_x_offset"], -45)
            self.assertEqual(proj["website_y_offset"], 30)

            # Test first undo reverts spinbox offsets back to 0
            self.win.undo()
            self.assertEqual(self.win.website_color, (255, 180, 0))
            self.assertEqual(self.win.website_x_offset_spin.value(), 0)
            self.assertEqual(self.win.website_y_offset_spin.value(), 0)

            # Test second undo reverts color back to Auto (None)
            self.win.undo()
            self.assertIsNone(self.win.website_color)
            self.assertEqual(self.win.website_x_offset_spin.value(), 0)
            self.assertEqual(self.win.website_y_offset_spin.value(), 0)

            # Test redo restores color, then offsets
            self.win.redo()
            self.assertEqual(self.win.website_color, (255, 180, 0))
            self.win.redo()
            self.assertEqual(self.win.website_color, (255, 180, 0))
            self.assertEqual(self.win.website_x_offset_spin.value(), -45)
            self.assertEqual(self.win.website_y_offset_spin.value(), 30)

            # Test save & reload
            self.win.save_project_as = lambda: None
            self.win._write_project(p)

            self.win.new_project()
            self.assertIsNone(self.win.website_color)
            self.assertEqual(self.win.website_x_offset_spin.value(), 0)

            self.win._load_project_file(p)
            self.assertEqual(self.win.website_color, (255, 180, 0))
            self.assertEqual(self.win.website_x_offset_spin.value(), -45)
            self.assertEqual(self.win.website_y_offset_spin.value(), 30)
        finally:
            Path(p).unlink(missing_ok=True)

    def test_sound_section_watermark_propagation_to_export(self):
        """Watermark configured in Sound section propagates to export composition when project website_text is empty."""
        import wave
        from src.services.render_service import build_render_command

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            audio_path = tmp / "audio.wav"
            with wave.open(str(audio_path), "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(b"\x00" * 44100 * 2)

            bg_path = tmp / "bg.png"
            Image.new("RGB", (640, 360), (30, 35, 40)).save(str(bg_path))

            proj = {
                "version": 1,
                "collection_title": "Test Title",
                "background": str(bg_path),
                "background_type": "image",
                "tracks": [{"title": "Track 1", "path": str(audio_path), "duration": 1.0}],
                "template": "Cinematic",
                "output_path": str(tmp / "out.mp4"),
                "website_text": "",
                "intro_enabled": False,
                "intro_website_show": True,
                "intro_website_text": "www.SoundWatermarkTest.com",
                "intro_website_color": (0, 255, 200),
            }

            work_dir = tmp / "work_sound_wm"
            build_render_command(proj, work_dir)

            # Baseline blank composition (no watermark)
            blank_dir = tmp / "work_blank"
            proj_blank = dict(proj)
            proj_blank["intro_website_text"] = ""
            build_render_command(proj_blank, blank_dir)

            with Image.open(work_dir / "composition.png") as im_wm, Image.open(blank_dir / "composition.png") as im_blank:
                data_wm = list(im_wm.get_flattened_data() if hasattr(im_wm, "get_flattened_data") else im_wm.getdata())
                data_blank = list(im_blank.get_flattened_data() if hasattr(im_blank, "get_flattened_data") else im_blank.getdata())
                diff = [p1 != p2 for p1, p2 in zip(data_wm, data_blank)]
                self.assertTrue(any(diff), "Watermark set in Sound section must be rendered onto composition.png")

    def test_blank_intro_watermark_inherits_project_watermark_on_intro_card(self):
        """Blank intro_website_text inherits project website_text on intro card."""
        import wave
        from src.services.render_service import build_render_command

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            audio_path = tmp / "audio2.wav"
            with wave.open(str(audio_path), "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(b"\x00" * 44100 * 2)

            bg_path = tmp / "bg.png"
            Image.new("RGB", (640, 360), (30, 35, 40)).save(str(bg_path))

            proj = {
                "version": 1,
                "collection_title": "Test Title",
                "background": str(bg_path),
                "background_type": "image",
                "tracks": [{"title": "Track 1", "path": str(audio_path), "duration": 1.0}],
                "template": "Cinematic",
                "output_path": str(tmp / "out2.mp4"),
                "website_text": "www.ProjectWatermarkFallback.com",
                "website_show": True,
                "intro_enabled": True,
                "intro_website_show": True,
                "intro_website_text": "",  # Blank: must fallback to website_text
            }

            work_dir = tmp / "work_intro_inherit"
            build_render_command(proj, work_dir)

            intro_overlay = work_dir / "intro_overlay.png"
            self.assertTrue(intro_overlay.exists())
            with Image.open(intro_overlay) as im:
                bbox = im.crop((0, 700, 1920, 1080)).getbbox()
                self.assertIsNotNone(bbox, "Intro overlay must render watermark text when falling back to project watermark")

    def test_inspector_panel_no_horizontal_clipping(self):
        """Inspector panel tabs have no horizontally clipped widgets at startup or minimum size."""
        self.win.show()
        _get_app().processEvents()

        # Test at startup size
        for i in range(self.win.inspector_tabs.count()):
            self.win.inspector_tabs.setCurrentIndex(i)
            _get_app().processEvents()
            scroll = self.win.inspector_tabs.widget(i)
            viewport = scroll.viewport()
            content = scroll.widget()

            for child in content.findChildren(object):
                if hasattr(child, "geometry") and hasattr(child, "isVisible") and child.isVisible():
                    pos = child.mapTo(content, child.rect().topLeft())
                    right = pos.x() + child.width()
                    self.assertLessEqual(
                        right, viewport.width() + 1,
                        f"Widget {child.metaObject().className()} in Tab {i} overflows viewport width ({right} > {viewport.width()})"
                    )

        # Test at minimum window size (1120x720)
        self.win.resize(1120, 720)
        self.win.splitter.setSizes([260, 480, 356])
        _get_app().processEvents()

        for i in range(self.win.inspector_tabs.count()):
            self.win.inspector_tabs.setCurrentIndex(i)
            _get_app().processEvents()
            scroll = self.win.inspector_tabs.widget(i)
            viewport = scroll.viewport()
            content = scroll.widget()

            for child in content.findChildren(object):
                if hasattr(child, "geometry") and hasattr(child, "isVisible") and child.isVisible():
                    pos = child.mapTo(content, child.rect().topLeft())
                    right = pos.x() + child.width()
                    self.assertLessEqual(
                        right, viewport.width() + 1,
                        f"At 720p, widget {child.metaObject().className()} in Tab {i} overflows viewport width ({right} > {viewport.width()})"
                    )


if __name__ == "__main__":
    unittest.main()
