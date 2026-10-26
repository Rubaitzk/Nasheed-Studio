"""
Workspace and directory management service.

Organizes user files into structured, configurable locations:
- projects/   : Saved editable project JSON files and managed asset bundles
- templates/  : Reusable design templates
- exports/    : Finished MP4 video exports
- temp/       : Isolated per-job intermediate render artifacts (never in user video folders)
- logs/       : Diagnostic export and error logs
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings

DEFAULT_WORKSPACE_NAME = "NasheedStudio"

# In-memory tracking of temporary workspaces explicitly configured during the active process (e.g. tests)
_session_authorized_temp_workspaces: set[str] = set()


def is_temp_path(path: str | Path | None) -> bool:
    """Return True if path resides inside the operating system's temporary directory."""
    if not path:
        return False
    try:
        p = Path(path).expanduser().resolve()
        temp_dir = Path(tempfile.gettempdir()).resolve()
        try:
            if p.is_relative_to(temp_dir):
                return True
        except AttributeError:
            pass

        # Case-insensitive comparison for Windows drives/casing
        p_str = str(p).lower()
        td_str = str(temp_dir).lower()
        return p_str.startswith(td_str)
    except Exception:
        return False


def is_temp_or_obsolete_path(path: str | Path | None) -> bool:
    """
    Return True if path is None, empty, does not exist, or is an unauthorized
    ephemeral temporary path left behind by an old/crashed process.
    Never deletes any user files.
    """
    if not path:
        return True
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return True
        if is_temp_path(p):
            # If in system temp and was not authorized during this active process, it is a leak
            if str(p) not in _session_authorized_temp_workspaces:
                return True
        return False
    except Exception:
        return True


def get_workspace_root() -> Path:
    """
    Return the active workspace root directory.
    If the persistent QSettings setting points to an obsolete or leaked system temporary directory,
    or a non-existent path, it automatically purges that setting and safely resets to the
    durable default (Path.home() / "NasheedStudio"), preserving any existing user data.
    """
    settings = QSettings("NasheedStudio", "NasheedStudio")
    val = settings.value("workspace_root", "")
    if val and isinstance(val, str) and val.strip():
        candidate = Path(val).expanduser().resolve()
        if not is_temp_or_obsolete_path(candidate):
            return candidate
        # Obsolete or temporary workspace path detected from an old session: purge the stale setting
        settings.remove("workspace_root")

    return (Path.home() / DEFAULT_WORKSPACE_NAME).resolve()


def set_workspace_root(path: str | Path) -> Path:
    """Set the workspace root directory in user settings."""
    resolved = Path(path).expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    if is_temp_path(resolved):
        _session_authorized_temp_workspaces.add(str(resolved))
    settings = QSettings("NasheedStudio", "NasheedStudio")
    settings.setValue("workspace_root", str(resolved))
    ensure_workspace(resolved)
    return resolved


def reset_workspace_root() -> Path:
    """
    Explicitly reset the workspace root to the default durable home directory
    (Path.home() / "NasheedStudio"), purge any obsolete setting, and ensure
    standard subdirectories exist. Existing user files are never deleted.
    """
    settings = QSettings("NasheedStudio", "NasheedStudio")
    settings.remove("workspace_root")
    default_root = (Path.home() / DEFAULT_WORKSPACE_NAME).resolve()
    ensure_workspace(default_root)
    return default_root


@contextmanager
def temporary_workspace(path: str | Path):
    """
    Context manager for tests to isolate workspace configuration.
    Saves the exact prior QSettings state (including whether the key existed)
    and guarantees restoration in finally block before cleanup.
    """
    settings = QSettings("NasheedStudio", "NasheedStudio")
    had_key = settings.contains("workspace_root")
    old_val = settings.value("workspace_root", None)
    try:
        set_workspace_root(path)
        yield Path(path).expanduser().resolve()
    finally:
        if had_key and old_val is not None:
            settings.setValue("workspace_root", old_val)
        else:
            settings.remove("workspace_root")


def get_projects_dir(root: Optional[Path] = None) -> Path:
    p = (root or get_workspace_root()) / "projects"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_templates_dir(root: Optional[Path] = None) -> Path:
    p = (root or get_workspace_root()) / "templates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_exports_dir(root: Optional[Path] = None) -> Path:
    p = (root or get_workspace_root()) / "exports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_temp_dir(root: Optional[Path] = None) -> Path:
    p = (root or get_workspace_root()) / "temp"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_logs_dir(root: Optional[Path] = None) -> Path:
    p = (root or get_workspace_root()) / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_workspace(root: Optional[Path] = None) -> None:
    """Ensure all standard workspace subdirectories exist."""
    r = root or get_workspace_root()
    r.mkdir(parents=True, exist_ok=True)
    get_projects_dir(r)
    get_templates_dir(r)
    get_exports_dir(r)
    get_temp_dir(r)
    get_logs_dir(r)


def create_job_work_dir(job_id: Optional[str] = None, root: Optional[Path] = None) -> Path:
    """
    Create a unique, isolated intermediate render working directory inside workspace temp/.
    This ensures intermediate PNG frames never pollute the user's export or video folder.
    """
    jid = job_id or uuid.uuid4().hex[:10]
    temp_root = get_temp_dir(root)
    work_dir = temp_root / f"render_{jid}"
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def cleanup_job_work_dir(work_dir: Path) -> None:
    """Safely remove a specific job's work directory."""
    try:
        if work_dir.exists() and work_dir.is_dir():
            shutil.rmtree(work_dir, ignore_errors=True)
    except Exception:
        pass


def clean_stale_temp_dirs(max_age_hours: float = 24.0, root: Optional[Path] = None) -> int:
    """
    Recovery policy: scan workspace temp/ for abandoned render directories
    left behind by sudden power loss or process crashes older than max_age_hours.
    Returns the count of cleaned directories.
    """
    temp_root = get_temp_dir(root)
    cleaned = 0
    now = time.time()
    cutoff = now - (max_age_hours * 3600.0)

    try:
        for entry in temp_root.iterdir():
            if entry.is_dir() and entry.name.startswith("render_"):
                try:
                    mtime = entry.stat().st_mtime
                    if mtime < cutoff:
                        shutil.rmtree(entry, ignore_errors=True)
                        cleaned += 1
                except (OSError, PermissionError):
                    continue
    except Exception:
        pass

    return cleaned
