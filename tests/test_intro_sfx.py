import unittest
import sys
from pathlib import Path
import tempfile
import wave
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.services.timeline import build_timeline
from src.services.compositor import create_intro_card
from src.services.render_service import build_render_command, validate_project
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


def _create_synthetic_wav(path: Path, duration_sec: float = 2.0, sample_rate: int = 44100):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        num_frames = int(duration_sec * sample_rate)
        # 16-bit silence
        data = b"\x00\x00\x00\x00" * num_frames
        wf.writeframes(data)


class TestIntroAndSFX(unittest.TestCase):
    def setUp(self):
        _get_app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Create dummy background image
        self.bg_path = self.tmp / "bg.png"
        Image.new("RGB", (1920, 1080), color=(15, 25, 20)).save(self.bg_path)

        # Create dummy logo
        self.logo_path = self.tmp / "logo.png"
        Image.new("RGBA", (150, 150), color=(255, 255, 255, 200)).save(self.logo_path)

        # Create dummy audio tracks
        self.audio1 = self.tmp / "track1.wav"
        self.audio2 = self.tmp / "track2.wav"
        self.audio3 = self.tmp / "track3.wav"
        _create_synthetic_wav(self.audio1, duration_sec=4.0)
        _create_synthetic_wav(self.audio2, duration_sec=6.0)
        _create_synthetic_wav(self.audio3, duration_sec=5.0)

        # Create dummy transition SFX
        self.sfx_wav = self.tmp / "sfx_woosh.wav"
        _create_synthetic_wav(self.sfx_wav, duration_sec=1.0)

        self.tracks = [
            {"path": str(self.audio1), "duration": 4.0, "title": "Track 1"},
            {"path": str(self.audio2), "duration": 6.0, "title": "Track 2"},
            {"path": str(self.audio3), "duration": 5.0, "title": "Track 3"},
        ]

        self.base_project = {
            "version": 1,
            "collection_title": "Nasheed Intro Test",
            "background": str(self.bg_path),
            "logo": str(self.logo_path),
            "tracks": self.tracks,
            "template": "Cinematic",
            "resolution": "1080p · Full HD",
            "indicator_mode": "both",
            "cursor_path": "",
            "cursor_size": 32,
            "output_path": str(self.tmp / "output.mp4"),
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # Timeline with Intro Duration
    # ------------------------------------------------------------------
    def test_timeline_shifted_by_intro_duration(self):
        """Timeline start and end times must be shifted forward by intro_duration."""
        intro_dur = 3.5
        timeline = build_timeline(self.tracks, intro_duration=intro_dur)

        self.assertEqual(len(timeline), 3)
        self.assertAlmostEqual(timeline[0].start, 3.5)
        self.assertAlmostEqual(timeline[0].end, 7.5)

        self.assertAlmostEqual(timeline[1].start, 7.5)
        self.assertAlmostEqual(timeline[1].end, 13.5)

        self.assertAlmostEqual(timeline[2].start, 13.5)
        self.assertAlmostEqual(timeline[2].end, 18.5)

        # Verify contiguous intervals
        for i in range(len(timeline) - 1):
            self.assertAlmostEqual(timeline[i].end, timeline[i + 1].start)

    # ------------------------------------------------------------------
    # Intro Card Generation
    # ------------------------------------------------------------------
    def test_create_intro_card_output(self):
        """create_intro_card produces a valid image file with specified dimensions."""
        card_path = create_intro_card(
            width=1920,
            height=1080,
            background_path=str(self.bg_path),
            logo_path=str(self.logo_path),
            collection_title="Golden Islamic Nasheeds",
            template="Cinematic",
            out_dir=str(self.tmp / "intro_out"),
            title_font_family="Arial",
            title_font_style="Bold",
            title_font_size=52,
            website_text="www.golden-nasheeds.com",
        )
        self.assertTrue(Path(card_path).exists())
        with Image.open(card_path) as img:
            self.assertEqual(img.size, (1920, 1080))

    # ------------------------------------------------------------------
    # Intro Render Command & Animations
    # ------------------------------------------------------------------
    def test_intro_render_command_animations(self):
        """Intro animations (Fade, Zoom, Slide) construct valid filtergraph expressions."""
        animations = ["Fade in / out", "Zoom in", "Slide"]
        for anim in animations:
            proj = dict(self.base_project)
            proj["intro_enabled"] = True
            proj["intro_duration"] = 3.0
            proj["intro_animation"] = anim
            work_dir = self.tmp / f"work_intro_{anim.replace(' ', '_')}"

            cmd, out_path = build_render_command(proj, work_dir)
            cmd_str = " ".join(cmd)

            # Silence prepended for audio alignment
            self.assertIn("anullsrc=channel_layout=stereo:sample_rate=44100", cmd_str)
            self.assertIn("atrim=duration=3.000[a_intro_silence]", cmd_str)
            self.assertIn("[a_intro_silence][a_norm_0][a_norm_1][a_norm_2]concat=n=4:v=0:a=1[aout]", cmd_str)

            # Intro overlay with proper timing
            self.assertIn("between(t\\,0\\,3.000)", cmd_str)

            # Specific animation filter checks
            if anim == "Fade in / out":
                self.assertIn("fade=t=in:st=0", cmd_str)
                self.assertIn("fade=t=out:st=2.500", cmd_str)
            elif anim == "Zoom in":
                self.assertIn("scale=w='iw*(1+0.06*t/3.000)'", cmd_str)
            elif anim == "Slide":
                self.assertIn("if(gte(t\\,2.500)", cmd_str)

    # ------------------------------------------------------------------
    # Transition SFX Mixing & Audio Synchronization
    # ------------------------------------------------------------------
    def test_sfx_adelay_and_amix_construction(self):
        """Transition SFX is split, delayed to track transitions, and mixed via amix."""
        proj = dict(self.base_project)
        proj["transition_sfx_enabled"] = True
        proj["transition_sfx_path"] = str(self.sfx_wav)
        proj["transition_sfx_volume"] = 0.65
        work_dir = self.tmp / "work_sfx"

        cmd, out_path = build_render_command(proj, work_dir)
        cmd_str = " ".join(cmd)

        # 3 tracks have 2 transitions: at track 2 start (4.0s = 4000ms) and track 3 start (10.0s = 10000ms)
        self.assertIn("volume=0.65[sfx_prep]", cmd_str)
        self.assertIn("[sfx_prep]asplit=2[sfx_0][sfx_1]", cmd_str)
        self.assertIn("[sfx_0]adelay=4000|4000[sfx_del_0]", cmd_str)
        self.assertIn("[sfx_1]adelay=10000|10000[sfx_del_1]", cmd_str)
        self.assertIn("[base_audio][sfx_del_0][sfx_del_1]amix=inputs=3:duration=first:dropout_transition=0:normalize=0[aout]", cmd_str)

    def test_intro_combined_with_sfx(self):
        """When both intro and SFX are enabled, SFX delays include intro offset."""
        proj = dict(self.base_project)
        proj["intro_enabled"] = True
        proj["intro_duration"] = 2.0
        proj["transition_sfx_enabled"] = True
        proj["transition_sfx_path"] = str(self.sfx_wav)
        proj["transition_sfx_volume"] = 0.50
        work_dir = self.tmp / "work_intro_sfx"

        cmd, out_path = build_render_command(proj, work_dir)
        cmd_str = " ".join(cmd)

        # Intro is 2.0s, track 1 is 4.0s (ends at 6.0s), track 2 is 6.0s (ends at 12.0s)
        # Transition 1 is at 6.0s = 6000ms; Transition 2 is at 12.0s = 12000ms
        self.assertIn("[sfx_0]adelay=6000|6000[sfx_del_0]", cmd_str)
        self.assertIn("[sfx_1]adelay=12000|12000[sfx_del_1]", cmd_str)
        self.assertIn("-map [aout]", cmd_str)

    # ------------------------------------------------------------------
    # Project Validation
    # ------------------------------------------------------------------
    def test_validate_project_intro_sfx_boundaries(self):
        """validate_project catches invalid intro durations, animations, SFX files, and volumes."""
        proj = dict(self.base_project)

        # Invalid intro duration (< 1.0)
        proj["intro_enabled"] = True
        proj["intro_duration"] = 0.5
        with self.assertRaises(ValueError):
            validate_project(proj)

        # Invalid intro duration (> 10.0)
        proj["intro_duration"] = 15.0
        with self.assertRaises(ValueError):
            validate_project(proj)

        # Invalid intro animation
        proj["intro_duration"] = 3.0
        proj["intro_animation"] = "Explosion"
        with self.assertRaises(ValueError):
            validate_project(proj)
        proj["intro_animation"] = "Fade in / out"

        # Missing SFX file
        proj["transition_sfx_enabled"] = True
        proj["transition_sfx_path"] = str(self.tmp / "non_existent_sfx.wav")
        with self.assertRaises(FileNotFoundError):
            validate_project(proj)

        # Invalid SFX volume (> 1.0)
        proj["transition_sfx_path"] = str(self.sfx_wav)
        proj["transition_sfx_volume"] = 1.5
        with self.assertRaises(ValueError):
            validate_project(proj)

        # Valid project passes
        proj["transition_sfx_volume"] = 0.8
        validate_project(proj)

    # ------------------------------------------------------------------
    # UI Save & Load Roundtrip for Intro & SFX
    # ------------------------------------------------------------------
    def test_intro_and_sfx_save_load_roundtrip(self):
        """UI correctly serializes and restores intro and SFX controls."""
        win = MainWindow()
        try:
            win.intro_check.setChecked(True)
            win.intro_dur_spin.setValue(4.5)
            win.intro_anim_combo.setCurrentText("Zoom in")

            win.sfx_check.setChecked(True)
            win.sfx_path = str(self.sfx_wav)
            win.sfx_vol_slider.setValue(85)

            proj = win._project()
            self.assertTrue(proj["intro_enabled"])
            self.assertAlmostEqual(proj["intro_duration"], 4.5)
            self.assertEqual(proj["intro_animation"], "Zoom in")
            self.assertTrue(proj["transition_sfx_enabled"])
            self.assertEqual(proj["transition_sfx_path"], str(self.sfx_wav))
            self.assertAlmostEqual(proj["transition_sfx_volume"], 0.85)

            proj_file = self.tmp / "intro_sfx_proj.json"
            win._write_project(str(proj_file))

            win2 = MainWindow()
            try:
                win2._load_project_file(str(proj_file))
                self.assertTrue(win2.intro_check.isChecked())
                self.assertAlmostEqual(win2.intro_dur_spin.value(), 4.5)
                self.assertEqual(win2.intro_anim_combo.currentText(), "Zoom in")
                self.assertTrue(win2.sfx_check.isChecked())
                self.assertEqual(win2.sfx_path, str(self.sfx_wav))
                self.assertEqual(win2.sfx_vol_slider.value(), 85)
            finally:
                dispose_window(win2)
        finally:
            dispose_window(win)
