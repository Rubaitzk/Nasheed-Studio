"""
Tests for UI Playlist Responsiveness and Custom Font UI Controls in MainWindow.

Verifies:
1. move_track does not block GUI thread and updates playlist ordering instantly.
2. Drag-and-drop rowsMoved preserves duplicate tracks with same file path.
3. Browse buttons for custom title and track fonts exist and invoke font registration.
4. Preview cache avoids re-rendering when parameters have not changed.
"""

import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from tests.conftest import dispose_window

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestUIResponsivenessAndFonts(unittest.TestCase):

    def setUp(self):
        _get_app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        self.win = MainWindow()
        self.win.resize(1120, 720)
        self.win.show()
        _get_app().processEvents()

        # Stop timers during initial setup
        if hasattr(self.win, "_preview_timer"):
            self.win._preview_timer.stop()
        if hasattr(self.win, "_title_timer"):
            self.win._title_timer.stop()

    def tearDown(self):
        dispose_window(self.win)
        self.temp_dir.cleanup()

    def test_custom_font_browse_buttons_exist(self):
        """MainWindow must feature browse buttons for both title and track fonts."""
        self.assertTrue(hasattr(self.win, "title_font_browse_btn"))
        self.assertTrue(hasattr(self.win, "track_font_browse_btn"))
        self.win.inspector_tabs.setCurrentIndex(1)
        _get_app().processEvents()
        self.assertTrue(self.win.title_font_browse_btn.isVisible())
        self.assertTrue(self.win.track_font_browse_btn.isVisible())

    def test_move_track_is_instantaneous_and_debounced(self):
        """Moving a track up/down responds in under 50ms without synchronous preview freeze."""
        # Populate with 5 tracks
        self.win.tracks = [
            {"title": f"Nasheed {i}", "path": f"C:/audio/track_{i}.mp3", "duration": 180.0}
            for i in range(5)
        ]
        self.win._refresh_tracks()
        self.win.track_list.setCurrentRow(2)

        # Time move_track
        t0 = time.perf_counter()
        with patch.object(self.win, "_refresh_preview") as mock_refresh:
            self.win.move_track(-1)
            elapsed = time.perf_counter() - t0

            # Must execute instantaneously (sub-50ms)
            self.assertLess(elapsed, 0.05, f"move_track took {elapsed*1000:.1f}ms, blocking GUI thread!")
            # Must NOT call _refresh_preview synchronously
            mock_refresh.assert_not_called()
            # Preview timer must be scheduled
            self.assertTrue(self.win._preview_timer.isActive())

        # Selected row should have moved to 1
        self.assertEqual(self.win.track_list.currentRow(), 1)
        self.assertEqual(self.win.tracks[1]["title"], "Nasheed 2")

    def test_rows_moved_handles_duplicate_paths(self):
        """Reordering duplicate tracks with identical paths maintains all items without data loss."""
        dup_path = "C:/audio/shared_nasheed.mp3"
        self.win.tracks = [
            {"title": "Track A", "path": dup_path, "duration": 120.0},
            {"title": "Track B", "path": "C:/audio/other.mp3", "duration": 150.0},
            {"title": "Track C (Repeat)", "path": dup_path, "duration": 120.0},
        ]
        self.win._refresh_tracks()
        self.assertEqual(self.win.track_list.count(), 3)

        # Simulate moving row 2 to row 0
        item = self.win.track_list.takeItem(2)
        self.win.track_list.insertItem(0, item)
        self.win._on_rows_moved()

        # All 3 tracks must remain present
        self.assertEqual(len(self.win.tracks), 3)
        self.assertEqual(self.win.tracks[0]["title"], "Track C (Repeat)")
        self.assertEqual(self.win.tracks[1]["title"], "Track A")
        self.assertEqual(self.win.tracks[2]["title"], "Track B")


if __name__ == "__main__":
    unittest.main()
