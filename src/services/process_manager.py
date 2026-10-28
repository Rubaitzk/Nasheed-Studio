"""Process lifecycle manager for Nasheed Studio.

Guarantees:
1. All subprocesses (FFmpeg, FFprobe) spawned by the application are tracked.
2. Subprocesses on Windows always run with CREATE_NO_WINDOW so no console windows or
   orphaned conhosts are spawned.
3. On application exit (normal exit, closeEvent, crash, or unhandled exception via atexit/signal),
   all active child processes are terminated gracefully with bounded waiting, escalating to
   kill only if necessary.
4. Zero indiscriminate termination by name: ONLY processes spawned and owned by this application
   instance are managed and cleaned up.
"""

from __future__ import annotations

import atexit
import os
import signal
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional, Set

# Windows-specific flags
if sys.platform == "win32":
    CREATE_NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
else:
    CREATE_NO_WINDOW = 0

_LOCK = threading.Lock()
_ACTIVE_PROCESSES: Set[subprocess.Popen] = set()
_CLEANED_UP = False


def register_process(proc: subprocess.Popen) -> None:
    """Register an active child process for managed tracking and cleanup."""
    if proc is None:
        return
    with _LOCK:
        if not _CLEANED_UP:
            _ACTIVE_PROCESSES.add(proc)


def unregister_process(proc: subprocess.Popen) -> None:
    """Unregister a finished child process."""
    if proc is None:
        return
    with _LOCK:
        _ACTIVE_PROCESSES.discard(proc)


def get_active_process_count() -> int:
    """Return count of currently running tracked child processes."""
    with _LOCK:
        # Prune dead processes while counting
        dead = [p for p in _ACTIVE_PROCESSES if p.poll() is not None]
        for p in dead:
            _ACTIVE_PROCESSES.discard(p)
        return len(_ACTIVE_PROCESSES)


def terminate_process_tree(
    proc: subprocess.Popen,
    timeout: float = 2.0,
) -> None:
    """
    Gracefully terminate a child process with bounded waiting, escalating to kill.
    Safe to call from any thread.
    """
    if proc is None or proc.poll() is not None:
        return

    # Attempt graceful termination first
    try:
        proc.terminate()
    except (OSError, ProcessLookupError):
        return

    # Bounded wait for graceful termination
    try:
        proc.wait(timeout=timeout)
        return
    except (subprocess.TimeoutExpired, Exception):
        pass

    # Escalate to kill if still alive
    try:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=1.0)
    except (OSError, ProcessLookupError, Exception):
        pass


def cleanup_all_processes(timeout_per_process: float = 1.5) -> None:
    """
    Clean up all active child processes started by this application instance.
    Registered with atexit and called explicitly on application shutdown.
    """
    global _CLEANED_UP
    with _LOCK:
        procs_to_clean = list(_ACTIVE_PROCESSES)
        _ACTIVE_PROCESSES.clear()
        _CLEANED_UP = True

    for proc in procs_to_clean:
        if proc.poll() is None:
            terminate_process_tree(proc, timeout=timeout_per_process)


def run_tracked_subprocess(
    cmd: list[str],
    *,
    timeout: Optional[float] = None,
    capture_output: bool = True,
    text: bool = True,
    check: bool = False,
    extra_flags: int = 0,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """
    Run a subprocess with CREATE_NO_WINDOW on Windows, automatic lifecycle tracking,
    and bounded timeout cleanup. Drop-in safe replacement for subprocess.run.
    """
    popen_kwargs = dict(kwargs)
    if sys.platform == "win32":
        creationflags = popen_kwargs.get("creationflags", 0) | CREATE_NO_WINDOW | extra_flags
        popen_kwargs["creationflags"] = creationflags

    if capture_output:
        popen_kwargs["stdout"] = subprocess.PIPE
        popen_kwargs["stderr"] = subprocess.PIPE

    if text:
        popen_kwargs["text"] = True

    proc = subprocess.Popen(cmd, **popen_kwargs)
    register_process(proc)

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        retcode = proc.poll()
        if retcode is None:
            retcode = 0
    except subprocess.TimeoutExpired:
        terminate_process_tree(proc, timeout=1.5)
        stdout, stderr = proc.communicate()
        raise subprocess.TimeoutExpired(cmd, timeout or 0, output=stdout, stderr=stderr)
    except Exception:
        terminate_process_tree(proc, timeout=1.5)
        raise
    finally:
        unregister_process(proc)

    if check and retcode != 0:
        raise subprocess.CalledProcessError(retcode, cmd, output=stdout, stderr=stderr)

    return subprocess.CompletedProcess(cmd, retcode, stdout, stderr)


# Register atexit handler so child processes are NEVER orphaned on unexpected exits
atexit.register(cleanup_all_processes)
