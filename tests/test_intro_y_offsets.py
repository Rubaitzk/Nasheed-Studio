import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.services.compositor import create_intro_card
from tests.conftest import dispose_window

_app = None

def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestIntroYOffsets(unittest.TestCase):
    def setUp(self):
        self.app = _get_app()
        self.win = MainWindow()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Create dummy bg and logo
        self.bg_path = self.tmp / "bg.png"
        Image.new("RGB", (640, 360), (30, 35, 40)).save(str(self.bg_path))

        self.logo_path = self.tmp / "logo.png"
        Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(str(self.logo_path))

    def tearDown(self):
        dispose_window(self.win)
        self.temp_dir.cleanup()

    def test_intro_y_offset_ui_controls(self):
        win = self.win
        self.assertTrue(hasattr(win, "intro_logo_y_offset_spin"))
        self.assertTrue(hasattr(win, "intro_title_y_offset_spin"))
        self.assertTrue(hasattr(win, "intro_website_y_offset_spin"))

        self.assertEqual(win.intro_logo_y_offset_spin.value(), 0)
        self.assertEqual(win.intro_title_y_offset_spin.value(), 0)
        self.assertEqual(win.intro_website_y_offset_spin.value(), 0)

        self.assertEqual(win.intro_logo_y_offset_spin.minimum(), -500)
        self.assertEqual(win.intro_logo_y_offset_spin.maximum(), 500)

    def test_intro_y_offset_project_serialization(self):
        win = self.win
        win.intro_logo_y_offset_spin.setValue(45)
        win.intro_title_y_offset_spin.setValue(-30)
        win.intro_website_y_offset_spin.setValue(25)

        proj = win._project()
        self.assertEqual(proj.get("intro_logo_y_offset"), 45)
        self.assertEqual(proj.get("intro_title_y_offset"), -30)
        self.assertEqual(proj.get("intro_website_y_offset"), 25)

        # Reset and restore
        win.intro_logo_y_offset_spin.setValue(0)
        win.intro_title_y_offset_spin.setValue(0)
        win.intro_website_y_offset_spin.setValue(0)

        win._restore_project_state(proj)
        self.assertEqual(win.intro_logo_y_offset_spin.value(), 45)
        self.assertEqual(win.intro_title_y_offset_spin.value(), -30)
        self.assertEqual(win.intro_website_y_offset_spin.value(), 25)

    def test_intro_y_offset_rendering_difference(self):
        """create_intro_card produces visibly shifted elements with Y-offsets."""
        out_base = self.tmp / "base"
        out_base.mkdir()
        base_path = create_intro_card(
            width=640, height=360,
            background_path=str(self.bg_path),
            logo_path=str(self.logo_path),
            collection_title="Nasheed Collection",
            template="Cinematic",
            out_dir=str(out_base),
            website_text="www.nasheed.com",
            logo_y_offset=0,
            title_y_offset=0,
            website_y_offset=0,
        )

        out_shifted = self.tmp / "shifted"
        out_shifted.mkdir()
        shifted_path = create_intro_card(
            width=640, height=360,
            background_path=str(self.bg_path),
            logo_path=str(self.logo_path),
            collection_title="Nasheed Collection",
            template="Cinematic",
            out_dir=str(out_shifted),
            website_text="www.nasheed.com",
            logo_y_offset=40,
            title_y_offset=-30,
            website_y_offset=20,
        )

        img_base = Image.open(base_path)
        img_shifted = Image.open(shifted_path)

        # Images must differ due to shifted elements
        self.assertNotEqual(list(img_base.getdata()), list(img_shifted.getdata()))
