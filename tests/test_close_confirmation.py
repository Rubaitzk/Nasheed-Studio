"""
Regression tests for Stage 1: Prevent Accidental Loss When Closing Application.

Verifies:
1. Clean project closes without prompt.
2. Unsaved new project prompts for Save / Discard / Cancel.
3. Modified saved project prompts for Save / Discard / Cancel.
4. User clicks Cancel: window stays open (event.ignore()).
5. User clicks Discard: window closes (event.accept()), changes discarded.
6. User clicks Save and succeeds: project saved, window closes.
7. User clicks Save but cancels file dialog: window stays open.
8. User clicks Save but write fails: critical error shown, window stays open.
9. Close during active export rejected: window stays open, export remains running.
10. Close during active export accepted: export cancelled and joined, window closes.
11. Close during active export accepted but unsaved changes cancelled: export remains running, window stays open.
12. Recursive close event guard: second closeEvent while closing is ignored.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

from PySide6.QtCore import QEvent
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestCloseConfirmation(unittest.TestCase):

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

    def test_clean_project_closes_without_prompt(self):
        """Clean project with no unsaved changes closes normally with no dialogs."""
        self.assertFalse(self.win.has_unsaved_changes())
        event = QCloseEvent()

        with patch.object(QMessageBox, "warning") as mock_warn, \
             patch.object(QMessageBox, "question") as mock_quest:
            self.win.closeEvent(event)
            self.assertTrue(event.isAccepted())
            self.assertEqual(mock_warn.call_count, 0)
            self.assertEqual(mock_quest.call_count, 0)

    def test_unsaved_new_project_shows_warning(self):
        """Unsaved new project prompts with Save / Discard / Cancel dialog."""
        self.win.collection_title.setText("Modified New Title")
        self.assertTrue(self.win.has_unsaved_changes())
        event = QCloseEvent()

        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel) as mock_warn:
            self.win.closeEvent(event)
            self.assertFalse(event.isAccepted())
            mock_warn.assert_called_once()
            args = mock_warn.call_args[0]
            self.assertEqual(args[1], "Unsaved Changes")

    def test_modified_saved_project_shows_warning(self):
        """Saved project after modifications prompts with Save / Discard / Cancel dialog."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self.win._write_project(tmp_path)
            self.assertFalse(self.win.has_unsaved_changes())

            # Modify project
            self.win.collection_title.setText("Brand New Title")
            self.win._apply_title()
            self.assertTrue(self.win.has_unsaved_changes())

            event = QCloseEvent()
            with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel) as mock_warn:
                self.win.closeEvent(event)
                self.assertFalse(event.isAccepted())
                mock_warn.assert_called_once()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_dialog_cancel_keeps_window_open(self):
        """Clicking Cancel in unsaved changes dialog keeps the window open."""
        self.win._is_dirty = True
        event = QCloseEvent()

        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel):
            self.win.closeEvent(event)
            self.assertFalse(event.isAccepted())
            self.assertFalse(self.win._is_closing)

    def test_dialog_discard_closes_window_without_saving(self):
        """Clicking Discard closes window without saving changes."""
        self.win._is_dirty = True
        event = QCloseEvent()

        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Discard), \
             patch.object(self.win, "save_project") as mock_save:
            self.win.closeEvent(event)
            self.assertTrue(event.isAccepted())
            self.assertEqual(mock_save.call_count, 0)

    def test_dialog_save_succeeds_and_closes_window(self):
        """Clicking Save succeeds, saving project and closing window."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self.win.project_path = tmp_path
            self.win._is_dirty = True
            event = QCloseEvent()

            with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Save):
                self.win.closeEvent(event)
                self.assertTrue(event.isAccepted())
                self.assertFalse(self.win._is_dirty)
                # Verify file was written
                self.assertTrue(Path(tmp_path).is_file())
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_dialog_save_cancelled_in_file_dialog_keeps_window_open(self):
        """Clicking Save when user cancels file dialog keeps the window open."""
        self.win.project_path = ""
        self.win._is_dirty = True
        event = QCloseEvent()

        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Save), \
             patch.object(self.win, "save_project_as", return_value=False):
            self.win.closeEvent(event)
            self.assertFalse(event.isAccepted())
            self.assertTrue(self.win._is_dirty)
            self.assertFalse(self.win._is_closing)

    def test_dialog_save_failed_keeps_window_open(self):
        """Clicking Save when write fails with exception shows error and keeps window open."""
        self.win.project_path = "Z:\\NonExistentDirectory\\invalid_project.json"
        self.win._is_dirty = True
        event = QCloseEvent()

        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Save), \
             patch.object(QMessageBox, "critical") as mock_crit:
            self.win.closeEvent(event)
            self.assertFalse(event.isAccepted())
            mock_crit.assert_called_once()
            self.assertTrue(self.win._is_dirty)
            self.assertFalse(self.win._is_closing)

    def test_close_during_export_rejected_keeps_window_open(self):
        """When user declines to cancel running export, window stays open and export continues."""
        mock_job = MagicMock()
        mock_job.is_running = True
        self.win._job = mock_job
        event = QCloseEvent()

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            self.win.closeEvent(event)
            self.assertFalse(event.isAccepted())
            mock_job.cancel.assert_not_called()
            self.assertFalse(self.win._is_closing)

    def test_close_during_export_accepted_cancels_export_and_closes(self):
        """When user confirms export cancellation on clean project, export is cancelled and window closes."""
        mock_job = MagicMock()
        mock_job.is_running = True
        self.win._job = mock_job
        self.win._is_dirty = False
        event = QCloseEvent()

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.win.closeEvent(event)
            self.assertTrue(event.isAccepted())
            mock_job.cancel.assert_called_once()
            mock_job.join.assert_called_once()

    def test_close_during_export_accepted_but_unsaved_changes_cancelled(self):
        """When export cancel is confirmed but unsaved changes dialog is cancelled, export is NOT cancelled and window stays open."""
        mock_job = MagicMock()
        mock_job.is_running = True
        self.win._job = mock_job
        self.win._is_dirty = True
        event = QCloseEvent()

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
             patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel):
            self.win.closeEvent(event)
            self.assertFalse(event.isAccepted())
            # Job MUST NOT be cancelled because close was aborted
            mock_job.cancel.assert_not_called()
            self.assertFalse(self.win._is_closing)

    def test_recursive_close_event_ignored(self):
        """If closeEvent is invoked while _is_closing is already active, the re-entrant call is ignored."""
        self.win._is_closing = True
        event = QCloseEvent()
        self.win.closeEvent(event)
        self.assertFalse(event.isAccepted())


if __name__ == "__main__":
    unittest.main()
