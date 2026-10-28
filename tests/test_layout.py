"""
Bug A regression test – Layout: long filenames must not drive panel width.

Uses an offscreen Qt application so no real window is shown.
"""

import sys
import unittest

from PySide6.QtWidgets import QApplication

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestLongFilenameLayout(unittest.TestCase):
    """Left panel must stay within its configured bounds regardless of filename length."""

    MAX_LABEL_WIDTH = 280          # matches _make_asset_label
    MIN_LEFT_PANEL_WIDTH = 260     # matches left.setMinimumWidth

    def setUp(self):
        _get_app()
        from src.ui.main_window import MainWindow
        self.win = MainWindow()
        # Do not show the window; resize to the supported minimum.
        self.win.resize(1120, 720)
        # Force layout pass.
        self.win.show()
        _get_app().processEvents()
        self.win.hide()

    def tearDown(self):
        from tests.conftest import dispose_window
        dispose_window(self.win)

    def _long_path(self, n=120):
        return "/".join(["a" * 40] * 3) + "/" + ("x" * n) + ".png"

    def test_background_label_width_capped(self):
        """background_label width ≤ MAX_LABEL_WIDTH even with a 120-char filename."""
        from src.ui.main_window import MainWindow
        long_path = self._long_path()
        self.win.background_path = long_path
        self.win._set_asset_label(self.win.background_label, long_path)
        _get_app().processEvents()
        w = self.win.background_label.maximumWidth()
        self.assertLessEqual(w, self.MAX_LABEL_WIDTH,
                             f"background_label maximumWidth={w} exceeds {self.MAX_LABEL_WIDTH}")
        text = self.win.background_label.text()
        self.assertTrue("…" in text or "..." in text, "Displayed label text should contain an ellipsis")
        self.assertLess(len(text), len(long_path), "Displayed text should be truncated")

    def test_logo_label_width_capped(self):
        """logo_label width ≤ MAX_LABEL_WIDTH even with a 120-char filename."""
        long_path = self._long_path()
        self.win._set_asset_label(self.win.logo_label, long_path)
        _get_app().processEvents()
        w = self.win.logo_label.maximumWidth()
        self.assertLessEqual(w, self.MAX_LABEL_WIDTH,
                             f"logo_label maximumWidth={w} exceeds {self.MAX_LABEL_WIDTH}")
        text = self.win.logo_label.text()
        self.assertTrue("…" in text or "..." in text, "Displayed label text should contain an ellipsis")
        self.assertLess(len(text), len(long_path), "Displayed text should be truncated")

    def test_left_panel_minimum_width_preserved(self):
        """Left panel minimumWidth >= MIN_LEFT_PANEL_WIDTH after a long-filename import."""
        from PySide6.QtWidgets import QSplitter
        splitter = self.win.findChild(QSplitter)
        self.assertIsNotNone(splitter, "Could not find QSplitter in MainWindow")
        left_widget = splitter.widget(0)
        mw = left_widget.minimumWidth()
        self.assertGreaterEqual(mw, self.MIN_LEFT_PANEL_WIDTH,
                                f"Left panel minimumWidth={mw} < {self.MIN_LEFT_PANEL_WIDTH}")

    def test_tooltip_contains_full_path(self):
        """Full path is exposed via tooltip even when the label text is truncated."""
        long_path = self._long_path()
        self.win._set_asset_label(self.win.background_label, long_path)
        tooltip = self.win.background_label.toolTip()
        self.assertEqual(tooltip, long_path,
                         "Tooltip must contain the full path for background_label")

    def test_logo_tooltip_contains_full_path(self):
        long_path = self._long_path()
        self.win._set_asset_label(self.win.logo_label, long_path)
        tooltip = self.win.logo_label.toolTip()
        self.assertEqual(tooltip, long_path,
                         "Tooltip must contain the full path for logo_label")


class TestIntrinsicReferenceLayout(unittest.TestCase):
    """Verifies reference-accurate intrinsic column layout engine behaviors."""

    def test_auto_max_title_chars_never_truncates_on_pixel_width(self):
        """When track_max_chars is 0 (Auto), titles are NEVER truncated with '…' or '...' based on pixel width."""
        from src.services.compositor import calculate_playlist_layout
        long_titles = [
            "A Very Long Majestic Nasheed Title Exceeding Ninety Characters In Total Length For Studio Video Production",
            "Another Incredibly Lengthy Nasheed With Extended Descriptions And Comprehensive Name Annotations",
        ]
        layout = calculate_playlist_layout(
            track_titles=long_titles,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=1.45,
            playlist_width_ratio=0.55,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=38,
            track_wrap_text=False,
            track_max_chars=0,
        )
        for it in layout["track_items"]:
            self.assertNotIn("…", it["text"])
            self.assertNotIn("...", it["text"])

    def test_position_left_expands_across_full_usable_width(self):
        """Position: Left starts at margin_left (int(canvas_w * 0.035)) without artificial 45%/50% width caps."""
        from src.services.compositor import calculate_playlist_layout
        titles = [f"Track Number {i} With Very Broad Intrinsic String Measure" for i in range(12)]
        layout = calculate_playlist_layout(
            track_titles=titles,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=1.45,
            playlist_width_ratio=0.50,  # Even if UI ratio is 0.50, intrinsic widths expand up to full usable width
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=38,
            track_wrap_text=False,
            track_max_chars=0,
        )
        start_x = layout["track_items"][0]["x"]
        self.assertEqual(start_x, int(1920 * 0.035))
        # Total panel rect width can exceed 50% of canvas (960px) when intrinsic content needs it
        panel_w = layout["panel_rect"][2]
        self.assertGreater(panel_w, 960)

    def test_col_gap_pushes_column_2_without_shrinking_column_1(self):
        """Increasing col_gap shifts Column 2 to the right without reducing col_width[0] or col_width[1]."""
        from src.services.compositor import calculate_playlist_layout
        titles = [f"Track {i:02d} Spacing Test" for i in range(10)]
        l_gap40 = calculate_playlist_layout(
            track_titles=titles,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_col_spacing=40,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=38,
            track_wrap_text=False,
            track_max_chars=0,
            playlist_row_spacing=1.45,
            playlist_width_ratio=0.55,
            playlist_x_offset=0,
            playlist_y_offset=0,
        )
        l_gap120 = calculate_playlist_layout(
            track_titles=titles,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_col_spacing=120,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=38,
            track_wrap_text=False,
            track_max_chars=0,
            playlist_row_spacing=1.45,
            playlist_width_ratio=0.55,
            playlist_x_offset=0,
            playlist_y_offset=0,
        )
        # Col 0 width remains completely identical
        self.assertEqual(l_gap40["col_widths"][0], l_gap120["col_widths"][0])
        self.assertEqual(l_gap40["col_widths"][1], l_gap120["col_widths"][1])
        # Col 1 X position shifted right by exactly (120 - 40) = 80px
        col1_x_gap40 = l_gap40["track_items"][5]["x"]
        col1_x_gap120 = l_gap120["track_items"][5]["x"]
        self.assertEqual(col1_x_gap120 - col1_x_gap40, 80)

    def test_row_spacing_does_not_shrink_font_size(self):
        """Increasing row_spacing spaces rows out without shrinking font_size."""
        from src.services.compositor import calculate_playlist_layout
        titles = [f"Track {i:02d}" for i in range(10)]
        l_tight = calculate_playlist_layout(
            track_titles=titles,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=1.20,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=38,
            track_wrap_text=False,
            track_max_chars=0,
            playlist_width_ratio=0.55,
            playlist_x_offset=0,
            playlist_y_offset=0,
        )
        l_spacious = calculate_playlist_layout(
            track_titles=titles,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=2.20,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=38,
            track_wrap_text=False,
            track_max_chars=0,
            playlist_width_ratio=0.55,
            playlist_x_offset=0,
            playlist_y_offset=0,
        )
        self.assertEqual(l_tight["eff_track_size"], 38)
        self.assertEqual(l_spacious["eff_track_size"], 38)
        self.assertGreater(l_spacious["row_gap"], l_tight["row_gap"])

    def test_multi_column_distribution_matching_refer2(self):
        """20 tracks across 2 columns places 14 tracks in Column 1 and 6 tracks in Column 2 (matching refer 2.jpg)."""
        from src.services.compositor import calculate_playlist_layout
        titles = [f"Nasheed Title {i + 1:02d}" for i in range(20)]
        layout = calculate_playlist_layout(
            track_titles=titles,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=1.45,
            playlist_width_ratio=0.55,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=38,
            track_wrap_text=False,
            track_max_chars=0,
        )
        col0_tracks = [it for it in layout["track_items"] if it["col_index"] == 0]
        col1_tracks = [it for it in layout["track_items"] if it["col_index"] == 1]
        self.assertEqual(len(col0_tracks), 14)
        self.assertEqual(len(col1_tracks), 6)


if __name__ == "__main__":
    unittest.main()
