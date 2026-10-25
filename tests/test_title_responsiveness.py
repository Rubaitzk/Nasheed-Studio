"""
Regression tests for Playlist / Collection Title editing UX:
Explicit Apply + Debounced Preview (1.5s - 2s delay).

Verifies:
1. Typing draft: updates only input field, enables Apply button, does NOT call preview or update committed title.
2. Clicking Apply button: commits title, updates preview, disables Apply button.
3. Pressing Enter (returnPressed): commits title, updates preview, disables Apply button.
4. Pressing Escape: cancels draft, reverts to committed title without marking project dirty.
5. Auto-apply timer (1.5s): single-shot timer automatically commits title after timeout.
6. Auto-commit on export / project serialization: unapplied draft is never silently lost.
7. Unsaved changes guard: draft detects unsaved changes before project switch/creation.
8. Empty string handling: graceful fallback to "Nasheed Collection" in project.
9. Repeated backspaces and typing: preserves UI thread responsiveness.
10. Pasting long text: preserved accurately without freeze or corruption.
"""

import sys
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt, QEvent, QCoreApplication
from PySide6.QtGui import QKeyEvent
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
        if hasattr(self.win, "_preview_timer"):
            self.win._preview_timer.stop()
        if hasattr(self.win, "_title_timer"):
            self.win._title_timer.stop()
        self.win.hide()

    def tearDown(self):
        from tests.conftest import dispose_window
        dispose_window(self.win)

    def test_typing_rapidly_updates_only_field_and_debounces(self):
        """Typing multiple characters rapidly does not synchronously refresh preview or commit title."""
        original_title = self.win._committed_title
        with patch.object(self.win, "_refresh_preview") as mock_refresh:
            self.win.collection_title.setText("T")
            self.win.collection_title.setText("Te")
            self.win.collection_title.setText("Tes")
            self.win.collection_title.setText("Test Title")

            # Input field has the draft
            self.assertEqual(self.win.collection_title.text(), "Test Title")
            # Apply button is enabled
            self.assertTrue(self.win.title_apply_btn.isEnabled())
            # Timer is active with 1500ms debounce
            self.assertTrue(self.win._title_timer.isActive())
            self.assertEqual(self.win._title_timer.interval(), 1500)
            # Preview was NOT called synchronously during typing
            self.assertEqual(mock_refresh.call_count, 0)
            # Committed title has NOT changed yet
            self.assertEqual(self.win._committed_title, original_title)

    def test_clicking_apply_commits_title_and_refreshes(self):
        """Clicking the Apply button commits the draft, refreshes preview, and disables the button."""
        with patch.object(self.win, "_refresh_preview") as mock_refresh:
            self.win.collection_title.setText("Applied By Button")
            self.assertTrue(self.win.title_apply_btn.isEnabled())

            self.win.title_apply_btn.click()

            self.assertEqual(self.win._committed_title, "Applied By Button")
            self.assertFalse(self.win.title_apply_btn.isEnabled())
            self.assertFalse(self.win._title_timer.isActive())
            self.assertEqual(mock_refresh.call_count, 1)

    def test_return_pressed_applies_title(self):
        """Pressing Enter in the title input field commits the draft and refreshes preview."""
        with patch.object(self.win, "_refresh_preview") as mock_refresh:
            self.win.collection_title.setText("Applied By Enter")
            self.win.collection_title.returnPressed.emit()

            self.assertEqual(self.win._committed_title, "Applied By Enter")
            self.assertFalse(self.win.title_apply_btn.isEnabled())
            self.assertEqual(mock_refresh.call_count, 1)

    def test_escape_key_cancels_draft_without_marking_dirty(self):
        """Pressing Escape restores previous committed title without marking project dirty."""
        initial_title = self.win._committed_title
        self.assertFalse(self.win._is_dirty)

        self.win.collection_title.setText("Temporary Draft To Discard")
        self.assertTrue(self.win.title_apply_btn.isEnabled())
        self.assertFalse(self.win._is_dirty)

        # Send Escape key press event to collection_title
        escape_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        handled = QCoreApplication.sendEvent(self.win.collection_title, escape_event)

        self.assertTrue(handled)
        self.assertEqual(self.win.collection_title.text(), initial_title)
        self.assertEqual(self.win._committed_title, initial_title)
        self.assertFalse(self.win.title_apply_btn.isEnabled())
        self.assertFalse(self.win._title_timer.isActive())
        self.assertFalse(self.win._is_dirty)

    def test_auto_apply_after_timeout(self):
        """Auto-apply single-shot timer commits title after inactivity timeout."""
        with patch.object(self.win, "_refresh_preview") as mock_refresh:
            self.win.collection_title.setText("Auto Committed Title")
            self.assertTrue(self.win._title_timer.isActive())

            # Simulate timer timeout
            self.win._title_timer.timeout.emit()

            self.assertEqual(self.win._committed_title, "Auto Committed Title")
            self.assertFalse(self.win.title_apply_btn.isEnabled())
            self.assertFalse(self.win._title_timer.isActive())
            self.assertEqual(mock_refresh.call_count, 1)

    def test_saving_or_project_commits_unapplied_draft(self):
        """Export or project serialization commits unapplied draft so work is never lost."""
        self.win.collection_title.setText("Pending Save Title")
        # Do not click apply or wait for timer
        self.assertTrue(self.win.title_apply_btn.isEnabled())

        proj = self.win._project()

        self.assertEqual(proj["collection_title"], "Pending Save Title")
        self.assertEqual(self.win._committed_title, "Pending Save Title")
        self.assertFalse(self.win.title_apply_btn.isEnabled())

    def test_unsaved_changes_detects_unapplied_draft(self):
        """has_unsaved_changes returns True when an uncommitted draft exists in the field."""
        self.assertFalse(self.win.has_unsaved_changes())

        self.win.collection_title.setText("Unsaved Draft")
        self.assertTrue(self.win.has_unsaved_changes())

        self.win._cancel_title_draft()
        self.assertFalse(self.win.has_unsaved_changes())

    def test_clearing_title_completely(self):
        """Clearing title completely handles empty string gracefully and uses fallback in project."""
        self.win.collection_title.setText("")
        self.win._apply_title()
        _get_app().processEvents()

        self.assertEqual(self.win.collection_title.text(), "")
        proj = self.win._project()
        self.assertEqual(proj["collection_title"], "Nasheed Collection")

    def test_typing_replacement_text(self):
        """Replacing text updates collection title accurately when applied."""
        new_title = "Prophetic Traditions Collection"
        self.win.collection_title.setText(new_title)
        self.win._apply_title()
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

        self.win._apply_title()
        self.assertEqual(self.win.collection_title.text(), "Peaceful Vocals")
        self.assertEqual(self.win._project()["collection_title"], "Peaceful Vocals")

    def test_pasting_long_title(self):
        """Pasting a very long title does not freeze or truncate unexpectedly."""
        long_title = "A" * 300
        self.win.collection_title.setText(long_title)
        self.win._apply_title()
        _get_app().processEvents()

        self.assertEqual(self.win.collection_title.text(), long_title)
        self.assertEqual(self.win._project()["collection_title"], long_title)


if __name__ == "__main__":
    unittest.main()
