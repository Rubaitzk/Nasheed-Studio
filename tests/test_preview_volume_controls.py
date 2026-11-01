import sys
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from src.ui.main_window import MainWindow
from tests.conftest import dispose_window

_app = None

def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestPreviewVolumeControls(unittest.TestCase):
    def setUp(self):
        _get_app()
        self.win = MainWindow()

    def tearDown(self):
        dispose_window(self.win)

    def test_preview_volume_defaults(self):
        win = self.win
        self.assertTrue(hasattr(win, "preview_volume_slider"))
        self.assertTrue(hasattr(win, "preview_volume_btn"))
        self.assertTrue(hasattr(win, "preview_volume_label"))

        self.assertEqual(win.preview_volume_slider.value(), 70)
        self.assertEqual(win.preview_volume_label.text(), "70%")
        self.assertAlmostEqual(win._get_effective_preview_volume(), 0.7, places=2)
        self.assertFalse(win._preview_is_muted)

    def test_preview_volume_adjustment(self):
        win = self.win
        win._preview_audio_player = QMediaPlayer(win)
        win._preview_audio_output = QAudioOutput(win)
        win._preview_audio_player.setAudioOutput(win._preview_audio_output)

        # Change to 40%
        win.preview_volume_slider.setValue(40)
        self.assertEqual(win.preview_volume_label.text(), "40%")
        self.assertAlmostEqual(win._get_effective_preview_volume(), 0.4, places=2)
        self.assertAlmostEqual(win._preview_audio_output.volume(), 0.4, places=2)

        # Change to 100%
        win.preview_volume_slider.setValue(100)
        self.assertEqual(win.preview_volume_label.text(), "100%")
        self.assertAlmostEqual(win._get_effective_preview_volume(), 1.0, places=2)
        self.assertAlmostEqual(win._preview_audio_output.volume(), 1.0, places=2)

    def test_preview_volume_mute_unmute(self):
        win = self.win
        win._preview_audio_player = QMediaPlayer(win)
        win._preview_audio_output = QAudioOutput(win)
        win._preview_audio_player.setAudioOutput(win._preview_audio_output)

        win.preview_volume_slider.setValue(80)
        self.assertAlmostEqual(win._get_effective_preview_volume(), 0.8, places=2)

        # Click mute
        win.preview_volume_btn.click()
        self.assertTrue(win._preview_is_muted)
        self.assertEqual(win.preview_volume_slider.value(), 0)
        self.assertEqual(win.preview_volume_label.text(), "0%")
        self.assertEqual(win._get_effective_preview_volume(), 0.0)
        self.assertEqual(win._preview_audio_output.volume(), 0.0)

        # Click unmute
        win.preview_volume_btn.click()
        self.assertFalse(win._preview_is_muted)
        self.assertEqual(win.preview_volume_slider.value(), 80)
        self.assertEqual(win.preview_volume_label.text(), "80%")
        self.assertAlmostEqual(win._get_effective_preview_volume(), 0.8, places=2)
        self.assertAlmostEqual(win._preview_audio_output.volume(), 0.8, places=2)

    def test_preview_volume_does_not_affect_export_settings(self):
        win = self.win
        proj = win._project()
        self.assertNotIn("preview_volume", proj)
        self.assertNotIn("preview_audio_volume", proj)
