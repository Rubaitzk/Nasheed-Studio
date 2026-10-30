import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.compositor import (
    _calculate_title_layout,
    compute_reference_playlist_layout,
    create_composition,
)
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window
from PySide6.QtWidgets import QApplication


class TestTitleAndPlaylistOffsets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.win = MainWindow()

    def tearDown(self):
        dispose_window(self.win)

    def test_big_title_zero_offset_preserves_default(self):
        lines0, font0, th0, coords0, b0 = _calculate_title_layout(
            collection_title="Spiritual Nasheed Collection",
            title_font_family="Segoe UI",
            title_font_style="Bold",
            title_font_size=46,
            norm_title_pos="Top-Center",
            width=1920,
            height=1080,
            margin=40,
            res_scale=1.0,
            logo_placed=False,
            logo_rect=None,
            usable_width=1800,
            playlist_x=60,
            title_x_offset=0,
            title_y_offset=0,
        )

        lines1, font1, th1, coords1, b1 = _calculate_title_layout(
            collection_title="Spiritual Nasheed Collection",
            title_font_family="Segoe UI",
            title_font_style="Bold",
            title_font_size=46,
            norm_title_pos="Top-Center",
            width=1920,
            height=1080,
            margin=40,
            res_scale=1.0,
            logo_placed=False,
            logo_rect=None,
            usable_width=1800,
            playlist_x=60,
        )

        self.assertEqual(coords0, coords1)
        self.assertEqual(b0, b1)

    def test_big_title_xy_offsets_shift_coordinates(self):
        _, _, _, coords_default, b_default = _calculate_title_layout(
            collection_title="Spiritual Nasheed Collection",
            title_font_family="Segoe UI",
            title_font_style="Bold",
            title_font_size=46,
            norm_title_pos="Top-Center",
            width=1920,
            height=1080,
            margin=40,
            res_scale=1.0,
            logo_placed=False,
            logo_rect=None,
            usable_width=1800,
            playlist_x=60,
            title_x_offset=0,
            title_y_offset=0,
        )

        _, _, _, coords_shifted, b_shifted = _calculate_title_layout(
            collection_title="Spiritual Nasheed Collection",
            title_font_family="Segoe UI",
            title_font_style="Bold",
            title_font_size=46,
            norm_title_pos="Top-Center",
            width=1920,
            height=1080,
            margin=40,
            res_scale=1.0,
            logo_placed=False,
            logo_rect=None,
            usable_width=1800,
            playlist_x=60,
            title_x_offset=75,
            title_y_offset=30,
        )

        self.assertEqual(coords_shifted[0][0], coords_default[0][0] + 75)
        self.assertEqual(coords_shifted[0][1], coords_default[0][1] + 30)
        self.assertEqual(b_shifted, b_default + 30)

    def test_big_title_resolution_scaling_preview_vs_render(self):
        # 1080p (res_scale = 1.0) with offset X=60, Y=30
        _, _, _, coords_1080, _ = _calculate_title_layout(
            collection_title="Nasheed",
            title_font_family="Segoe UI",
            title_font_style="Bold",
            title_font_size=46,
            norm_title_pos="Top-Left",
            width=1920,
            height=1080,
            margin=40,
            res_scale=1.0,
            logo_placed=False,
            logo_rect=None,
            usable_width=1800,
            playlist_x=60,
            title_x_offset=60,
            title_y_offset=30,
        )

        # 720p (res_scale = 720/1080 = 2/3) with same offset X=60, Y=30
        _, _, _, coords_720, _ = _calculate_title_layout(
            collection_title="Nasheed",
            title_font_family="Segoe UI",
            title_font_style="Bold",
            title_font_size=46,
            norm_title_pos="Top-Left",
            width=1280,
            height=720,
            margin=int(40 * 720 / 1080),
            res_scale=720 / 1080,
            logo_placed=False,
            logo_rect=None,
            usable_width=1200,
            playlist_x=40,
            title_x_offset=60,
            title_y_offset=30,
        )

        # Shift in 720p should be exactly 2/3 of shift in 1080p
        # 60 * (720/1080) = 40 px
        # 30 * (720/1080) = 20 px
        _, _, _, base_720, _ = _calculate_title_layout(
            collection_title="Nasheed",
            title_font_family="Segoe UI",
            title_font_style="Bold",
            title_font_size=46,
            norm_title_pos="Top-Left",
            width=1280,
            height=720,
            margin=int(40 * 720 / 1080),
            res_scale=720 / 1080,
            logo_placed=False,
            logo_rect=None,
            usable_width=1200,
            playlist_x=40,
            title_x_offset=0,
            title_y_offset=0,
        )

        self.assertEqual(coords_720[0][0] - base_720[0][0], 40)
        self.assertEqual(coords_720[0][1] - base_720[0][1], 20)

    def test_playlist_offsets_shift_track_rows_and_highlights(self):
        titles = ["01. Track One", "02. Track Two", "03. Track Three"]
        res_default = compute_reference_playlist_layout(
            track_titles=titles,
            canvas_size=(1920, 1080),
            cols=1,
            position="Left",
            playlist_x_offset=0,
            playlist_y_offset=0,
        )

        res_shifted = compute_reference_playlist_layout(
            track_titles=titles,
            canvas_size=(1920, 1080),
            cols=1,
            position="Left",
            playlist_x_offset=80,
            playlist_y_offset=-40,
        )

        row0_def = res_default.rows[0]
        row0_shift = res_shifted.rows[0]

        self.assertEqual(row0_shift.text_x, row0_def.text_x + 80)
        self.assertEqual(row0_shift.text_y, row0_def.text_y - 40)
        self.assertEqual(row0_shift.highlight_rect[0], row0_def.highlight_rect[0] + 80)
        self.assertEqual(row0_shift.highlight_rect[1], row0_def.highlight_rect[1] - 40)

    def test_offsets_support_long_titles_and_wrapping(self):
        long_title = "A Very Long Majestic Collection Title That Exceeds Normal Single Line Width For Testing"
        lines, _, _, coords, _ = _calculate_title_layout(
            collection_title=long_title,
            title_font_family="Segoe UI",
            title_font_style="Bold",
            title_font_size=46,
            norm_title_pos="Top-Center",
            width=1920,
            height=1080,
            margin=40,
            res_scale=1.0,
            logo_placed=False,
            logo_rect=None,
            usable_width=1800,
            playlist_x=60,
            title_x_offset=-50,
            title_y_offset=25,
        )
        self.assertGreaterEqual(len(lines), 2)
        for x, y in coords:
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)

    def test_ui_controls_persistence_and_undo_redo(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            p = f.name
        try:
            self.win.playlist_x_offset_spin.setValue(45)
            self.win.playlist_y_offset_spin.setValue(-30)
            self.win.title_x_offset_spin.setValue(-25)
            self.win.title_y_offset_spin.setValue(15)
            self.win._commit_undo_snapshot()

            proj = self.win._project()
            self.assertEqual(proj["playlist_x_offset"], 45)
            self.assertEqual(proj["playlist_y_offset"], -30)
            self.assertEqual(proj["title_x_offset"], -25)
            self.assertEqual(proj["title_y_offset"], 15)

            # Test undo reverts to 0
            self.win.undo()
            self.assertEqual(self.win.playlist_x_offset_spin.value(), 0)
            self.assertEqual(self.win.playlist_y_offset_spin.value(), 0)
            self.assertEqual(self.win.title_x_offset_spin.value(), 0)
            self.assertEqual(self.win.title_y_offset_spin.value(), 0)

            # Test redo restores values
            self.win.redo()
            self.assertEqual(self.win.playlist_x_offset_spin.value(), 45)
            self.assertEqual(self.win.playlist_y_offset_spin.value(), -30)
            self.assertEqual(self.win.title_x_offset_spin.value(), -25)
            self.assertEqual(self.win.title_y_offset_spin.value(), 15)

            # Test save to disk & reload
            self.win.save_project_as = lambda: None
            self.win._write_project(p)

            self.win.new_project()
            self.assertEqual(self.win.playlist_x_offset_spin.value(), 0)
            self.assertEqual(self.win.playlist_y_offset_spin.value(), 0)
            self.assertEqual(self.win.title_x_offset_spin.value(), 0)
            self.assertEqual(self.win.title_y_offset_spin.value(), 0)

            self.win._load_project_file(p)
            self.assertEqual(self.win.playlist_x_offset_spin.value(), 45)
            self.assertEqual(self.win.playlist_y_offset_spin.value(), -30)
            self.assertEqual(self.win.title_x_offset_spin.value(), -25)
            self.assertEqual(self.win.title_y_offset_spin.value(), 15)
        finally:
            Path(p).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
