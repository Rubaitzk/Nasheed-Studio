import sys
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ui.main_window import MainWindow
from tests.conftest import dispose_window


class TestButtonIconsAndTooltips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.win = MainWindow()

    def tearDown(self):
        dispose_window(self.win)

    def test_buttons_have_no_broken_text_and_valid_icons(self):
        # Visible text should be empty to prevent text truncation/clipping in narrow layouts
        self.assertEqual(self.win.add_tracks_btn.text(), "")
        self.assertEqual(self.win.rename_track_btn.text(), "")
        self.assertEqual(self.win.remove_track_btn.text(), "")
        self.assertEqual(self.win.up_btn.text(), "")
        self.assertEqual(self.win.down_btn.text(), "")

        # Icons must be present and valid
        self.assertFalse(self.win.add_tracks_btn.icon().isNull())
        self.assertFalse(self.win.rename_track_btn.icon().isNull())
        self.assertFalse(self.win.remove_track_btn.icon().isNull())
        self.assertFalse(self.win.up_btn.icon().isNull())
        self.assertFalse(self.win.down_btn.icon().isNull())

        # Icon size should be uniform
        self.assertEqual(self.win.add_tracks_btn.iconSize(), QSize(16, 16))
        self.assertEqual(self.win.rename_track_btn.iconSize(), QSize(16, 16))
        self.assertEqual(self.win.remove_track_btn.iconSize(), QSize(16, 16))
        self.assertEqual(self.win.up_btn.iconSize(), QSize(16, 16))
        self.assertEqual(self.win.down_btn.iconSize(), QSize(16, 16))

    def test_buttons_have_explanatory_tooltips(self):
        self.assertIn("Add Audio", self.win.add_tracks_btn.toolTip())
        self.assertIn("Edit Title", self.win.rename_track_btn.toolTip())
        self.assertIn("Remove", self.win.remove_track_btn.toolTip())
        self.assertIn("Move", self.win.up_btn.toolTip())
        self.assertIn("Move", self.win.down_btn.toolTip())

    def test_buttons_have_accessible_names(self):
        self.assertEqual(self.win.add_tracks_btn.accessibleName(), "Add Audio")
        self.assertEqual(self.win.rename_track_btn.accessibleName(), "Edit Title")
        self.assertEqual(self.win.remove_track_btn.accessibleName(), "Remove")
        self.assertEqual(self.win.up_btn.accessibleName(), "Move Up")
        self.assertEqual(self.win.down_btn.accessibleName(), "Move Down")

    def test_actions_triggered_by_buttons(self):
        # Setup sample tracks
        self.win.tracks = [
            {"title": "Track 1", "path": "t1.mp3", "duration": 100.0},
            {"title": "Track 2", "path": "t2.mp3", "duration": 120.0},
            {"title": "Track 3", "path": "t3.mp3", "duration": 140.0},
        ]
        self.win._refresh_tracks()
        self.win.track_list.setCurrentRow(1) # Select Track 2

        # Test move up button
        self.win.up_btn.click()
        self.assertEqual(self.win.tracks[0]["title"], "Track 2")
        self.assertEqual(self.win.tracks[1]["title"], "Track 1")

        # Test move down button
        self.win.down_btn.click()
        self.assertEqual(self.win.tracks[0]["title"], "Track 1")
        self.assertEqual(self.win.tracks[1]["title"], "Track 2")

        # Test remove track button
        self.win.remove_track_btn.click()
        self.assertEqual(len(self.win.tracks), 2)
        self.assertEqual(self.win.tracks[0]["title"], "Track 1")
        self.assertEqual(self.win.tracks[1]["title"], "Track 3")

        # Test add tracks button trigger
        called = [False]
        self.win.add_tracks = lambda: called.__setitem__(0, True)
        self.win.add_tracks_btn.click()
        self.assertTrue(called[0])

        # Test edit title button trigger
        rename_called = [False]
        self.win._on_rename_track_clicked = lambda: rename_called.__setitem__(0, True)
        self.win.rename_track_btn.click()
        self.assertTrue(rename_called[0])


if __name__ == "__main__":
    unittest.main()
