import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.services.compositor import create_composition
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window

_app = None

def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


def _pix_to_bytes(pix):
    if not pix or pix.isNull():
        return b""
    from PySide6.QtCore import QBuffer, QIODevice
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pix.save(buf, "PNG")
    return bytes(buf.data())


class TestWatermarkControls(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Background image (dark gray)
        self.bg_path = self.tmp / "bg.png"
        Image.new("RGB", (640, 360), (30, 35, 40)).save(str(self.bg_path))

        self.tracks = ["01. Sample Track"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_watermark_default_and_explicit_colors(self):
        """Watermark respects default auto-contrast and explicit color settings."""
        # 1. Default (None)
        w_def = self.tmp / "w_def"
        base_def, _ = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(w_def),
            website_text="www.nasheedstudio.com",
            website_color=None,
        )
        self.assertTrue(Path(base_def).is_file())

        # 2. Explicit Cyan Color (#00FFCC)
        w_cyan = self.tmp / "w_cyan"
        base_cyan, _ = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(w_cyan),
            website_text="www.nasheedstudio.com",
            website_color="#00FFCC",
            website_position="Top-Right",
        )
        im_cyan = Image.open(base_cyan)
        crop_cyan = im_cyan.crop((1400, 0, 1920, 200))

        # Check for cyan pixels (high green & blue, low red)
        found_cyan = False
        for x in range(crop_cyan.width):
            for y in range(crop_cyan.height):
                r, g, b = crop_cyan.getpixel((x, y))[:3]
                if r < 50 and g > 200 and b > 180:
                    found_cyan = True
                    break
            if found_cyan:
                break
        self.assertTrue(found_cyan, "Explicit cyan watermark color must be rendered")

        # 3. Invalid color fallback safety
        w_inv = self.tmp / "w_inv"
        base_inv, _ = create_composition(
            width=1920, height=1080,
            background_path=str(self.bg_path),
            logo_path=None,
            collection_title="Nasheed Collection",
            track_titles=self.tracks,
            template="Cinematic",
            out_dir=str(w_inv),
            website_text="www.nasheedstudio.com",
            website_color="invalid_garbage_color",
        )
        self.assertTrue(Path(base_inv).is_file(), "Invalid color string must not crash render")

    def test_watermark_offsets_positive_and_negative(self):
        """Watermark X and Y offsets move the watermark accurately."""
        # Top-Right corner: baseline (0, 0)
        offsets = [(0, 0), (-60, 0), (0, 40), (0, -20)]
        bboxes = []

        for ox, oy in offsets:
            work = self.tmp / f"work_web_{ox}_{oy}"
            base_p, _ = create_composition(
                width=1920, height=1080,
                background_path=str(self.bg_path),
                logo_path=None,
                collection_title="Nasheed Collection",
                track_titles=self.tracks,
                template="Cinematic",
                out_dir=str(work),
                website_text="WATERMARK_TEST",
                website_position="Top-Right",
                website_color="#FF0000", # Pure red for easy isolation
                website_x_offset=ox,
                website_y_offset=oy,
            )
            im = Image.open(base_p)
            crop = im.crop((1200, 0, 1920, 300))
            mask = Image.new("L", crop.size)
            for x in range(crop.width):
                for y in range(crop.height):
                    r, g, b = crop.getpixel((x, y))[:3]
                    if r > 180 and g < 50 and b < 50:
                        mask.putpixel((x, y), 255)
            bb = mask.getbbox()
            self.assertIsNotNone(bb)
            bboxes.append((1200 + bb[0], bb[1]))

        base_x, base_y = bboxes[0]

        # Shift X by -60 (moves left)
        self.assertEqual(bboxes[1][0] - base_x, -60)
        self.assertEqual(bboxes[1][1], base_y)

        # Shift Y by +40 (moves down)
        self.assertEqual(bboxes[2][0], base_x)
        self.assertEqual(bboxes[2][1] - base_y, 40)

        # Shift Y by -20 (moves up)
        self.assertEqual(bboxes[3][0], base_x)
        self.assertEqual(bboxes[3][1] - base_y, -20)


class TestWatermarkUIControls(unittest.TestCase):

    def setUp(self):
        _get_app()
        self.win = MainWindow()
        self.win.resize(1120, 720)
        self.win.show()
        _get_app().processEvents()
        self.win.hide()

    def tearDown(self):
        dispose_window(self.win)

    def test_watermark_ui_controls_exist_and_default_state(self):
        self.assertTrue(hasattr(self.win, "website_color_btn"))
        self.assertTrue(hasattr(self.win, "website_color_reset_btn"))
        self.assertTrue(hasattr(self.win, "website_x_offset_spin"))
        self.assertTrue(hasattr(self.win, "website_y_offset_spin"))

        self.assertIsNone(self.win.website_color)
        self.assertIn("Auto", self.win.website_color_btn.text())
        self.assertEqual(self.win.website_x_offset_spin.value(), 0)
        self.assertEqual(self.win.website_y_offset_spin.value(), 0)

    def test_watermark_color_change_and_reset(self):
        # Set color
        self.win.set_website_color((0, 255, 200))
        self.assertEqual(self.win.website_color, (0, 255, 200))
        self.assertIn("#00FFC8", self.win.website_color_btn.text().upper())

        # Reset color to Auto
        self.win.reset_website_color()
        self.assertIsNone(self.win.website_color)
        self.assertIn("Auto", self.win.website_color_btn.text())

    def test_watermark_persistence_and_undo_redo(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            p = f.name
        try:
            self.win.set_website_color((255, 180, 0))
            self.win.website_x_offset_spin.setValue(-45)
            self.win.website_y_offset_spin.setValue(30)
            self.win._commit_undo_snapshot()

            proj = self.win._project()
            self.assertEqual(proj["website_color"], (255, 180, 0))
            self.assertEqual(proj["website_x_offset"], -45)
            self.assertEqual(proj["website_y_offset"], 30)

            # Test first undo reverts spinbox offsets back to 0
            self.win.undo()
            self.assertEqual(self.win.website_color, (255, 180, 0))
            self.assertEqual(self.win.website_x_offset_spin.value(), 0)
            self.assertEqual(self.win.website_y_offset_spin.value(), 0)

            # Test second undo reverts color back to Auto (None)
            self.win.undo()
            self.assertIsNone(self.win.website_color)
            self.assertEqual(self.win.website_x_offset_spin.value(), 0)
            self.assertEqual(self.win.website_y_offset_spin.value(), 0)

            # Test redo restores color, then offsets
            self.win.redo()
            self.assertEqual(self.win.website_color, (255, 180, 0))
            self.win.redo()
            self.assertEqual(self.win.website_color, (255, 180, 0))
            self.assertEqual(self.win.website_x_offset_spin.value(), -45)
            self.assertEqual(self.win.website_y_offset_spin.value(), 30)

            # Test save & reload
            self.win.save_project_as = lambda: None
            self.win._write_project(p)

            self.win.new_project()
            self.assertIsNone(self.win.website_color)
            self.assertEqual(self.win.website_x_offset_spin.value(), 0)

            self.win._load_project_file(p)
            self.assertEqual(self.win.website_color, (255, 180, 0))
            self.assertEqual(self.win.website_x_offset_spin.value(), -45)
            self.assertEqual(self.win.website_y_offset_spin.value(), 30)
        finally:
            Path(p).unlink(missing_ok=True)

    def test_watermark_case_a_and_case_b_conditions(self):
        """Case A: When main watermark is populated and intro watermark is enabled,
        intro card shows main watermark with intro controls applied.
        Disabling intro watermark hides it on intro card.
        Case B: Intro watermark does NOT leak to main video composition when main watermark is empty."""
        import wave
        from src.services.render_service import build_render_command

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            audio_path = tmp / "audio.wav"
            with wave.open(str(audio_path), "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(b"\x00" * 44100 * 2)

            bg_path = tmp / "bg.png"
            Image.new("RGB", (640, 360), (30, 35, 40)).save(str(bg_path))

            # Baseline blank composition (neither watermark set)
            blank_proj = {
                "version": 1,
                "collection_title": "Test Title",
                "background": str(bg_path),
                "background_type": "image",
                "tracks": [{"title": "Track 1", "path": str(audio_path), "duration": 1.0}],
                "template": "Cinematic",
                "output_path": str(tmp / "out_blank.mp4"),
                "website_text": "",
                "intro_enabled": True,
                "intro_website_show": True,
                "intro_website_text": "",
            }
            blank_dir = tmp / "work_blank"
            build_render_command(blank_proj, blank_dir)

            # Scenario 1 (Case A enabled): Main watermark populated, Intro text blank, intro_website_show=True
            # Must render on main composition AND show main watermark on intro card
            case_a_enabled_proj = dict(blank_proj)
            case_a_enabled_proj["website_text"] = "www.MainWatermark.com"
            case_a_enabled_proj["intro_website_text"] = ""
            case_a_enabled_proj["intro_website_show"] = True
            case_a_dir = tmp / "work_case_a_enabled"
            build_render_command(case_a_enabled_proj, case_a_dir)

            with Image.open(case_a_dir / "composition.png") as im_wm, Image.open(blank_dir / "composition.png") as im_blank:
                self.assertNotEqual(im_wm.tobytes(), im_blank.tobytes(), "Main watermark must render on main composition")

            with Image.open(case_a_dir / "intro_overlay.png") as im_intro:
                bbox = im_intro.crop((0, 700, 1920, 1080)).getbbox()
                self.assertIsNotNone(bbox, "Intro overlay must show main watermark when intro watermark is enabled and blank")

            # Scenario 1b (Case A disabled): Main watermark populated, Intro text blank, intro_website_show=False
            # Must render on main composition, but NOT on intro card
            case_a_disabled_proj = dict(case_a_enabled_proj)
            case_a_disabled_proj["intro_website_show"] = False
            case_a_dis_dir = tmp / "work_case_a_disabled"
            build_render_command(case_a_disabled_proj, case_a_dis_dir)

            with Image.open(case_a_dis_dir / "intro_overlay.png") as im_intro_dis:
                bbox_dis = im_intro_dis.crop((0, 700, 1920, 1080)).getbbox()
                self.assertIsNone(bbox_dis, "Disabling intro watermark must prevent watermark from showing on intro card")

            # Scenario 1c (Case A intro controls applied): Intro watermark Y-offset moves the watermark on intro card
            case_a_shifted_proj = dict(case_a_enabled_proj)
            case_a_shifted_proj["intro_website_y_offset"] = -50
            case_a_shifted_dir = tmp / "work_case_a_shifted"
            build_render_command(case_a_shifted_proj, case_a_shifted_dir)

            with Image.open(case_a_dir / "intro_overlay.png") as im_orig, Image.open(case_a_shifted_dir / "intro_overlay.png") as im_shift:
                self.assertNotEqual(im_orig.tobytes(), im_shift.tobytes(), "Intro watermark controls (e.g. Y-offset) must apply to intro card")

            # Scenario 2 (Case B): Intro watermark populated, Main watermark empty
            # Must render on intro card, but NOT on main composition (no reverse leaking)
            intro_only_proj = dict(blank_proj)
            intro_only_proj["website_text"] = ""
            intro_only_proj["intro_website_text"] = "www.IntroOnlyWatermark.com"
            intro_dir = tmp / "work_intro_only"
            build_render_command(intro_only_proj, intro_dir)

            with Image.open(intro_dir / "composition.png") as im_wm, Image.open(blank_dir / "composition.png") as im_blank:
                self.assertEqual(im_wm.tobytes(), im_blank.tobytes(), "Intro watermark must NOT leak onto main video composition")

            with Image.open(intro_dir / "intro_overlay.png") as im_intro:
                bbox = im_intro.crop((0, 700, 1920, 1080)).getbbox()
                self.assertIsNotNone(bbox, "Intro watermark must render on intro card")

    def test_interactive_case_a_and_intro_controls_in_mainwindow(self):
        """Case A in MainWindow UI: Main watermark propagates to intro card when intro watermark is enabled,
        intro controls (size, opacity, color, Y-offset) apply as intended, and Case B main video does not leak."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            bg_path = f.name
        try:
            Image.new("RGB", (640, 360), (35, 40, 45)).save(bg_path)
            self.win.background_path = bg_path
            self.win.tracks = [{"title": "Test Track", "duration": 30.0}]

            # Baseline blank intro card
            self.win.website_edit.setText("")
            self.win.intro_website_edit.setText("")
            self.win.intro_website_show_check.setChecked(False)
            _get_app().processEvents()
            blank_intro = self.win._render_intro_card_pixmap(bg_path)
            self.assertIsNotNone(blank_intro)
            blank_bytes = _pix_to_bytes(blank_intro)

            # Case A: Main watermark populated, Intro text blank, Intro show = True
            self.win.website_edit.setText("www.NasheedStudioMain.com")
            self.win.intro_website_edit.setText("")
            self.win.intro_website_show_check.setChecked(True)
            _get_app().processEvents()
            intro_enabled_pix = self.win._render_intro_card_pixmap(bg_path)
            self.assertIsNotNone(intro_enabled_pix)
            enabled_bytes = _pix_to_bytes(intro_enabled_pix)
            self.assertNotEqual(enabled_bytes, blank_bytes, "Intro card MUST show main watermark when intro watermark is enabled")

            # Case A with Intro show = False
            self.win.intro_website_show_check.setChecked(False)
            _get_app().processEvents()
            intro_disabled_pix = self.win._render_intro_card_pixmap(bg_path)
            self.assertIsNotNone(intro_disabled_pix)
            disabled_bytes = _pix_to_bytes(intro_disabled_pix)
            self.assertEqual(disabled_bytes, blank_bytes, "Intro card MUST NOT show watermark when intro watermark is disabled")

            # Verify intro controls apply
            self.win.intro_website_show_check.setChecked(True)
            _get_app().processEvents()
            base_bytes = _pix_to_bytes(self.win._render_intro_card_pixmap(bg_path))

            # Size
            self.win.intro_website_size_spin.setValue(40)
            _get_app().processEvents()
            self.assertNotEqual(_pix_to_bytes(self.win._render_intro_card_pixmap(bg_path)), base_bytes, "Intro size spinbox must affect intro watermark")
            self.win.intro_website_size_spin.setValue(20)

            # Opacity
            self.win.intro_website_opacity_slider.setValue(20)
            _get_app().processEvents()
            self.assertNotEqual(_pix_to_bytes(self.win._render_intro_card_pixmap(bg_path)), base_bytes, "Intro opacity slider must affect intro watermark")
            self.win.intro_website_opacity_slider.setValue(90)

            # Y-offset
            self.win.intro_website_y_offset_spin.setValue(-80)
            _get_app().processEvents()
            self.assertNotEqual(_pix_to_bytes(self.win._render_intro_card_pixmap(bg_path)), base_bytes, "Intro Y-offset spinbox must affect intro watermark")
            self.win.intro_website_y_offset_spin.setValue(0)

            # Custom text override
            self.win.intro_website_edit.setText("www.CustomOverride.com")
            _get_app().processEvents()
            self.assertNotEqual(_pix_to_bytes(self.win._render_intro_card_pixmap(bg_path)), base_bytes, "Custom intro text must override main watermark")
            self.win.intro_website_edit.setText("")

            # Case B: Main blank, Intro populated -> Main video preview MUST NOT leak intro watermark
            self.win.website_edit.setText("")
            self.win.intro_website_edit.setText("www.IntroCustomOnly.com")
            self.win.website_show_check.setChecked(True)
            self.win.intro_website_show_check.setChecked(True)
            self.win._refresh_preview()
            _get_app().processEvents()
            main_pix = self.win.preview_image.pixmap()

            self.win.intro_website_edit.setText("")
            self.win._refresh_preview()
            _get_app().processEvents()
            blank_main_pix = self.win.preview_image.pixmap()
            self.assertEqual(_pix_to_bytes(main_pix), _pix_to_bytes(blank_main_pix), "Main video MUST NOT leak intro watermark when main watermark is empty")
        finally:
            Path(bg_path).unlink(missing_ok=True)

    def test_playlist_cols_spin_visibility_and_layout(self):
        """Playlist columns spinbox displays number cleanly without button overlap."""
        self.win.show()
        _get_app().processEvents()

        spin = self.win.playlist_cols_spin
        self.assertGreaterEqual(spin.width(), 60, "Columns spinbox width must be at least 60px")
        line_edit = spin.lineEdit()
        self.assertIsNotNone(line_edit)
        self.assertGreaterEqual(line_edit.width(), 35, "Columns spinbox text area must be wide enough to clearly show digits")

        # Verify editing and value changing works
        spin.setValue(2)
        self.assertEqual(spin.value(), 2)
        self.assertEqual(line_edit.text(), "2")
        spin.setValue(1)
        self.assertEqual(spin.value(), 1)
        self.assertEqual(line_edit.text(), "1")

    def test_inspector_panel_no_horizontal_clipping(self):
        """Inspector panel tabs have no horizontally clipped widgets at startup or minimum size."""
        self.win.show()
        _get_app().processEvents()

        # Test at startup size
        for i in range(self.win.inspector_tabs.count()):
            self.win.inspector_tabs.setCurrentIndex(i)
            _get_app().processEvents()
            scroll = self.win.inspector_tabs.widget(i)
            viewport = scroll.viewport()
            content = scroll.widget()

            for child in content.findChildren(object):
                if hasattr(child, "geometry") and hasattr(child, "isVisible") and child.isVisible():
                    pos = child.mapTo(content, child.rect().topLeft())
                    right = pos.x() + child.width()
                    self.assertLessEqual(
                        right, viewport.width() + 1,
                        f"Widget {child.metaObject().className()} in Tab {i} overflows viewport width ({right} > {viewport.width()})"
                    )

        # Test at minimum window size (1120x720)
        self.win.resize(1120, 720)
        self.win.splitter.setSizes([260, 480, 356])
        _get_app().processEvents()

        for i in range(self.win.inspector_tabs.count()):
            self.win.inspector_tabs.setCurrentIndex(i)
            _get_app().processEvents()
            scroll = self.win.inspector_tabs.widget(i)
            viewport = scroll.viewport()
            content = scroll.widget()

            for child in content.findChildren(object):
                if hasattr(child, "geometry") and hasattr(child, "isVisible") and child.isVisible():
                    pos = child.mapTo(content, child.rect().topLeft())
                    right = pos.x() + child.width()
                    self.assertLessEqual(
                        right, viewport.width() + 1,
                        f"At 720p, widget {child.metaObject().className()} in Tab {i} overflows viewport width ({right} > {viewport.width()})"
                    )


if __name__ == "__main__":
    unittest.main()
