import sys
import unittest
from pathlib import Path
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from tests.conftest import dispose_window

_app = None

def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestUndoRedoAndShortcuts(unittest.TestCase):

    def setUp(self):
        _get_app()
        self.win = MainWindow()
        self.win.resize(1120, 720)
        self.win.show()
        _get_app().processEvents()
        self.win.hide()

    def tearDown(self):
        dispose_window(self.win)

    def test_initial_undo_redo_state(self):
        # At start, undo stack has 1 base snapshot, redo is empty
        self.assertEqual(len(self.win._undo_stack), 1)
        self.assertEqual(len(self.win._redo_stack), 0)
        self.assertFalse(self.win.undo_act.isEnabled())
        self.assertFalse(self.win.redo_act.isEnabled())

    def test_undo_redo_tracks(self):
        # Add tracks to simulate import
        self.win.tracks.append({"title": "Nasheed One", "path": "track1.mp3", "duration": 120.0})
        self.win.tracks.append({"title": "Nasheed Two", "path": "track2.mp3", "duration": 180.0})
        self.win._commit_undo_snapshot()
        self.win._refresh_tracks()

        self.assertEqual(len(self.win.tracks), 2)
        self.assertTrue(self.win.undo_act.isEnabled())
        self.assertFalse(self.win.redo_act.isEnabled())

        # Undo adding tracks
        self.win.undo()
        self.assertEqual(len(self.win.tracks), 0)
        self.assertFalse(self.win.undo_act.isEnabled())
        self.assertTrue(self.win.redo_act.isEnabled())

        # Redo adding tracks
        self.win.redo()
        self.assertEqual(len(self.win.tracks), 2)
        self.assertEqual(self.win.tracks[0]["title"], "Nasheed One")
        self.assertEqual(self.win.tracks[1]["title"], "Nasheed Two")
        self.assertTrue(self.win.undo_act.isEnabled())
        self.assertFalse(self.win.redo_act.isEnabled())

    def test_undo_redo_track_reorder(self):
        self.win.tracks = [
            {"title": "Track A", "path": "1.mp3", "duration": 100.0},
            {"title": "Track B", "path": "2.mp3", "duration": 200.0},
        ]
        self.win._commit_undo_snapshot()
        self.win._refresh_tracks()

        # Select track 0 and move down
        self.win.track_list.setCurrentRow(0)
        self.win.move_track(1)

        self.assertEqual(self.win.tracks[0]["title"], "Track B")
        self.assertEqual(self.win.tracks[1]["title"], "Track A")

        # Undo move
        self.win.undo()
        self.assertEqual(self.win.tracks[0]["title"], "Track A")
        self.assertEqual(self.win.tracks[1]["title"], "Track B")

        # Redo move
        self.win.redo()
        self.assertEqual(self.win.tracks[0]["title"], "Track B")
        self.assertEqual(self.win.tracks[1]["title"], "Track A")

    def test_undo_redo_track_removal(self):
        self.win.tracks = [{"title": "Only Track", "path": "1.mp3", "duration": 60.0}]
        self.win._commit_undo_snapshot()
        self.win._refresh_tracks()
        self.win.track_list.setCurrentRow(0)

        # Remove track
        self.win.remove_track()
        self.assertEqual(len(self.win.tracks), 0)

        # Undo removal
        self.win.undo()
        self.assertEqual(len(self.win.tracks), 1)
        self.assertEqual(self.win.tracks[0]["title"], "Only Track")

        # Redo removal
        self.win.redo()
        self.assertEqual(len(self.win.tracks), 0)

    def test_undo_redo_color_change(self):
        original_title_color = getattr(self.win, "title_color", (255, 255, 255))
        new_color = (255, 0, 128)

        self.win.set_title_color(new_color)
        self.assertEqual(self.win.title_color, new_color)

        self.win.undo()
        self.assertEqual(self.win.title_color, original_title_color)

        self.win.redo()
        self.assertEqual(self.win.title_color, new_color)

    def test_shortcuts_focus_guard_line_edit(self):
        self.win.show()
        self.win.activateWindow()
        # Put some text in collection_title and focus it
        self.win.collection_title.setText("My Album")
        self.win.collection_title.setFocus()
        self.win.collection_title.setCursorPosition(2)
        _get_app().processEvents()

        self.win.tracks = [{"title": "Important Track", "path": "test.mp3", "duration": 50.0}]
        self.win._refresh_tracks()
        self.win.track_list.setCurrentRow(0)

        # Trigger delete shortcut action
        self.win._on_shortcut_delete_track()
        # Track must NOT be deleted because QLineEdit has focus!
        self.assertEqual(len(self.win.tracks), 1)

        # Key press Space in QLineEdit must NOT toggle intro preview
        old_intro_preview = getattr(self.win, "_previewing_intro", False)
        ev_space = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, " ")
        _get_app().sendEvent(self.win.collection_title, ev_space)
        self.assertEqual(getattr(self.win, "_previewing_intro", False), old_intro_preview)
        self.win.hide()

    def test_track_list_key_shortcuts(self):
        self.win.tracks = [
            {"title": "Track 1", "path": "1.mp3", "duration": 10.0},
            {"title": "Track 2", "path": "2.mp3", "duration": 20.0},
        ]
        self.win._commit_undo_snapshot()
        self.win._refresh_tracks()
        self.win.track_list.setFocus()
        self.win.track_list.setCurrentRow(0)
        _get_app().processEvents()

        # Press Alt+Down on playlist to move track down
        ev_move = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
        _get_app().sendEvent(self.win.track_list, ev_move)
        self.assertEqual(self.win.tracks[0]["title"], "Track 2")
        self.assertEqual(self.win.tracks[1]["title"], "Track 1")

        # Press Delete on playlist to remove selected track (row 1: Track 1)
        ev_del = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
        _get_app().sendEvent(self.win.track_list, ev_del)
        self.assertEqual(len(self.win.tracks), 1)
        self.assertEqual(self.win.tracks[0]["title"], "Track 2")

        # Undo deletion
        self.win.undo()
        self.assertEqual(len(self.win.tracks), 2)

    def test_dirty_state_clears_on_undo_to_saved(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            proj_path = f.name

        try:
            self.win.save_project_as = lambda: None
            self.win._write_project(proj_path)
            self.assertFalse(self.win.has_unsaved_changes())

            # Modify a setting
            self.win.cursor_size_spin.setValue(48)
            self.win._commit_undo_snapshot()
            self.assertTrue(self.win.has_unsaved_changes())

            # Undo modification -> matches saved snapshot -> dirty flag cleared!
            self.win.undo()
            self.assertFalse(self.win.has_unsaved_changes())

            # Redo modification -> dirty flag returns!
            self.win.redo()
            self.assertTrue(self.win.has_unsaved_changes())
        finally:
            Path(proj_path).unlink(missing_ok=True)
