"""Tests for process lifecycle management, subprocess tracking, and export bitrate quality modes."""

import os
import subprocess
import sys
import unittest
from pathlib import Path
import tempfile

from src.services.process_manager import (
    register_process,
    unregister_process,
    get_active_process_count,
    terminate_process_tree,
    cleanup_all_processes,
    run_tracked_subprocess,
    CREATE_NO_WINDOW,
)
from src.services.render_service import build_render_command


class TestProcessLifecycle(unittest.TestCase):
    """Test process tracking, graceful termination, and cleanup."""

    def test_register_and_unregister(self):
        # Start a dummy sleep process
        cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
        flags = CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(cmd, creationflags=flags)
        try:
            register_process(proc)
            self.assertGreaterEqual(get_active_process_count(), 1)
        finally:
            terminate_process_tree(proc, timeout=1.0)
            unregister_process(proc)

        self.assertIsNotNone(proc.poll())

    def test_cleanup_all_processes(self):
        cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
        flags = CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc1 = subprocess.Popen(cmd, creationflags=flags)
        proc2 = subprocess.Popen(cmd, creationflags=flags)

        register_process(proc1)
        register_process(proc2)

        cleanup_all_processes(timeout_per_process=1.0)

        self.assertIsNotNone(proc1.poll())
        self.assertIsNotNone(proc2.poll())
        self.assertEqual(get_active_process_count(), 0)

    def test_run_tracked_subprocess(self):
        cmd = [sys.executable, "-c", "print('hello_tracked')"]
        res = run_tracked_subprocess(cmd, capture_output=True, text=True, check=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("hello_tracked", res.stdout)
        self.assertEqual(get_active_process_count(), 0)


class TestExportQualitySettings(unittest.TestCase):
    """Test CRF, maxrate, bufsize, and audio bitrate configuration."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Create dummy assets
        self.audio = self.tmp / "audio.mp3"
        self.audio.write_bytes(b"dummy")
        self.bg = self.tmp / "bg.png"
        self.bg.write_bytes(b"dummy")

        self.base_project = {
            "background": str(self.bg),
            "tracks": [{"path": str(self.audio), "duration": 10.0, "title": "Track 1"}],
            "collection_title": "Test Collection",
            "resolution": "1080p · Full HD",
            "resource_profile": "Balanced",
            "output_path": str(self.tmp / "out.mp4"),
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_high_quality_settings(self):
        """Default export_quality should be High Quality with CRF 22 and 6M cap for 1080p."""
        proj = dict(self.base_project)
        cmd, _ = build_render_command(proj, self.tmp / "work_hq")
        cmd_str = " ".join(cmd)

        self.assertIn("-crf 22", cmd_str)
        self.assertIn("-maxrate 6M", cmd_str)
        self.assertIn("-bufsize 12M", cmd_str)
        self.assertIn("-b:a 192k", cmd_str)

    def test_maximum_quality_archival_settings(self):
        """Maximum Quality should use unconstrained CRF 20 and 256k audio for 1080p."""
        proj = dict(self.base_project)
        proj["export_quality"] = "Maximum Quality (Archival)"
        cmd, _ = build_render_command(proj, self.tmp / "work_max")
        cmd_str = " ".join(cmd)

        self.assertIn("-crf 20", cmd_str)
        self.assertNotIn("-maxrate", cmd_str)
        self.assertIn("-b:a 256k", cmd_str)

    def test_compact_web_settings(self):
        """Compact Quality should use CRF 24 and 4M cap for 1080p."""
        proj = dict(self.base_project)
        proj["export_quality"] = "Compact (Web/Share)"
        cmd, _ = build_render_command(proj, self.tmp / "work_compact")
        cmd_str = " ".join(cmd)

        self.assertIn("-crf 24", cmd_str)
        self.assertIn("-maxrate 4M", cmd_str)
        self.assertIn("-bufsize 8M", cmd_str)
        self.assertIn("-b:a 160k", cmd_str)

    def test_target_bitrate_override(self):
        """Explicit target_bitrate should override CRF and apply custom bitrate."""
        proj = dict(self.base_project)
        proj["target_bitrate"] = "5M"
        cmd, _ = build_render_command(proj, self.tmp / "work_custom")
        cmd_str = " ".join(cmd)

        self.assertIn("-b:v 5M", cmd_str)
        self.assertNotIn("-crf", cmd_str)


if __name__ == "__main__":
    unittest.main()
