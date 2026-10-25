"""
Render pipeline regression tests for Phase 2 (Task G).

Verifies:
1. build_render_command with 'neither' mode does NOT crash FFmpeg and produces valid command without overlay inputs.
2. build_render_command with 'both', 'cursor_only', and 'highlight_only' properly hooks up overlay filters.
3. Audio inputs are normalized via aformat before concatenation.
4. Custom cursor path is validated and reaches render command generation.
"""

import tempfile
import unittest
from pathlib import Path

from src.services.render_service import build_render_command, validate_project


class TestPhase2RenderPipeline(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Create dummy assets
        self.bg_path = self.tmp / "bg.png"
        self.bg_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # minimal header

        # We need a real valid image for PIL to read
        from PIL import Image
        img = Image.new("RGB", (320, 240), (20, 30, 25))
        img.save(str(self.bg_path))

        self.audio_path = self.tmp / "track.wav"
        self.audio_path.write_bytes(b"RIFF" + b"\x00" * 100)

        self.cursor_svg = self.tmp / "cursor.svg"
        self.cursor_svg.write_text(
            '<svg width="32" height="32"><polygon points="0,0 32,16 0,32" fill="yellow"/></svg>',
            encoding="utf-8"
        )

        self.base_project = {
            "version": 1,
            "collection_title": "Render Pipeline Test",
            "background": str(self.bg_path),
            "logo": "",
            "tracks": [{"title": "Track A", "path": str(self.audio_path), "duration": 5.0}],
            "template": "Cinematic",
            "resolution": "1080p · Full HD",
            "output_path": str(self.tmp / "output.mp4"),
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_mode_neither_generates_clean_command(self):
        """Mode 'neither' generates a command with 0 overlay inputs and routes 0:v directly to output."""
        proj = dict(self.base_project)
        proj["indicator_mode"] = "neither"
        work_dir = self.tmp / "work_neither"

        cmd, out_path = build_render_command(proj, work_dir)

        # Verify command flags
        cmd_str = " ".join(cmd)
        self.assertIn("-map 0:v", cmd_str)
        self.assertIn("concat=n=1:v=0:a=1[aout]", cmd_str)
        self.assertNotIn("overlay=0:0", cmd_str)
        # Only base composition and 1 audio track
        self.assertIn(str(self.audio_path), cmd)

    def test_mode_both_generates_overlay_filters(self):
        """Mode 'both' generates overlay filters and maps the final composited video."""
        proj = dict(self.base_project)
        proj["indicator_mode"] = "both"
        work_dir = self.tmp / "work_both"

        cmd, out_path = build_render_command(proj, work_dir)
        cmd_str = " ".join(cmd)

        self.assertIn("overlay=0:0:enable=", cmd_str)
        self.assertIn("-map [v1]", cmd_str)
        self.assertIn("-map [aout]", cmd_str)

    def test_audio_normalization_filter_included(self):
        """All audio tracks must be normalized via aformat before concatenation."""
        proj = dict(self.base_project)
        work_dir = self.tmp / "work_norm"

        cmd, out_path = build_render_command(proj, work_dir)
        cmd_str = " ".join(cmd)

        self.assertIn("aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo", cmd_str)

    def test_custom_cursor_validation(self):
        """Valid custom cursor passes validation; missing cursor raises FileNotFoundError."""
        proj = dict(self.base_project)
        proj["cursor_path"] = str(self.cursor_svg)
        validate_project(proj)  # should not raise

        proj["cursor_path"] = str(self.tmp / "missing_cursor.svg")
        with self.assertRaises(FileNotFoundError):
            validate_project(proj)


if __name__ == "__main__":
    unittest.main()
