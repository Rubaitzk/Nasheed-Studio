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


class TestCursorXOffset(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Create dummy background
        self.bg_path = self.tmp / "bg.png"
        bg_img = Image.new("RGB", (640, 360), (30, 40, 35))
        bg_img.save(str(self.bg_path))

        self.tracks = ["01. First Nasheed", "02. Second Nasheed"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cursor_x_offset_zero_preserves_default(self):
        """Zero offset matches default cursor placement exactly."""
        work_default = self.tmp / "work_default"
        work_zero = self.tmp / "work_zero"

        # Baseline with omitted cursor_x_offset (defaults to 0)
        _, overlays_default = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(work_default),
            indicator_mode="cursor_only",
        )

        # Explicit cursor_x_offset = 0
        _, overlays_zero = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(work_zero),
            indicator_mode="cursor_only",
            cursor_x_offset=0,
        )

        img_def = Image.open(overlays_default[0])
        img_zero = Image.open(overlays_zero[0])

        bbox_def = img_def.getbbox()
        bbox_zero = img_zero.getbbox()

        self.assertEqual(bbox_def, bbox_zero, "Zero offset must produce identical bounding box to default")

    def test_cursor_x_offset_positive_and_negative_shifts(self):
        """Positive offset moves cursor right; negative offset moves cursor left."""
        work_base = self.tmp / "work_base"
        work_pos = self.tmp / "work_pos"
        work_neg = self.tmp / "work_neg"

        # 1080p has res_scale = 1.0, so offset pixels are 1:1
        _, ov_base = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(work_base),
            indicator_mode="cursor_only",
            cursor_x_offset=0,
        )

        _, ov_pos = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(work_pos),
            indicator_mode="cursor_only",
            cursor_x_offset=30,
        )

        _, ov_neg = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(work_neg),
            indicator_mode="cursor_only",
            cursor_x_offset=-30,
        )

        bbox_base = Image.open(ov_base[0]).getbbox()
        bbox_pos = Image.open(ov_pos[0]).getbbox()
        bbox_neg = Image.open(ov_neg[0]).getbbox()

        # bbox is (left, upper, right, lower)
        # Positive offset moves cursor to the right
        shift_pos = bbox_pos[0] - bbox_base[0]
        self.assertEqual(shift_pos, 30, "Cursor must shift right by exactly 30px at 1080p")
        # Vertical position must be unchanged
        self.assertEqual(bbox_pos[1], bbox_base[1])
        self.assertEqual(bbox_pos[3], bbox_base[3])

        # Negative offset moves cursor to the left
        shift_neg = bbox_neg[0] - bbox_base[0]
        self.assertEqual(shift_neg, -30, "Cursor must shift left by exactly 30px at 1080p")
        # Vertical position must be unchanged
        self.assertEqual(bbox_neg[1], bbox_base[1])
        self.assertEqual(bbox_neg[3], bbox_base[3])

    def test_resolution_scaled_consistency(self):
        """Offset scales proportionally with resolution (720p preview vs 1080p render vs 4K)."""
        offset = 40

        # 720p (preview): res_scale = 720 / 1080 = 2/3
        work_720_0 = self.tmp / "work_720_0"
        work_720_off = self.tmp / "work_720_off"
        _, ov_720_0 = create_composition(
            width=1280, height=720,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            template="Cinematic",
            track_titles=self.tracks,
            out_dir=str(work_720_0),
            indicator_mode="cursor_only",
            cursor_x_offset=0,
        )
        _, ov_720_off = create_composition(
            width=1280, height=720,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            template="Cinematic",
            track_titles=self.tracks,
            out_dir=str(work_720_off),
            indicator_mode="cursor_only",
            cursor_x_offset=offset,
        )

        # 4K UHD: res_scale = 2160 / 1080 = 2.0
        work_4k_0 = self.tmp / "work_4k_0"
        work_4k_off = self.tmp / "work_4k_off"
        _, ov_4k_0 = create_composition(
            width=3840, height=2160,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            template="Cinematic",
            track_titles=self.tracks,
            out_dir=str(work_4k_0),
            indicator_mode="cursor_only",
            cursor_x_offset=0,
        )
        _, ov_4k_off = create_composition(
            width=3840, height=2160,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            template="Cinematic",
            track_titles=self.tracks,
            out_dir=str(work_4k_off),
            indicator_mode="cursor_only",
            cursor_x_offset=offset,
        )

        b720_0 = Image.open(ov_720_0[0]).getbbox()
        b720_off = Image.open(ov_720_off[0]).getbbox()
        expected_720_shift = int(round(offset * (720.0 / 1080.0)))
        actual_720_shift = b720_off[0] - b720_0[0]
        self.assertEqual(actual_720_shift, expected_720_shift)

        b4k_0 = Image.open(ov_4k_0[0]).getbbox()
        b4k_off = Image.open(ov_4k_off[0]).getbbox()
        expected_4k_shift = int(round(offset * (2160.0 / 1080.0)))
        actual_4k_shift = b4k_off[0] - b4k_0[0]
        self.assertEqual(actual_4k_shift, expected_4k_shift)


class TestCursorXOffsetUI(unittest.TestCase):

    def setUp(self):
        _get_app()
        self.win = MainWindow()
        self.win.resize(1120, 720)
        self.win.show()
        _get_app().processEvents()
        self.win.hide()

    def tearDown(self):
        dispose_window(self.win)

    def test_spinbox_properties_and_initial_value(self):
        self.assertTrue(hasattr(self.win, "cursor_x_offset_spin"))
        spin = self.win.cursor_x_offset_spin
        self.assertEqual(spin.minimum(), -100)
        self.assertEqual(spin.maximum(), 100)
        self.assertEqual(spin.value(), 0)
        self.assertEqual(spin.suffix(), " px")

    def test_persistence_in_project_dict(self):
        self.win.cursor_x_offset_spin.setValue(25)
        proj = self.win._project()
        self.assertIn("cursor_x_offset", proj)
        self.assertEqual(proj["cursor_x_offset"], 25)

    def test_save_and_restore_project_state(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.win.cursor_x_offset_spin.setValue(-35)
            self.win.save_project_as = lambda: None
            self.win._write_project(path)

            # Reset project
            self.win.new_project()
            self.assertEqual(self.win.cursor_x_offset_spin.value(), 0)

            # Reload project
            self.win._load_project_file(path)
            self.assertEqual(self.win.cursor_x_offset_spin.value(), -35)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_undo_redo_cursor_x_offset(self):
        initial = self.win.cursor_x_offset_spin.value()
        self.assertEqual(initial, 0)

        # Change offset
        self.win.cursor_x_offset_spin.setValue(45)
        self.win._commit_undo_snapshot()
        self.assertEqual(self.win.cursor_x_offset_spin.value(), 45)

        # Undo
        self.win.undo()
        self.assertEqual(self.win.cursor_x_offset_spin.value(), 0)

        # Redo
        self.win.redo()
        self.assertEqual(self.win.cursor_x_offset_spin.value(), 45)


if __name__ == "__main__":
    unittest.main()
