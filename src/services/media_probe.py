"""FFprobe integration. FFmpeg binaries can be bundled with the app later."""
import json
import shutil
import subprocess
from pathlib import Path


def find_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    # Support a local bundled tools folder in development / packaged builds.
    suffix = ".exe" if __import__("os").name == "nt" else ""
    for candidate in (Path(__file__).resolve().parents[2] / "tools" / f"{name}{suffix}", Path(__file__).resolve().parents[2] / f"{name}{suffix}"):
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(f"{name} was not found. Install FFmpeg and add it to PATH, or place it in the app's tools folder.")


def get_duration(path: str) -> float:
    command = [find_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "json", path]
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=60)
    duration = float(json.loads(result.stdout)["format"]["duration"])
    if duration <= 0:
        raise ValueError(f"Could not determine a valid duration for {path}")
    return duration
