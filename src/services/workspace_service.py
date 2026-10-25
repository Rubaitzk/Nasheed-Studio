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
import time
import uuid
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings

DEFAULT_WORKSPACE_NAME = "NasheedStudio"


def get_workspace_root() -> Path:
    """Return the active workspace root directory, configured via QSettings or default."""
    settings = QSettings("NasheedStudio", "NasheedStudio")
    val = settings.value("workspace_root", "")
    if val and isinstance(val, str) and val.strip():
        return Path(val).expanduser().resolve()
    return (Path.home() / DEFAULT_WORKSPACE_NAME).resolve()


def set_workspace_root(path: str | Path) -> Path:
    """Set the workspace root directory in user settings."""
    resolved = Path(path).expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    settings = QSettings("NasheedStudio", "NasheedStudio")
    settings.setValue("workspace_root", str(resolved))
    ensure_workspace(resolved)
    return resolved


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
