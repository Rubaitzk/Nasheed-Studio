"""
Regression tests for Task A (Playlist / Collection Title editing responsiveness).

Verifies:
1. Debouncing preview updates: rapid keystrokes do not invoke expensive composition on every character.
2. Clearing title completely: handles empty string gracefully without crash or freeze.
3. Typing replacement text: updates UI immediately without freezing.
4. Repeated Backspace & typing: keeps UI thread responsive.
5. Pasting long text: preserved accurately in model and project dictionary without corruption.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock

from PySide6.QtWidgets import QApplication

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestTitleResponsiveness(unittest.TestCase):

    def setUp(self):
        _get_app()
        from src.ui.main_window import MainWindow
        self.win = MainWindow()
        self.win.resize(1120, 720)
        self.win.show()
        _get_app().processEvents()
        self.win.hide()

    def tearDown(self):
        if self.win._preview_timer.isActive():
            self.win._preview_timer.stop()
        self.win.close()
        self.win.deleteLater()
        _get_app().processEvents()

    def test_typing_rapidly_debounces_preview(self):
        """Typing multiple characters rapidly restarts timer and does not synchronously refresh preview."""
        with patch.object(self.win, "_refresh_preview") as mock_refresh:
            self.win.collection_title.setText("T")
            self.win.collection_title.setText("Te")
            self.win.collection_title.setText("Tes")
            self.win.collection_title.setText("Test")
            # Should have scheduled timer but NOT immediately called _refresh_preview 4 times
            self.assertTrue(self.win._preview_timer.isActive())
            self.assertEqual(mock_refresh.call_count, 0)

            # Once the timer fires or is flushed, _refresh_preview is called once
            self.win._flush_preview()
            self.assertEqual(mock_refresh.call_count, 1)

    def test_clearing_title_completely(self):
        """Clearing title completely handles empty string gracefully and updates project state."""
        self.win.collection_title.setText("")
        self.win._flush_preview()
        _get_app().processEvents()
        self.assertEqual(self.win.collection_title.text(), "")
        # Fallback collection title is used in project
        proj = self.win._project()
        self.assertEqual(proj["collection_title"], "Nasheed Collection")

    def test_typing_replacement_text(self):
        """Replacing text updates collection title accurately in project."""
        new_title = "Prophetic Traditions Collection"
        self.win.collection_title.setText(new_title)
        self.win._flush_preview()
        _get_app().processEvents()
        self.assertEqual(self.win.collection_title.text(), new_title)
        self.assertEqual(self.win._project()["collection_title"], new_title)

    def test_repeated_backspace_and_typing(self):
        """Simulating repeated backspace and typing maintains responsiveness and accurate final text."""
        initial = "Nasheed Track"
        self.win.collection_title.setText(initial)
        # Simulate backspaces
        for i in range(len(initial), 0, -1):
            self.win.collection_title.setText(initial[:i])
            _get_app().processEvents()
        self.win.collection_title.setText("")
        _get_app().processEvents()

        # Simulate typing new text
        for ch in "Peaceful Vocals":
            current = self.win.collection_title.text() + ch
            self.win.collection_title.setText(current)
            _get_app().processEvents()

        self.win._flush_preview()
        self.assertEqual(self.win.collection_title.text(), "Peaceful Vocals")
        self.assertEqual(self.win._project()["collection_title"], "Peaceful Vocals")

    def test_pasting_long_title(self):
        """Pasting a very long title does not freeze or truncate unexpectedly."""
        long_title = "A" * 300
        self.win.collection_title.setText(long_title)
        self.win._flush_preview()
        _get_app().processEvents()
        self.assertEqual(self.win.collection_title.text(), long_title)
        self.assertEqual(self.win._project()["collection_title"], long_title)


if __name__ == "__main__":
    unittest.main()
