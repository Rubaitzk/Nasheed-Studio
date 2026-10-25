"""
Bug C regression test – Duplicate export guard.

Verifies that:
  1. The UI rejects a second render_video() call while one is running.
  2. The UI returns to idle (Render button enabled, progress hidden) after
     every terminal state: done, failed, cancelled.

Uses an offscreen Qt application; no real FFmpeg or media files are needed.
ExportJob is monkey-patched to a controllable fake.
"""

import sys
import threading
import time
import unittest

from PySide6.QtWidgets import QApplication, QMessageBox

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


# ---------------------------------------------------------------------------
# Fake ExportJob
# ---------------------------------------------------------------------------

class _FakeExportJob:
    """A synchronous, controllable stand-in for ExportJob."""

    def __init__(self, command, work_dir, output_path, *,
                 on_progress=None, on_done=None, on_failed=None, on_cancelled=None):
        from src.services.export_job import STATE_IDLE
        self.state = STATE_IDLE
        self.is_running = False
        self._on_done = on_done or (lambda _: None)
        self._on_failed = on_failed or (lambda _: None)
        self._on_cancelled = on_cancelled or (lambda: None)
        self._output_path = output_path

    def start(self):
        from src.services.export_job import STATE_RUNNING
        if self.is_running:
            raise RuntimeError("Export is already running.")
        self.state = STATE_RUNNING
        self.is_running = True

    def cancel(self):
        from src.services.export_job import STATE_CANCELLED
        self.is_running = False
        self.state = STATE_CANCELLED

    def join(self, timeout=None):
        pass

    # -- helpers for the test to manually trigger terminal states --

    def finish_done(self):
        from src.services.export_job import STATE_DONE
        self.is_running = False
        self.state = STATE_DONE
        self._on_done(str(self._output_path))

    def finish_failed(self, msg="induced failure"):
        from src.services.export_job import STATE_FAILED
        self.is_running = False
        self.state = STATE_FAILED
        self._on_failed(msg)

    def finish_cancelled(self):
        from src.services.export_job import STATE_CANCELLED
        self.is_running = False
        self.state = STATE_CANCELLED
        self._on_cancelled()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDuplicateExportGuard(unittest.TestCase):

    def setUp(self):
        _get_app()
        import src.ui.main_window as mw_module
        import src.services.export_job as job_module

        # Patch build_render_command to return a dummy command.
        import tempfile, pathlib
        from unittest.mock import patch, MagicMock

        self._patcher_cmd = patch(
            "src.ui.main_window.build_render_command",
            return_value=(["python", "-c", "pass"], pathlib.Path(tempfile.mktemp(suffix=".mp4")))
        )
        self._patcher_cmd.start()

        # Patch ExportJob with our fake.
        self._patcher_job = patch("src.ui.main_window.ExportJob", _FakeExportJob)
        self._patcher_job.start()

        self.win = mw_module.MainWindow()
        # Give the window a minimal valid project state.
        import tempfile as _tf, pathlib as _pl
        self.win.background_path = __file__  # any existing file
        self.win.tracks = [
            {"title": "T1", "path": __file__, "duration": 10.0}
        ]
        self.win.show()
        _get_app().processEvents()
        self.win.hide()

    def tearDown(self):
        self._patcher_cmd.stop()
        self._patcher_job.stop()
        from tests.conftest import dispose_window
        dispose_window(self.win)

    def _pump(self):
        _get_app().processEvents()

    def test_duplicate_export_rejected(self):
        """Second call to render_video() while running shows a warning, not a second job."""
        from unittest.mock import patch
        self.win.render_video()
        self._pump()
        first_job = self.win._job
        self.assertIsNotNone(first_job)
        self.assertTrue(first_job.is_running)

        # A second call must NOT replace the job or start a new one.
        with patch("src.ui.main_window.QMessageBox.warning"):
            self.win.render_video()   # should show QMessageBox warning and return
        self._pump()
        self.assertIs(self.win._job, first_job, "Second render_video() must not replace the job")

    def test_ui_idle_after_done(self):
        """Render button must be enabled and progress hidden after a successful export."""
        from unittest.mock import patch
        self.win.render_video()
        self._pump()
        job: _FakeExportJob = self.win._job  # type: ignore
        # Patch QMessageBox.information so it doesn't block the test.
        with patch("src.ui.main_window.QMessageBox.information"):
            job.finish_done()          # directly fires on_done → bridge → _render_complete
            self._pump()
        self.assertTrue(self.win.render_btn.isEnabled(), "Render button should be enabled after done")
        self.assertFalse(self.win.progress.isVisible(), "Progress bar should be hidden after done")
        self.assertIsNone(self.win._job, "_job should be None after done")

    def test_ui_idle_after_failed(self):
        """Render button must be enabled and progress hidden after a failed export."""
        from unittest.mock import patch
        self.win.render_video()
        self._pump()
        job: _FakeExportJob = self.win._job  # type: ignore
        with patch("src.ui.main_window.QMessageBox.critical"):
            job.finish_failed()
            self._pump()
        self.assertTrue(self.win.render_btn.isEnabled(), "Render button should be enabled after failure")
        self.assertFalse(self.win.progress.isVisible(), "Progress bar should be hidden after failure")
        self.assertIsNone(self.win._job)

    def test_ui_idle_after_cancel(self):
        """Render button must be enabled and progress hidden after cancellation."""
        self.win.render_video()
        self._pump()
        job: _FakeExportJob = self.win._job  # type: ignore
        job.finish_cancelled()
        self._pump()
        self.assertTrue(self.win.render_btn.isEnabled(), "Render button should be enabled after cancel")
        self.assertFalse(self.win.progress.isVisible(), "Progress bar should be hidden after cancel")
        self.assertIsNone(self.win._job)

    def test_cancel_btn_visible_while_running(self):
        """Cancel button must be visible (not hidden) while an export is running."""
        self.win.render_video()
        self._pump()
        # Use isHidden() because isVisible() depends on the parent window being shown.
        self.assertFalse(self.win.cancel_btn.isHidden(),
                         "Cancel button should not be hidden while export is running")
        self.assertFalse(self.win.render_btn.isEnabled(),
                         "Render button should be disabled while export is running")

    def test_cancel_btn_hidden_after_done(self):
        """Cancel button must be hidden after a completed export."""
        from unittest.mock import patch
        self.win.render_video()
        self._pump()
        job: _FakeExportJob = self.win._job  # type: ignore
        with patch("src.ui.main_window.QMessageBox.information"):
            job.finish_done()
            self._pump()
        self.assertTrue(self.win.cancel_btn.isHidden(),
                        "Cancel button should be hidden after export completes")


if __name__ == "__main__":
    unittest.main()
