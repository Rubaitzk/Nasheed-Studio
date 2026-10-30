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


if __name__ == "__main__":
    unittest.main()
