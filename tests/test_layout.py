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
        self.win.close()
        self.win.deleteLater()
        _get_app().processEvents()

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


if __name__ == "__main__":
    unittest.main()
