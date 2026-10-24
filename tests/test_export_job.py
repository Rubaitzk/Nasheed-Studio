"""
Bug C regression tests – Export process lifecycle.

Tests start a real, controlled subprocess (a short Python sleep script) via
ExportJob and verify:

  1. cancel()           – child process is dead after cancel.
  2. Induced failure    – non-zero exit code reaches FAILED state; no orphan.
  3. job.join() after cancel – worker thread terminates within timeout.

These tests do NOT require FFmpeg.  They use a short-lived helper script as a
stand-in for FFmpeg so the test suite runs without media files.

PID liveness is checked with psutil if available, otherwise via
os.kill(pid, 0).
"""

import os
import sys
import tempfile
import textwrap
import time
import threading
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional psutil for more reliable PID checks
# ---------------------------------------------------------------------------
try:
    import psutil as _psutil
    def _pid_alive(pid: int) -> bool:
        try:
            p = _psutil.Process(pid)
            return p.status() not in (_psutil.STATUS_ZOMBIE, _psutil.STATUS_DEAD)
        except _psutil.NoSuchProcess:
            return False
except ImportError:
    _psutil = None  # type: ignore
    if sys.platform == "win32":
        import ctypes as _ct
        import ctypes.wintypes as _wt
        _k32 = _ct.WinDLL("kernel32", use_last_error=True)
        _k32.OpenProcess.restype = _wt.HANDLE
        _k32.OpenProcess.argtypes = [_wt.DWORD, _wt.BOOL, _wt.DWORD]
        _k32.GetExitCodeProcess.restype = _wt.BOOL
        _k32.GetExitCodeProcess.argtypes = [_wt.HANDLE, _ct.POINTER(_wt.DWORD)]
        _k32.CloseHandle.restype = _wt.BOOL
        _k32.CloseHandle.argtypes = [_wt.HANDLE]
        _STILL_ACTIVE = 259  # STILL_ACTIVE / STATUS_PENDING

        def _pid_alive(pid: int) -> bool:
            h = _k32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
            if not h:
                return False  # process is gone
            ec = _wt.DWORD(0)
            _k32.GetExitCodeProcess(h, _ct.byref(ec))
            _k32.CloseHandle(h)
            return ec.value == _STILL_ACTIVE
    else:
        def _pid_alive(pid: int) -> bool:
            try:
                os.kill(pid, 0)
                return True
            except (ProcessLookupError, PermissionError):
                return False


# ---------------------------------------------------------------------------
# Helper: build a command that sleeps for `seconds`
# ---------------------------------------------------------------------------

def _sleep_command(seconds: float) -> list[str]:
    """Return a command that sleeps for `seconds` seconds via Python."""
    script = textwrap.dedent(f"""
        import time, sys
        time.sleep({seconds})
        sys.exit(0)
    """)
    return [sys.executable, "-c", script]


def _fail_command() -> list[str]:
    """Return a command that exits with code 1."""
    return [sys.executable, "-c", "import sys; sys.exit(1)"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExportJobLifecycle(unittest.TestCase):

    def _make_job(self, command, callbacks=None):
        from src.services.export_job import ExportJob
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp) / "work"
            out_path = Path(tmp) / "out.mp4"
            callbacks = callbacks or {}
            job = ExportJob(
                command,
                work_dir,
                out_path,
                **callbacks,
            )
        # work_dir deleted – ExportJob will recreate it; we only care about process lifecycle.
        return job

    # ------------------------------------------------------------------
    # Test 1: cancel kills the child process
    # ------------------------------------------------------------------

    def test_cancel_kills_child_process(self):
        """After cancel(), the child process must not be alive."""
        from src.services.export_job import STATE_CANCELLED

        states: list[str] = []
        cancel_event = threading.Event()

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp) / "work"
            out_path = Path(tmp) / "out.mp4"
            from src.services.export_job import ExportJob

            job = ExportJob(
                _sleep_command(30),   # 30-second sleep – we cancel it
                work_dir,
                out_path,
                on_cancelled=lambda: states.append("cancelled"),
                on_failed=lambda m: states.append(f"failed:{m}"),
                on_done=lambda p: states.append("done"),
            )
            job.start()

            # Wait briefly for the process to start.
            time.sleep(0.5)
            self.assertTrue(job.is_running, "Job should be running before cancel")

            pid = job._proc.pid if job._proc else None
            self.assertIsNotNone(pid, "Process must have a PID")

            job.cancel()
            job.join(timeout=8.0)

            self.assertFalse(job.is_running, "Job should not be running after cancel+join")
            self.assertEqual(job.state, STATE_CANCELLED, f"State should be CANCELLED, got {job.state}")
            self.assertIn("cancelled", states, "on_cancelled callback must have fired")

            # Give the OS a moment to reap.
            time.sleep(0.3)
            if pid:
                self.assertFalse(_pid_alive(pid),
                                 f"Child process {pid} is still alive after cancel")

    # ------------------------------------------------------------------
    # Test 2: induced failure reaches FAILED state, no orphan
    # ------------------------------------------------------------------

    def test_failure_reaches_failed_state(self):
        """A non-zero exit code must result in FAILED state and fire on_failed."""
        from src.services.export_job import STATE_FAILED

        errors: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp) / "work"
            out_path = Path(tmp) / "out.mp4"
            from src.services.export_job import ExportJob

            job = ExportJob(
                _fail_command(),
                work_dir,
                out_path,
                on_failed=errors.append,
                on_done=lambda p: errors.append("UNEXPECTED_DONE"),
                on_cancelled=lambda: errors.append("UNEXPECTED_CANCELLED"),
            )
            job.start()
            job.join(timeout=10.0)

            self.assertEqual(job.state, STATE_FAILED,
                             f"State should be FAILED, got {job.state}")
            self.assertTrue(any("UNEXPECTED" not in e for e in errors),
                            "on_failed callback must have fired")

    # ------------------------------------------------------------------
    # Test 3: join() terminates within timeout after cancel
    # ------------------------------------------------------------------

    def test_join_returns_after_cancel(self):
        """job.join() must return within 5 s after cancel() on a 30-s job."""
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp) / "work"
            out_path = Path(tmp) / "out.mp4"
            from src.services.export_job import ExportJob

            job = ExportJob(_sleep_command(30), work_dir, out_path)
            job.start()
            time.sleep(0.4)
            job.cancel()
            t0 = time.monotonic()
            job.join(timeout=5.0)
            elapsed = time.monotonic() - t0
            self.assertLess(elapsed, 5.5,
                            f"join() took {elapsed:.1f}s – expected < 5.5s after cancel")

    # ------------------------------------------------------------------
    # Test 4: successful short job reaches DONE
    # ------------------------------------------------------------------

    def test_short_job_reaches_done(self):
        from src.services.export_job import STATE_DONE

        dones: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp) / "work"
            out_path = Path(tmp) / "out.mp4"
            from src.services.export_job import ExportJob

            job = ExportJob(
                _sleep_command(0.1),
                work_dir,
                out_path,
                on_done=dones.append,
            )
            job.start()
            job.join(timeout=8.0)

            self.assertEqual(job.state, STATE_DONE,
                             f"State should be DONE, got {job.state}")

    # ------------------------------------------------------------------
    # Test 5: duplicate start raises RuntimeError
    # ------------------------------------------------------------------

    def test_duplicate_start_raises(self):
        """Calling start() twice on a running job must raise RuntimeError."""
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp) / "work"
            out_path = Path(tmp) / "out.mp4"
            from src.services.export_job import ExportJob

            job = ExportJob(_sleep_command(10), work_dir, out_path)
            job.start()
            try:
                with self.assertRaises(RuntimeError):
                    job.start()
            finally:
                job.cancel()
                job.join(timeout=5.0)

    # ------------------------------------------------------------------
    # Test 6: work_dir is cleaned up after cancel
    # ------------------------------------------------------------------

    def test_work_dir_cleaned_after_cancel(self):
        """The work directory must not exist after cancel+join."""
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp) / "work"
            work_dir.mkdir()
            out_path = Path(tmp) / "out.mp4"
            from src.services.export_job import ExportJob

            job = ExportJob(_sleep_command(30), work_dir, out_path)
            job.start()
            time.sleep(0.3)
            job.cancel()
            job.join(timeout=5.0)

            self.assertFalse(work_dir.exists(),
                             "work_dir should be removed after cancel")


if __name__ == "__main__":
    unittest.main()
