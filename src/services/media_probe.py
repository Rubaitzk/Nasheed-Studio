"""FFprobe integration with bundled binary detection and robust duration probing."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_tool(name: str) -> str:
    """
    Locate an executable binary (ffmpeg / ffprobe).
    Prioritizes bundled tools (PyInstaller _MEIPASS, adjacent tools/ directory, project tools/),
    falling back to system PATH.
    """
    suffix = ".exe" if os.name == "nt" else ""
    filename = f"{name}{suffix}"

    candidates: list[Path] = []

    # 1. PyInstaller temporary extraction directory
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "tools" / filename)
        candidates.append(Path(sys._MEIPASS) / filename)

    # 2. Directory adjacent to the running executable / script
    exe_dir = Path(sys.executable).parent
    candidates.append(exe_dir / "tools" / filename)
    candidates.append(exe_dir / filename)

    # 3. Development project directory (2 levels up from services/)
    proj_root = Path(__file__).resolve().parents[2]
    candidates.append(proj_root / "tools" / filename)
    candidates.append(proj_root / filename)

    for c in candidates:
        if c.is_file():
            return str(c)

    # 4. Fallback to system PATH
    found = shutil.which(name)
    if found:
        return found

    raise FileNotFoundError(
        f"{name} was not found. Place {filename} in the tools folder or install FFmpeg and add it to PATH."
    )


def get_duration(path: str) -> float:
    """
    Probe the duration of an audio/video file in seconds.
    Tries format duration first, then falls back to stream duration for gapless/container compatibility.
    """
    command = [
        find_tool("ffprobe"),
        "-v", "error",
        "-show_entries", "format=duration:stream=duration",
        "-of", "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=60)
    data = json.loads(result.stdout)

    # Try format duration
    dur = 0.0
    if "format" in data and "duration" in data["format"]:
        try:
            dur = float(data["format"]["duration"])
        except (ValueError, TypeError):
            pass

    # Try stream duration if format duration missing/invalid
    if dur <= 0 and "streams" in data:
        for s in data["streams"]:
            if "duration" in s:
                try:
                    candidate = float(s["duration"])
                    if candidate > 0:
                        dur = candidate
                        break
                except (ValueError, TypeError):
                    pass

    if dur <= 0:
        raise ValueError(f"Could not determine a valid duration for {path}")
    return dur

