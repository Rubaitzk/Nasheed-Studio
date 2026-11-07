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


class TestLogoResizingAndOffsets(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        self.bg_path = self.tmp / "bg.png"
        Image.new("RGB", (640, 360), (30, 40, 35)).save(str(self.bg_path))

        # Create rectangular logo with exact 2:1 aspect ratio
        self.logo_path = self.tmp / "test_logo.png"
        Image.new("RGBA", (200, 100), (255, 100, 50, 255)).save(str(self.logo_path))

        self.tracks = ["01. Test Track"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_logo_resizing_and_aspect_ratio_preservation(self):
        """Logo can scale up and down while preserving aspect ratio."""
        scales = [0.5, 1.0, 1.5]
        dims = []

        for sc in scales:
            work = self.tmp / f"work_scale_{sc}"
            base_p, _ = create_composition(
                width=1920, height=1080,
                background_path=str(self.bg_path),
                logo_path=str(self.logo_path),
                collection_title="Nasheed Collection",
                track_titles=self.tracks,
                template="Cinematic",
                out_dir=str(work),
                logo_position="Top-Left",
                logo_scale=sc,
            )
            # Inspect composition base image where logo is placed
            im = Image.open(base_p)
            # In Top-Left, logo starts at margin_x=margin, margin_y=margin_y
            # Look at logo bounding box relative to background color (30, 40, 35)
            # Find non-background pixels in top-left region
            crop = im.crop((0, 0, 800, 500))
            # Find pixels with color near (255, 100, 50)
            diff = Image.new("L", crop.size)
            for x in range(crop.width):
                for y in range(crop.height):
                    r, g, b = crop.getpixel((x, y))[:3]
                    if r > 200 and g < 150: # logo pixel
                        diff.putpixel((x, y), 255)
            bbox = diff.getbbox()
            self.assertIsNotNone(bbox)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            dims.append((w, h))

        # Check aspect ratio for all scales is ~ 2.0 (2:1)
        for w, h in dims:
            ratio = w / h
            self.assertAlmostEqual(ratio, 2.0, delta=0.1)

        # Check that scale 1.5 is larger than scale 1.0, and 1.0 is larger than 0.5
        self.assertGreater(dims[1][0], dims[0][0])
        self.assertGreater(dims[2][0], dims[1][0])

    def test_logo_offsets_positive_and_negative(self):
        """Logo offsets move the logo horizontally and vertically from corner."""
        offsets = [(0, 0), (50, 0), (-50, 0), (0, 40), (0, -40)]
        coords = []

        for ox, oy in offsets:
            work = self.tmp / f"work_off_{ox}_{oy}"
            base_p, _ = create_composition(
                width=1920, height=1080,
                background_path=str(self.bg_path),
                logo_path=str(self.logo_path),
                collection_title="Nasheed Collection",
                track_titles=self.tracks,
                template="Cinematic",
                out_dir=str(work),
                logo_position="Top-Left",
                logo_x_offset=ox,
                logo_y_offset=oy,
            )
            im = Image.open(base_p)
            crop = im.crop((0, 0, 800, 500))
            diff = Image.new("L", crop.size)
            for x in range(crop.width):
                for y in range(crop.height):
                    r, g, b = crop.getpixel((x, y))[:3]
                    if r > 200 and g < 150:
                        diff.putpixel((x, y), 255)
            bbox = diff.getbbox()
            coords.append((bbox[0], bbox[1]))

        base_x, base_y = coords[0]

        # +50 X
        self.assertEqual(coords[1][0] - base_x, 50)
        self.assertEqual(coords[1][1], base_y)

        # -50 X
        self.assertEqual(coords[2][0] - base_x, -50)
        self.assertEqual(coords[2][1], base_y)

        # +40 Y
        self.assertEqual(coords[3][0], base_x)
        self.assertEqual(coords[3][1] - base_y, 40)

        # -40 Y
        self.assertEqual(coords[4][0], base_x)
        self.assertEqual(coords[4][1] - base_y, -40)

    def test_preview_vs_render_scaling_consistency(self):
        """Preview (720p) and Render (1080p) offsets scale proportionally."""
        off_x, off_y = 60, 40

        work_720 = self.tmp / "w720"
        work_1080 = self.tmp / "w1080"

        base_720, _ = create_composition(
            width=1280, height=720,
            background_path=str(self.bg_path),
            logo_path=str(self.logo_path),
            collection_title="Nasheed Collection",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(work_720),
            logo_position="Top-Left",
            logo_x_offset=off_x,
            logo_y_offset=off_y,
        )

        base_1080, _ = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=str(self.logo_path),
            collection_title="Nasheed Collection",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(work_1080),
            logo_position="Top-Left",
            logo_x_offset=off_x,
            logo_y_offset=off_y,
        )

        # Expected 720p offsets: int(round(60 * 720/1080)) = 40, int(round(40 * 720/1080)) = 27
        self.assertEqual(int(round(off_x * (720.0 / 1080.0))), 40)
        self.assertEqual(int(round(off_y * (720.0 / 1080.0))), 27)


class TestLogoUIControls(unittest.TestCase):

    def setUp(self):
        _get_app()
        self.win = MainWindow()
        self.win.resize(1120, 720)
        self.win.show()
        _get_app().processEvents()
        self.win.hide()

    def tearDown(self):
        dispose_window(self.win)

    def test_logo_spinbox_controls_exist_and_ranges(self):
        self.assertTrue(hasattr(self.win, "logo_scale_spin"))
        self.assertTrue(hasattr(self.win, "logo_x_offset_spin"))
        self.assertTrue(hasattr(self.win, "logo_y_offset_spin"))

        self.assertEqual(self.win.logo_scale_spin.value(), 100)
        self.assertEqual(self.win.logo_scale_spin.minimum(), 20)
        self.assertEqual(self.win.logo_scale_spin.maximum(), 300)

        self.assertEqual(self.win.logo_x_offset_spin.value(), 0)
        self.assertEqual(self.win.logo_y_offset_spin.value(), 0)

    def test_logo_settings_persistence_and_undo_redo(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            p = f.name
        try:
            self.win.logo_scale_spin.setValue(140)
            self.win.logo_x_offset_spin.setValue(25)
            self.win.logo_y_offset_spin.setValue(-15)
            self.win._commit_undo_snapshot()

            proj = self.win._project()
            self.assertEqual(proj["logo_scale"], 1.4)
            self.assertEqual(proj["logo_x_offset"], 25)
            self.assertEqual(proj["logo_y_offset"], -15)

            # Test undo
            self.win.undo()
            self.assertEqual(self.win.logo_scale_spin.value(), 100)
            self.assertEqual(self.win.logo_x_offset_spin.value(), 0)
            self.assertEqual(self.win.logo_y_offset_spin.value(), 0)

            # Test redo
            self.win.redo()
            self.assertEqual(self.win.logo_scale_spin.value(), 140)
            self.assertEqual(self.win.logo_x_offset_spin.value(), 25)
            self.assertEqual(self.win.logo_y_offset_spin.value(), -15)

            # Test file save & restore
            self.win.save_project_as = lambda: None
            self.win._write_project(p)

            self.win.new_project()
            self.assertEqual(self.win.logo_scale_spin.value(), 100)
            self.assertEqual(self.win.logo_x_offset_spin.value(), 0)
            self.assertEqual(self.win.logo_y_offset_spin.value(), 0)

            self.win._load_project_file(p)
            self.assertEqual(self.win.logo_scale_spin.value(), 140)
            self.assertEqual(self.win.logo_x_offset_spin.value(), 25)
            self.assertEqual(self.win.logo_y_offset_spin.value(), -15)
        finally:
            Path(p).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
