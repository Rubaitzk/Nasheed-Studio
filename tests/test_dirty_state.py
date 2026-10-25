"""
Regression tests for Task B (Project Save & Dirty-State Behavior).

Required tests per brief:
1. Edit -> Save -> Create Project: no discard warning.
2. Edit -> Save -> Edit again -> Create Project: discard warning.
3. Modify an unsaved new project -> Create Project: discard warning.
4. Attempt a failed save -> Create Project: warning remains.
5. Open a saved project and make no edits -> Create Project: no unnecessary warning.
6. Open a saved project, modify it, and create another project: warning appears.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestDirtyState(unittest.TestCase):

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

    def tearDown(self):
        from tests.conftest import dispose_window
        dispose_window(self.win)
        self.temp_dir.cleanup()

    def test_1_edit_save_create_project_no_warning(self):
        """Edit -> Save -> Create Project: no discard warning."""
        # 1. Edit
        self.win.collection_title.setText("Edited Collection Title")
        self.win.tracks = [{"title": "T1", "path": "t1.mp3", "duration": 10.0}]
        self.assertTrue(self.win.has_unsaved_changes())

        # 2. Save
        save_file = self.tmp_path / "saved_proj.json"
        self.win._write_project(str(save_file))
        self.assertFalse(self.win.has_unsaved_changes())

        # 3. Create Project: QMessageBox.question must NOT be called
        with patch("src.ui.main_window.QMessageBox.question") as mock_question:
            self.win.new_project()
            mock_question.assert_not_called()

    def test_2_edit_save_edit_create_project_warning(self):
        """Edit -> Save -> Edit again -> Create Project: discard warning."""
        # 1. Edit & Save
        self.win.collection_title.setText("Title V1")
        save_file = self.tmp_path / "saved_proj_2.json"
        self.win._write_project(str(save_file))
        self.assertFalse(self.win.has_unsaved_changes())

        # 2. Edit again
        self.win.collection_title.setText("Title V2")
        self.assertTrue(self.win.has_unsaved_changes())

        # 3. Create Project: discard warning must appear
        with patch("src.ui.main_window.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes) as mock_question:
            self.win.new_project()
            mock_question.assert_called_once()

    def test_3_modify_unsaved_new_project_create_project_warning(self):
        """Modify an unsaved new project -> Create Project: discard warning."""
        self.win.background_path = "some_bg.jpg"
        self.assertTrue(self.win.has_unsaved_changes())

        with patch("src.ui.main_window.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes) as mock_question:
            self.win.new_project()
            mock_question.assert_called_once()

    def test_4_failed_save_create_project_warning_remains(self):
        """Attempt a failed save -> Create Project: warning remains."""
        self.win.collection_title.setText("Unsaved Important Work")
        self.win._mark_dirty()
        self.assertTrue(self.win.has_unsaved_changes())

        # Attempt to write to an illegal path to force save failure
        illegal_path = "Z:\\nonexistent_dir\\sub\\project.json"
        with patch("src.ui.main_window.QMessageBox.critical") as mock_crit:
            self.win._write_project(illegal_path)
            mock_crit.assert_called_once()

        # Dirty state must still remain True!
        self.assertTrue(self.win.has_unsaved_changes())

        with patch("src.ui.main_window.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.No) as mock_question:
            self.win.new_project()
            mock_question.assert_called_once()

    def test_5_open_saved_project_no_edits_create_project_no_warning(self):
        """Open a saved project and make no edits -> Create Project: no unnecessary warning."""
        proj_data = {
            "version": 1,
            "collection_title": "Opened Saved Collection",
            "background": "",
            "logo": "",
            "tracks": [{"title": "T1", "path": "t1.mp3", "duration": 5.0}],
            "template": "Cinematic",
            "resolution": "1080p · Full HD",
            "output_path": "out.mp4",
        }
        proj_file = self.tmp_path / "valid_proj.json"
        proj_file.write_text(json.dumps(proj_data), encoding="utf-8")

        self.win._load_project_file(str(proj_file))
        self.assertFalse(self.win.has_unsaved_changes())

        with patch("src.ui.main_window.QMessageBox.question") as mock_question:
            self.win.new_project()
            mock_question.assert_not_called()

    def test_6_open_saved_project_modify_create_project_warning(self):
        """Open a saved project, modify it, and create another project: warning appears."""
        proj_data = {
            "version": 1,
            "collection_title": "Opened Collection",
            "background": "",
            "logo": "",
            "tracks": [],
            "template": "Cinematic",
            "resolution": "1080p · Full HD",
            "output_path": "out.mp4",
        }
        proj_file = self.tmp_path / "open_modify.json"
        proj_file.write_text(json.dumps(proj_data), encoding="utf-8")

        self.win._load_project_file(str(proj_file))
        self.assertFalse(self.win.has_unsaved_changes())

        # Modify after opening
        self.win.collection_title.setText("Modified After Opening")
        self.assertTrue(self.win.has_unsaved_changes())

        with patch("src.ui.main_window.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes) as mock_question:
            self.win.new_project()
            mock_question.assert_called_once()


if __name__ == "__main__":
    unittest.main()
