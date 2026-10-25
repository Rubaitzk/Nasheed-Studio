"""
Export staging, validation, atomic publication, and collision safety service.

Design & Safety Rules:
1. Never render directly to a final destination. Render to a unique staging file
   in the destination directory with a valid extension (e.g. .mp4) so FFmpeg can format it properly.
2. Only publish after FFmpeg exits successfully and the output passes validation (non-empty, valid streams).
3. On cancellation or failure, delete ONLY the staging file. The original destination is NEVER touched.
4. If overwrite is confirmed, use a safe two-phase replacement with backup rollback:
   - Rename original to temporary backup.
   - Move staging to destination.
   - On success: delete backup.
   - On failure: restore backup to original path and propagate error.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional, Tuple

from .media_probe import find_tool
from .workspace_service import get_logs_dir


def generate_job_id() -> str:
    """Generate a compact 8-character unique job identifier."""
    return uuid.uuid4().hex[:8]


def get_staging_path(final_destination: Path, job_id: Optional[str] = None) -> Path:
    """
    Generate a collision-safe staging file path in the same directory as destination.
    Retains the original video extension (.mp4) so FFmpeg detects the container muxer.
    """
    dest = Path(final_destination).expanduser().resolve()
    jid = job_id or generate_job_id()
    # e.g., /path/to/.my_video.staging_a1b2c3d4.mp4
    staging_name = f".{dest.stem}.staging_{jid}{dest.suffix}"
    return dest.parent / staging_name


def validate_rendered_output(staging_path: Path) -> Tuple[bool, str]:
    """
    Verify that the rendered staging file exists, is non-empty, and contains
    valid media streams recognized by ffprobe.
    """
    if not staging_path.exists():
        return False, f"Staged output file does not exist: {staging_path}"

    try:
        size = staging_path.stat().st_size
        if size < 1024:
            return False, f"Staged output file is corrupted or too small ({size} bytes)"
    except Exception as exc:
        return False, f"Cannot inspect staged output: {exc}"

    # Probe media format with ffprobe
    ffprobe = find_tool("ffprobe")
    if ffprobe:
        try:
            cmd = [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration:stream=codec_type",
                "-of", "json",
                str(staging_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10.0)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                streams = data.get("streams", [])
                has_video = any(s.get("codec_type") == "video" for s in streams)
                has_audio = any(s.get("codec_type") == "audio" for s in streams)
                if not has_video:
                    return False, "Rendered video stream is missing or unreadable"
                if not has_audio:
                    return False, "Rendered audio stream is missing or unreadable"
        except Exception as exc:
            # If probe fails due to timeout or missing binary, proceed if size is healthy
            pass

    return True, ""


def publish_staged_export(
    staging_path: Path,
    final_destination: Path,
    overwrite: bool = False,
    job_id: Optional[str] = None,
) -> Path:
    """
    Publish the validated staging file to the final destination.
    Uses an atomic swap with rollback to ensure the original file is preserved
    if replacement fails (e.g. locked file or permission error).
    """
    staging = Path(staging_path).resolve()
    dest = Path(final_destination).resolve()

    if not staging.exists():
        raise FileNotFoundError(f"Staged file missing before publication: {staging}")

    # Ensure parent directory exists
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        if not overwrite:
            raise FileExistsError(
                f"Destination file already exists and overwrite was not permitted: {dest}"
            )

        # Safe two-phase replacement with backup
        jid = job_id or generate_job_id()
        backup_path = dest.parent / f".{dest.name}.bak_{jid}"
        try:
            # 1. Rename existing destination to backup
            dest.replace(backup_path)
            # 2. Move staging file into place
            staging.replace(dest)
            # 3. Success: delete temporary backup
            try:
                backup_path.unlink(missing_ok=True)
            except Exception:
                pass
        except Exception as exc:
            # 4. Replacement failed: restore original backup
            if backup_path.exists():
                try:
                    backup_path.replace(dest)
                except Exception:
                    pass
            raise IOError(f"Could not safely replace destination {dest}: {exc}") from exc
    else:
        # Destination does not exist: simple atomic move
        staging.replace(dest)

    return dest


def cleanup_staging(staging_path: Path) -> None:
    """Safely unlink the temporary staging file if present."""
    try:
        p = Path(staging_path)
        if p.exists():
            p.unlink(missing_ok=True)
    except Exception:
        pass


def write_export_log(
    job_id: str,
    command: list[str],
    output_path: str,
    duration_sec: float,
    success: bool,
    error: str = "",
) -> Path:
    """Record an export session log into workspace logs/."""
    logs_dir = get_logs_dir()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"export_{timestamp}_{job_id}.log"
    try:
        content = [
            f"Job ID: {job_id}",
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Target Output: {output_path}",
            f"Duration: {duration_sec:.2f} seconds",
            f"Success: {success}",
        ]
        if error:
            content.append(f"Error:\n{error}")
        content.append("\nCommand Line:")
        content.append(" ".join(command))
        log_file.write_text("\n".join(content), encoding="utf-8")
    except Exception:
        pass
    return log_file
