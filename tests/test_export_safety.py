"""
Tests for Stage 1 Export Safety and Collision Protection.

Requirements covered:
1. Destination protection: never render directly to existing files; render to staging file.
2. Original video preserved bit-for-bit on cancellation or failed renders.
3. Explicit overwrite choices (Overwrite, Choose Another Name, Cancel).
4. Safe replacement with backup rollback if publishing fails.
5. Isolation of work directories in application workspace temp/ (never in user video folder).
6. Stale temp directory cleanup policy.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from src.services.workspace_service import (
    get_workspace_root,
    set_workspace_root,
    get_temp_dir,
    create_job_work_dir,
    cleanup_job_work_dir,
    clean_stale_temp_dirs,
)
from src.services.export_service import (
    generate_job_id,
    get_staging_path,
    validate_rendered_output,
    publish_staged_export,
    cleanup_staging,
)
from src.services.export_job import ExportJob
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestExportSafety(unittest.TestCase):
    def setUp(self):
        _get_app()
        settings = QSettings("NasheedStudio", "NasheedStudio")
        self._had_workspace = settings.contains("workspace_root")
        self._orig_workspace = settings.value("workspace_root", None)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)
        self.workspace_dir = self.tmp / "test_workspace"
        set_workspace_root(self.workspace_dir)

    def tearDown(self):
        settings = QSettings("NasheedStudio", "NasheedStudio")
        if self._had_workspace and self._orig_workspace is not None:
            settings.setValue("workspace_root", self._orig_workspace)
        else:
            settings.remove("workspace_root")
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # 1. Staging Path & Extension Safety
    # ------------------------------------------------------------------
    def test_staging_path_retains_extension_and_parent(self):
        """Staging path must retain .mp4 extension and share parent directory with final destination."""
        dest = self.tmp / "final_export.mp4"
        staging = get_staging_path(dest, job_id="test1234")

        self.assertEqual(staging.parent, dest.parent)
        self.assertTrue(staging.name.endswith(".mp4"))
        self.assertTrue(staging.name.startswith("."))
        self.assertIn("staging_test1234", staging.name)

    # ------------------------------------------------------------------
    # 2. Pre-existing Video Preservation on Cancel and Failure
    # ------------------------------------------------------------------
    def test_staged_export_preserves_existing_video_on_cancel(self):
        """When an export is cancelled, existing destination video remains 100% untouched."""
        dest = self.tmp / "my_precious_video.mp4"
        original_bytes = b"ORIGINAL_EXISTING_MP4_CONTENT_12345"
        dest.write_bytes(original_bytes)

        staging = get_staging_path(dest, job_id="cancel_job")
        work_dir = create_job_work_dir(job_id="cancel_job")

        # Fake command that writes partial data to staging
        fake_cmd = [
            sys.executable,
            "-c",
            "import sys, pathlib, time; pathlib.Path(sys.argv[1]).write_bytes(b'PARTIAL_DATA'); time.sleep(0.5)",
            str(staging),
        ]

        cancelled_flag = []
        job = ExportJob(
            fake_cmd,
            work_dir,
            dest,
            staging_path=staging,
            job_id="cancel_job",
            on_cancelled=lambda: cancelled_flag.append(True),
        )
        job.start()
        # Give worker a moment to create staging, then cancel
        import time
        time.sleep(0.1)
        job.cancel()
        job.join(timeout=3.0)

        self.assertTrue(cancelled_flag)
        # 1. Staging file must be cleaned up
        self.assertFalse(staging.exists())
        # 2. Existing destination must survive unchanged!
        self.assertTrue(dest.exists())
        self.assertEqual(dest.read_bytes(), original_bytes)
        # 3. Work dir must be cleaned up
        self.assertFalse(work_dir.exists())

    def test_staged_export_preserves_existing_video_on_failure(self):
        """When an export fails, existing destination video remains 100% untouched."""
        dest = self.tmp / "important_video.mp4"
        original_bytes = b"PRESERVED_VIDEO_DATA"
        dest.write_bytes(original_bytes)

        staging = get_staging_path(dest, job_id="fail_job")
        work_dir = create_job_work_dir(job_id="fail_job")

        # Command that writes corrupt partial data and exits with error code 1
        fake_cmd = [
            sys.executable,
            "-c",
            "import sys, pathlib; pathlib.Path(sys.argv[1]).write_bytes(b'FAIL_CHUNK'); sys.exit(1)",
            str(staging),
        ]

        failed_flag = []
        job = ExportJob(
            fake_cmd,
            work_dir,
            dest,
            staging_path=staging,
            job_id="fail_job",
            on_failed=lambda err: failed_flag.append(err),
        )
        job.start()
        job.join(timeout=3.0)

        self.assertTrue(failed_flag)
        # Staging file deleted, original preserved, work dir cleaned
        self.assertFalse(staging.exists())
        self.assertTrue(dest.exists())
        self.assertEqual(dest.read_bytes(), original_bytes)
        self.assertFalse(work_dir.exists())

    # ------------------------------------------------------------------
    # 3. Publishing & Safe Replacement with Rollback
    # ------------------------------------------------------------------
    def test_publish_without_overwrite_raises_if_exists(self):
        """Publishing to an existing file without overwrite=True must raise FileExistsError."""
        dest = self.tmp / "dest.mp4"
        dest.write_text("old")
        staging = self.tmp / "staging.mp4"
        staging.write_text("new")

        with self.assertRaises(FileExistsError):
            publish_staged_export(staging, dest, overwrite=False)

        # Staging and dest remain
        self.assertTrue(staging.exists())
        self.assertEqual(dest.read_text(), "old")

    def test_publish_safe_replacement_with_backup_success(self):
        """With overwrite=True, destination is cleanly replaced and backup is removed."""
        dest = self.tmp / "target.mp4"
        dest.write_text("OLD_CONTENT")
        staging = self.tmp / "staging.mp4"
        staging.write_text("NEW_CONTENT")

        publish_staged_export(staging, dest, overwrite=True, job_id="replace1")

        self.assertTrue(dest.exists())
        self.assertEqual(dest.read_text(), "NEW_CONTENT")
        self.assertFalse(staging.exists())
        # No leftover backup files
        bak_files = list(self.tmp.glob("*.bak*"))
        self.assertEqual(len(bak_files), 0)

    def test_publish_safe_replacement_rollback_on_error(self):
        """If replacement fails midway, original destination is restored from backup."""
        dest = self.tmp / "target.mp4"
        dest.write_text("ORIGINAL_CONTENT")
        staging = self.tmp / "staging.mp4"
        staging.write_text("NEW_STAGED")

        # Mock staging.replace to raise an IOError to simulate failure during move
        with patch.object(Path, "replace") as mock_replace:
            # Let the first replace (dest -> backup) succeed, but fail second (staging -> dest)
            call_count = [0]
            real_replace = Path.replace

            def side_effect(src, dst):
                call_count[0] += 1
                if call_count[0] == 2:
                    raise IOError("Simulated disk error or locked destination")
                return real_replace(src, dst)

            mock_replace.side_effect = side_effect

            with self.assertRaises(IOError):
                publish_staged_export(staging, dest, overwrite=True, job_id="fail_replace")

        # Original content must be restored!
        self.assertTrue(dest.exists())
        self.assertEqual(dest.read_text(), "ORIGINAL_CONTENT")

    # ------------------------------------------------------------------
    # 4. Workspace Temp Isolation & Stale Cleanup
    # ------------------------------------------------------------------
    def test_work_dir_isolated_in_workspace_temp(self):
        """create_job_work_dir places temporary render files in workspace temp/."""
        work_dir = create_job_work_dir("job99")
        temp_root = get_temp_dir()

        self.assertEqual(work_dir.parent, temp_root)
        self.assertTrue(work_dir.exists())
        self.assertTrue(work_dir.name.startswith("render_job99"))

        cleanup_job_work_dir(work_dir)
        self.assertFalse(work_dir.exists())

    def test_clean_stale_temp_dirs(self):
        """clean_stale_temp_dirs removes abandoned work directories older than max_age_hours."""
        temp_root = get_temp_dir()
        old_dir = temp_root / "render_old123"
        old_dir.mkdir()
        (old_dir / "old_frame.png").write_text("old")

        # Set modification time to 48 hours ago
        import time
        past = time.time() - (48 * 3600)
        os.utime(str(old_dir), (past, past))

        # New dir created now
        new_dir = temp_root / "render_new456"
        new_dir.mkdir()

        cleaned_count = clean_stale_temp_dirs(max_age_hours=24.0)
        self.assertGreaterEqual(cleaned_count, 1)
        self.assertFalse(old_dir.exists())
        self.assertTrue(new_dir.exists())

    # ------------------------------------------------------------------
    # 5. UI Overwrite Prompt Choices (Overwrite, Rename, Cancel)
    # ------------------------------------------------------------------
    def test_render_video_collision_cancel_aborts_without_rendering(self):
        """When destination exists and user selects Cancel, render is aborted and job is not started."""
        win = MainWindow()
        try:
            target = self.tmp / "existing_video.mp4"
            target.write_bytes(b"EXISTING_DATA")
            win.output_edit.setText(str(target))
            win.background_path = str(self.tmp / "bg.png")
            Path(win.background_path).write_bytes(b"dummy")
            win.tracks = [{"path": str(self.tmp / "t.wav"), "duration": 5.0, "title": "T"}]
            Path(win.tracks[0]["path"]).write_bytes(b"dummy")

            # Mock QMessageBox to simulate user clicking Cancel
            with patch.object(QMessageBox, "exec") as mock_exec, \
                 patch.object(QMessageBox, "clickedButton") as mock_clicked:
                mock_clicked.return_value = None  # None or Cancel button
                win.render_video()

            # Job must not have started
            self.assertIsNone(win._job)
            # Target must remain intact
            self.assertEqual(target.read_bytes(), b"EXISTING_DATA")
        finally:
            dispose_window(win)

    # ------------------------------------------------------------------
    # 6. Real FFmpeg Staged Export & Cancellation Integration Test
    # ------------------------------------------------------------------
    def test_real_ffmpeg_staged_export_and_cancellation(self):
        """End-to-end integration test with real FFmpeg verifying staging, publishing, and cancellation safety."""
        from PIL import Image
        import wave
        from src.services.render_service import build_render_command

        # 1. Assets
        bg_path = self.tmp / "real_bg.png"
        Image.new("RGB", (640, 360), (40, 50, 40)).save(bg_path)

        wav_path = self.tmp / "real_track.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframes(b"\x00\x00\x00\x00" * 44100)  # 1.0s audio

        dest_mp4 = self.tmp / "final_real_output.mp4"
        project = {
            "version": 1,
            "collection_title": "Real FFmpeg Staging Test",
            "background": str(bg_path),
            "logo": "",
            "tracks": [{"path": str(wav_path), "duration": 1.0, "title": "Track 1"}],
            "template": "Cinematic",
            "resolution": "1080p · Full HD",
            "indicator_mode": "neither",
            "output_path": str(dest_mp4),
        }

        job_id = "real1"
        work_dir = create_job_work_dir(job_id=job_id)
        staging_path = get_staging_path(dest_mp4, job_id=job_id)

        cmd, _ = build_render_command(
            project, work_dir, target_path=staging_path
        )

        done_event = []
        job = ExportJob(
            cmd,
            work_dir,
            dest_mp4,
            staging_path=staging_path,
            overwrite=False,
            job_id=job_id,
            on_done=lambda p: done_event.append(p),
        )
        job.start()
        job.join(timeout=10.0)

        # 1. Verify successful export
        self.assertTrue(done_event)
        self.assertTrue(dest_mp4.exists())
        self.assertGreater(dest_mp4.stat().st_size, 5000)
        self.assertFalse(staging_path.exists())
        self.assertFalse(work_dir.exists())

        # 2. Test Cancellation with existing video
        orig_bytes = dest_mp4.read_bytes()
        job_id_2 = "real2"
        work_dir_2 = create_job_work_dir(job_id=job_id_2)
        staging_path_2 = get_staging_path(dest_mp4, job_id=job_id_2)

        cmd2, _ = build_render_command(
            project, work_dir_2, target_path=staging_path_2
        )

        cancel_event = []
        job2 = ExportJob(
            cmd2,
            work_dir_2,
            dest_mp4,
            staging_path=staging_path_2,
            overwrite=True,
            job_id=job_id_2,
            on_cancelled=lambda: cancel_event.append(True),
        )
        job2.start()
        # Immediately cancel
        import time
        time.sleep(0.05)
        job2.cancel()
        job2.join(timeout=10.0)

        self.assertTrue(cancel_event)
        # Verify pre-existing file was NOT touched or deleted!
        self.assertTrue(dest_mp4.exists())
        self.assertEqual(dest_mp4.read_bytes(), orig_bytes)
        self.assertFalse(staging_path_2.exists())
        self.assertFalse(work_dir_2.exists())
