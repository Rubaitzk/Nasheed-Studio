"""
Automated unit tests for MP4 Video Background functionality.

Verifies:
1. is_video_file correctly identifies video vs image formats.
2. get_video_info probes video metadata (duration, width, height, fps, codec).
3. extract_video_frame extracts a valid PIL frame from video at specified timestamp.
4. create_composition generates both composition.png and composition_fg.png when background is video.
5. composition_fg.png contains transparent regions allowing video background to show through.
6. validate_project succeeds for valid video and raises for missing/invalid video.
7. build_render_command configures video background inputs, looping, scaling, foreground overlay, and audio mapping.
8. ProjectService preserves video background attributes across serialization/deserialization.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from src.services.media_probe import is_video_file, get_video_info, extract_video_frame
from src.services.compositor import create_composition
from src.services.render_service import build_render_command, validate_project
from src.services.project_service import (
    save_project_atomic,
    extract_template,
    apply_template_to_project,
    TEMPLATE_DESIGN_KEYS,
)


class TestVideoBackground(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Locate project root and test assets
        cls.project_root = Path(__file__).resolve().parent.parent
        candidates = [
            cls.project_root / "mp4_proof" / "source" / "alma_milky_way_seamless.mp4",
            cls.project_root / "final_deliverable" / "Evidence" / "14612537_1920_1080_30fps.mp4",
        ]
        cls.sample_video = next((p for p in candidates if p.exists()), None)
        assert cls.sample_video is not None and cls.sample_video.exists(), f"Sample video not found in {candidates}"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Create dummy valid audio for render pipeline tests
        self.audio_path = self.tmp / "track.wav"
        # Generate a small 1-second silence wav file using wave module
        import wave
        with wave.open(str(self.audio_path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframes(b"\x00" * (44100 * 4))

        self.base_project = {
            "version": 1,
            "collection_title": "Night Sky Serenity",
            "background": str(self.sample_video),
            "background_type": "video",
            "video_fit_mode": "cover",
            "video_start_time": 0.0,
            "video_loop": True,
            "video_mute_audio": True,
            "logo": "",
            "tracks": [{"title": "Whispers of Peace", "path": str(self.audio_path), "duration": 1.0}],
            "template": "Cinematic",
            "resolution": "1080p · Full HD",
            "indicator_mode": "pill",
            "output_path": str(self.tmp / "output.mp4"),
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_is_video_file_detection(self):
        """is_video_file accurately differentiates video and image formats."""
        self.assertTrue(is_video_file(self.sample_video))

        # Images
        dummy_img = self.tmp / "test.png"
        Image.new("RGB", (100, 100), (20, 20, 20)).save(str(dummy_img))
        self.assertFalse(is_video_file(dummy_img))

        # Audio
        self.assertFalse(is_video_file(self.audio_path))

        # Non-existent files or empty strings
        self.assertFalse(is_video_file(self.tmp / "missing.mp4"))
        self.assertFalse(is_video_file(""))
        self.assertFalse(is_video_file(None))

    def test_get_video_info_probe(self):
        """get_video_info retrieves accurate stream and container metadata."""
        info = get_video_info(self.sample_video)
        self.assertIsNotNone(info)
        self.assertEqual(info["width"], 1920)
        self.assertEqual(info["height"], 1080)
        self.assertGreater(info["duration"], 5.0)
        self.assertIn("h264", info["codec"].lower())
        self.assertTrue(info["has_video"])

        # Non-existent file raises FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            get_video_info(self.tmp / "nonexistent.mp4")

    def test_extract_video_frame(self):
        """extract_video_frame extracts a valid PIL RGB Image at timestamp."""
        img = extract_video_frame(self.sample_video, timestamp=1.5)
        self.assertIsNotNone(img)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (1920, 1080))
        self.assertIn(img.mode, ("RGB", "RGBA"))

    def test_create_composition_with_video_generates_foreground_layer(self):
        """When background is a video, create_composition outputs composition_fg.png and composition.png."""
        work_dir = self.tmp / "comp_work"
        work_dir.mkdir(parents=True, exist_ok=True)

        comp_path, overlay_paths = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.sample_video),
            logo_path=None,
            collection_title="Night Sky Serenity",
            track_titles=["Track 1", "Track 2"],
            template="Cinematic",
            out_dir=str(work_dir),
        )
        self.assertTrue(os.path.exists(comp_path))

        fg_path = work_dir / "composition_fg.png"
        self.assertTrue(fg_path.exists(), "composition_fg.png should be generated for video backgrounds")

        with Image.open(str(fg_path)) as fg_img:
            self.assertEqual(fg_img.mode, "RGBA")
            self.assertEqual(fg_img.size, (1920, 1080))
            alpha_min = fg_img.getextrema()[3][0]

        # With default video_wash_opacity=0.20, minimum alpha is 51 (semi-transparent wash for text readability)
        self.assertLess(alpha_min, 255, "Foreground layer must be semi-transparent, not fully opaque")
        self.assertEqual(alpha_min, int(round(255 * 0.20)))

        # When video_wash_opacity is set to 0.0, minimum alpha is 0 (fully transparent pass-through)
        clean_dir = self.tmp / "clean_comp"
        clean_dir.mkdir(parents=True, exist_ok=True)
        create_composition(
            width=1920,
            height=1080,
            background_path=str(self.sample_video),
            logo_path=None,
            collection_title="Clean",
            track_titles=["Track 1"],
            template="Cinematic",
            out_dir=str(clean_dir),
            video_wash_opacity=0.0,
        )
        with Image.open(str(clean_dir / "composition_fg.png")) as fg_clean:
            self.assertEqual(fg_clean.getextrema()[3][0], 0, "With 0.0 wash opacity, pass-through is 100% transparent")

    def test_validate_project_accepts_valid_video(self):
        """validate_project succeeds when background is a valid video file."""
        validate_project(self.base_project)

    def test_validate_project_raises_on_missing_video(self):
        """validate_project raises ValueError if video file is missing."""
        proj = dict(self.base_project)
        proj["background"] = str(self.tmp / "missing.mp4")
        with self.assertRaises(ValueError):
            validate_project(proj)

    def test_build_render_command_video_flags(self):
        """build_render_command creates proper FFmpeg inputs and filter graph for video background."""
        work_dir = self.tmp / "render_work"
        work_dir.mkdir(parents=True, exist_ok=True)

        cmd, out_path = build_render_command(self.base_project, work_dir)
        cmd_str = " ".join(cmd)

        # Video looping flag before video input
        self.assertIn("-stream_loop -1", cmd_str)
        # Input 0 is background video
        self.assertIn(f"-i {str(self.sample_video)}", cmd_str)
        # Input 1 is composition_fg.png
        fg_path = work_dir / "composition_fg.png"
        self.assertIn(str(fg_path), cmd_str)

        # Video fit filter (cover mode: scale and crop)
        self.assertIn("scale=w=1920:h=1080:force_original_aspect_ratio=increase,crop=1920:1080", cmd_str)
        # Overlay foreground on video
        self.assertIn("overlay=0:0[v_base]", cmd_str)
        # Audio mapping: nasheed track mapped to [aout], video audio excluded
        self.assertIn("-map [aout]", cmd_str)
        self.assertNotIn("-map 0:a", cmd_str, "Input 0 (video background) audio must never be mapped to output")
        self.assertNotIn("[0:a", cmd_str, "Input 0 (video background) audio stream must never be piped into audio concat")

    def test_build_render_command_video_fit_modes(self):
        """Fit modes 'pad' and 'stretch' generate correct filter chains."""
        for mode, expected_filter in [
            ("pad", "scale=w=1920:h=1080:force_original_aspect_ratio=decrease,pad=1920:1080"),
            ("stretch", "scale=w=1920:h=1080"),
        ]:
            proj = dict(self.base_project)
            proj["video_fit_mode"] = mode
            work_dir = self.tmp / f"render_{mode}"
            work_dir.mkdir(parents=True, exist_ok=True)

            cmd, _ = build_render_command(proj, work_dir)
            cmd_str = " ".join(cmd)
            self.assertIn(expected_filter, cmd_str)

    def test_project_service_serialization_roundtrip(self):
        """save_project_atomic preserves video background attributes in project files."""
        proj_file = self.tmp / "project.json"
        save_project_atomic(self.base_project, proj_file)

        loaded = json.loads(proj_file.read_text(encoding="utf-8"))
        self.assertEqual(loaded.get("background"), str(self.sample_video))
        self.assertEqual(loaded.get("background_type"), "video")
        self.assertEqual(loaded.get("video_fit_mode"), "cover")
        self.assertEqual(loaded.get("video_start_time"), 0.0)
        self.assertTrue(loaded.get("video_loop"))
        self.assertTrue(loaded.get("video_mute_audio"))

    def test_extract_template_preserves_video_keys(self):
        """extract_template extracts and preserves video configuration settings."""
        template = extract_template(self.base_project, "Video Theme")
        self.assertEqual(template.get("video_fit_mode"), "cover")
        self.assertEqual(template.get("video_loop"), True)
        self.assertEqual(template.get("video_mute_audio"), True)
        self.assertEqual(template.get("background_type"), "video")


if __name__ == "__main__":
    unittest.main()
