"""
Regression tests for Task C (Recent Projects Selection & Management).

Verifies:
1. Saving or opening a project adds it to the recent projects list.
2. The recent projects list is ordered most-recent-first and deduplicated.
3. Attempting to open a missing/moved project shows an actionable warning and removes it from the list.
4. Opening a recent project prompts if there are unsaved changes.
5. Clearing recent projects empties the list.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestRecentProjects(unittest.TestCase):

    def setUp(self):
        _get_app()
        from src.ui.main_window import MainWindow
        self.win = MainWindow()
        self.win.resize(1120, 720)
        self.win.show()
        _get_app().processEvents()
        self.win.hide()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        # Clear recent projects for tests
        self.win._clear_recent_projects()

    def tearDown(self):
        if self.win._preview_timer.isActive():
            self.win._preview_timer.stop()
        self.win._clear_recent_projects()
        self.win.close()
        self.win.deleteLater()
        _get_app().processEvents()
        self.temp_dir.cleanup()

    def test_saving_adds_to_recent(self):
        """Saving a project adds it to the top of recent projects."""
        p1 = self.tmp_path / "proj1.json"
        self.win._write_project(str(p1))
        recents = self.win._get_recent_projects()
        self.assertIn(str(p1), recents)
        self.assertEqual(recents[0], str(p1))

    def test_recent_list_deduplicated_and_reordered(self):
        """Re-saving or re-opening a project moves it to the top without duplicates."""
        p1 = self.tmp_path / "proj1.json"
        p2 = self.tmp_path / "proj2.json"
        self.win._add_recent_project(str(p1))
        self.win._add_recent_project(str(p2))
        self.win._add_recent_project(str(p1))

        recents = self.win._get_recent_projects()
        self.assertEqual(len(recents), 2)
        self.assertEqual(recents[0], str(p1))
        self.assertEqual(recents[1], str(p2))

    def test_missing_recent_project_shows_warning_and_removes(self):
        """Selecting a missing recent project warns user and removes entry."""
        missing_path = self.tmp_path / "deleted.json"
        self.win._add_recent_project(str(missing_path))
        self.assertIn(str(missing_path), self.win._get_recent_projects())

        with patch("src.ui.main_window.QMessageBox.warning") as mock_warn:
            self.win.open_recent_project(str(missing_path))
            mock_warn.assert_called_once()

        # Must be removed from recent projects
        self.assertNotIn(str(missing_path), self.win._get_recent_projects())

    def test_opening_recent_respects_unsaved_changes_guard(self):
        """Opening a recent project warns if current project has unsaved changes."""
        valid_proj = self.tmp_path / "other.json"
        valid_proj.write_text(json.dumps({"version": 1, "tracks": []}), encoding="utf-8")
        self.win._add_recent_project(str(valid_proj))

        # Make current project dirty
        self.win.collection_title.setText("Dirty Current Project")
        self.assertTrue(self.win.has_unsaved_changes())

        with patch("src.ui.main_window.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.No) as mock_question:
            self.win.open_recent_project(str(valid_proj))
            mock_question.assert_called_once()
            # Since user clicked No, project path should not have changed
            self.assertNotEqual(self.win.project_path, str(valid_proj))

    def test_clear_recent_projects(self):
        """Clearing recent projects removes all items and updates menu."""
        p1 = self.tmp_path / "proj.json"
        self.win._add_recent_project(str(p1))
        self.assertEqual(len(self.win._get_recent_projects()), 1)

        self.win._clear_recent_projects()
        self.assertEqual(len(self.win._get_recent_projects()), 0)


if __name__ == "__main__":
    unittest.main()
