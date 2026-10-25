"""
Owned, cancellable FFmpeg export job.

Design decisions
----------------
* The job runs FFmpeg in a child process owned by a Windows Job Object so that
  the entire process tree is killed when the Job Object handle is closed – even
  if the Python parent exits abnormally.
* On non-Windows systems a process-group kill is used as a fallback.
* The job runs in a background thread so the Qt event loop stays responsive.
* Cancel, failure, and completion all reach a single ``_finish`` path that
  cleans temp files and emits the right terminal signal.
* ``ExportJob`` is pure business logic – it does not import any Qt symbol at
  the module level so it can be unit-tested without a display.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Windows Job Object helpers
# ---------------------------------------------------------------------------

_job_handle = None  # type: ignore[assignment]

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes as _wt

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    # CreateJobObjectW
    _kernel32.CreateJobObjectW.restype = _wt.HANDLE
    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]

    # SetInformationJobObject
    _kernel32.SetInformationJobObject.restype = _wt.BOOL
    _kernel32.SetInformationJobObject.argtypes = [
        _wt.HANDLE, ctypes.c_int, ctypes.c_void_p, _wt.DWORD
    ]

    # AssignProcessToJobObject
    _kernel32.AssignProcessToJobObject.restype = _wt.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [_wt.HANDLE, _wt.HANDLE]

    # TerminateJobObject
    _kernel32.TerminateJobObject.restype = _wt.BOOL
    _kernel32.TerminateJobObject.argtypes = [_wt.HANDLE, _wt.UINT]

    # CloseHandle
    _kernel32.CloseHandle.restype = _wt.BOOL
    _kernel32.CloseHandle.argtypes = [_wt.HANDLE]

    # OpenProcess
    _kernel32.OpenProcess.restype = _wt.HANDLE
    _kernel32.OpenProcess.argtypes = [_wt.DWORD, _wt.BOOL, _wt.DWORD]

    _JobObjectExtendedLimitInformation = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _PROCESS_ALL_ACCESS = 0x1F0FFF

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", _wt.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", _wt.DWORD),
            ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
            ("PriorityClass", _wt.DWORD),
            ("SchedulingClass", _wt.DWORD),
        ]

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    def _create_job_object() -> Optional[_wt.HANDLE]:
        """Create a Windows Job Object with KILL_ON_JOB_CLOSE."""
        job = _kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = _kernel32.SetInformationJobObject(
            job,
            _JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            _kernel32.CloseHandle(job)
            return None
        return job

    def _assign_to_job(job_handle, pid: int) -> bool:
        proc = _kernel32.OpenProcess(_PROCESS_ALL_ACCESS, False, pid)
        if not proc:
            return False
        ok = bool(_kernel32.AssignProcessToJobObject(job_handle, proc))
        _kernel32.CloseHandle(proc)
        return ok

    def _terminate_job(job_handle) -> None:
        _kernel32.TerminateJobObject(job_handle, 1)

    def _close_handle(handle) -> None:
        _kernel32.CloseHandle(handle)

else:
    # POSIX fallback – use process groups.
    def _create_job_object():  # type: ignore[misc]
        return None

    def _assign_to_job(job_handle, pid: int) -> bool:  # type: ignore[misc]
        return False

    def _terminate_job(job_handle) -> None:  # type: ignore[misc]
        pass

    def _close_handle(handle) -> None:  # type: ignore[misc]
        pass


# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------

STATE_IDLE = "idle"
STATE_RUNNING = "running"
STATE_CANCELLED = "cancelled"
STATE_FAILED = "failed"
STATE_DONE = "done"


# ---------------------------------------------------------------------------
# ExportJob
# ---------------------------------------------------------------------------

class ExportJob:
    """
    One export job: one FFmpeg invocation, owned by a Job Object.

    Callbacks (all optional, called from the worker thread):
        on_progress(message: str)
        on_done(output_path: str)
        on_failed(error_message: str)
        on_cancelled()
    """

    def __init__(
        self,
        command: list[str],
        work_dir: Path,
        output_path: Path,
        *,
        staging_path: Optional[Path] = None,
        overwrite: bool = False,
        job_id: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None,
        on_done: Optional[Callable[[str], None]] = None,
        on_failed: Optional[Callable[[str], None]] = None,
        on_cancelled: Optional[Callable[[], None]] = None,
    ) -> None:
        self._command = command
        self._work_dir = Path(work_dir)
        self._output_path = Path(output_path)
        self._staging_path = Path(staging_path) if staging_path is not None else None
        self._overwrite = overwrite
        self._job_id = job_id
        self._on_progress = on_progress or (lambda _: None)
        self._on_done = on_done or (lambda _: None)
        self._on_failed = on_failed or (lambda _: None)
        self._on_cancelled = on_cancelled or (lambda: None)

        self._state = STATE_IDLE
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen] = None  # type: ignore[type-arg]
        self._job_handle = None  # Windows Job Object handle

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def is_running(self) -> bool:
        return self.state == STATE_RUNNING

    def start(self) -> None:
        """Start the export in a background thread. Raises if already running."""
        with self._lock:
            if self._state == STATE_RUNNING:
                raise RuntimeError("Export is already running.")
            self._state = STATE_RUNNING
        self._thread = threading.Thread(target=self._run, daemon=True, name="ExportJob")
        self._thread.start()

    def cancel(self) -> None:
        """Request cancellation. Safe to call from any thread."""
        with self._lock:
            if self._state != STATE_RUNNING:
                return
            self._state = STATE_CANCELLED
            # Kill while holding the lock to atomically read/clear _job_handle/_proc.
            self._kill_process_tree_locked()

    def join(self, timeout: Optional[float] = None) -> None:
        """Wait for the worker thread to finish."""
        if self._thread:
            self._thread.join(timeout)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        stderr_buf: list[str] = []
        try:
            # Check if already cancelled before we even start.
            with self._lock:
                if self._state == STATE_CANCELLED:
                    self._finish(STATE_CANCELLED)
                    return

            self._on_progress("Starting FFmpeg…")
            popen_kwargs: dict = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.PIPE,
                "text": True,
            }
            if sys.platform == "win32":
                # Do NOT create a new console window.
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

            proc = subprocess.Popen(self._command, **popen_kwargs)

            # Atomically store proc and assign to Job Object.
            with self._lock:
                self._proc = proc
                # Assign the child to a Job Object so it is killed when we close the handle.
                if sys.platform == "win32":
                    self._job_handle = _create_job_object()
                    if self._job_handle:
                        _assign_to_job(self._job_handle, self._proc.pid)
                # If cancel() was called between Popen and here, kill now.
                if self._state == STATE_CANCELLED:
                    self._kill_process_tree_locked()

            # Stream stderr so we accumulate error output.
            assert self._proc.stderr is not None
            for line in self._proc.stderr:
                stderr_buf.append(line)

            self._proc.wait()
            returncode = self._proc.returncode

        except Exception as exc:
            self._finish(STATE_FAILED, error=str(exc))
            return

        with self._lock:
            current_state = self._state

        if current_state == STATE_CANCELLED:
            self._finish(STATE_CANCELLED)
        elif returncode == 0:
            self._finish(STATE_DONE)
        else:
            err = "".join(stderr_buf).strip() or f"FFmpeg exited with code {returncode}."
            self._finish(STATE_FAILED, error=err)

    def _kill_process_tree_locked(self) -> None:
        """Kill process tree. MUST be called while self._lock is held."""
        jh = self._job_handle
        proc = self._proc
        self._job_handle = None  # prevent double-kill
        if jh is not None:
            _terminate_job(jh)
            _close_handle(jh)
        elif proc is not None:
            try:
                if sys.platform == "win32":
                    proc.kill()
                else:
                    import signal, os as _os
                    _os.killpg(_os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass

    def _kill_process_tree(self) -> None:
        """Kill the FFmpeg process tree. Safe to call from any thread."""
        with self._lock:
            self._kill_process_tree_locked()

    def _finish(self, terminal_state: str, *, error: str = "") -> None:
        """Clean up and fire the appropriate callback. Called exactly once."""
        from .export_service import (
            validate_rendered_output,
            publish_staged_export,
            cleanup_staging,
        )

        # Ensure the Job Object is closed (kills any surviving children).
        with self._lock:
            self._kill_process_tree_locked()

        # Clean up work directory.
        try:
            if self._work_dir.exists():
                shutil.rmtree(self._work_dir, ignore_errors=True)
        except Exception:
            pass

        if terminal_state == STATE_DONE:
            if self._staging_path is not None:
                is_valid, val_err = validate_rendered_output(self._staging_path)
                if not is_valid:
                    cleanup_staging(self._staging_path)
                    with self._lock:
                        self._state = STATE_FAILED
                    self._on_failed(f"Render output validation failed: {val_err}")
                    return
                try:
                    publish_staged_export(
                        self._staging_path,
                        self._output_path,
                        overwrite=self._overwrite,
                        job_id=self._job_id,
                    )
                except Exception as exc:
                    cleanup_staging(self._staging_path)
                    with self._lock:
                        self._state = STATE_FAILED
                    self._on_failed(f"Could not publish rendered video: {exc}")
                    return

            with self._lock:
                self._state = STATE_DONE
            self._on_done(str(self._output_path))

        elif terminal_state == STATE_CANCELLED:
            # If staged: delete ONLY the staging file. Pre-existing target remains untouched!
            if self._staging_path is not None:
                cleanup_staging(self._staging_path)
            else:
                try:
                    if self._output_path.exists():
                        self._output_path.unlink(missing_ok=True)
                except Exception:
                    pass
            with self._lock:
                self._state = STATE_CANCELLED
            self._on_cancelled()

        else:  # FAILED
            # If staged: delete ONLY the staging file. Pre-existing target remains untouched!
            if self._staging_path is not None:
                cleanup_staging(self._staging_path)
            else:
                try:
                    if self._output_path.exists():
                        self._output_path.unlink(missing_ok=True)
                except Exception:
                    pass
            with self._lock:
                self._state = STATE_FAILED
            self._on_failed(error)
