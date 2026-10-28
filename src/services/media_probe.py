"""FFprobe integration with bundled binary detection and robust duration probing."""
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

_TOOL_CACHE: dict[str, str] = {}
_VIDEO_INFO_CACHE: dict[tuple[str, float], dict] = {}


def find_tool(name: str) -> str:
    """
    Locate an executable binary (ffmpeg / ffprobe).
    Prioritizes bundled tools (PyInstaller _MEIPASS, adjacent tools/ directory, project tools/),
    falling back to system PATH.
    """
    if name in _TOOL_CACHE and os.path.isfile(_TOOL_CACHE[name]):
        return _TOOL_CACHE[name]

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
            found_path = str(c)
            _TOOL_CACHE[name] = found_path
            return found_path

    # 4. Fallback to system PATH
    found = shutil.which(name)
    if found:
        _TOOL_CACHE[name] = found
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


def is_video_file(path: str | Path | None) -> bool:
    """Return True if path points to an existing playable video file."""
    if not path:
        return False
    p = Path(path)
    if not p.is_file():
        return False

    suffix = p.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return False
    if suffix in VIDEO_EXTENSIONS:
        try:
            info = get_video_info(p)
            return bool(info.get("has_video"))
        except Exception:
            return False

    # Fallback probe for non-standard extensions
    try:
        info = get_video_info(p)
        return bool(info.get("has_video"))
    except Exception:
        return False


def get_video_info(path: str | Path) -> dict:
    """
    Probe video metadata using ffprobe.
    Returns dict with keys:
        width: int
        height: int
        duration: float
        fps: float
        codec: str
        has_video: bool
        has_audio: bool
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Video file not found: {path}")

    canon_path = str(p.resolve())
    try:
        mtime = p.stat().st_mtime
    except OSError:
        mtime = 0.0

    cache_key = (canon_path, mtime)
    if cache_key in _VIDEO_INFO_CACHE:
        return dict(_VIDEO_INFO_CACHE[cache_key])

    command = [
        find_tool("ffprobe"),
        "-v", "error",
        "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,duration",
        "-show_entries", "format=duration",
        "-of", "json",
        str(p),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=60)
    data = json.loads(result.stdout)

    info = {
        "width": 0,
        "height": 0,
        "duration": 0.0,
        "fps": 30.0,
        "codec": "",
        "has_video": False,
        "has_audio": False,
    }

    if "format" in data and "duration" in data["format"]:
        try:
            info["duration"] = float(data["format"]["duration"])
        except (ValueError, TypeError):
            pass

    for s in data.get("streams", []):
        ctype = s.get("codec_type")
        if ctype == "video" and not info["has_video"]:
            info["has_video"] = True
            info["width"] = int(s.get("width") or 0)
            info["height"] = int(s.get("height") or 0)
            info["codec"] = str(s.get("codec_name") or "")
            if "duration" in s:
                try:
                    s_dur = float(s["duration"])
                    if s_dur > 0:
                        info["duration"] = s_dur
                except (ValueError, TypeError):
                    pass
            fps_str = s.get("avg_frame_rate") or s.get("r_frame_rate") or "30/1"
            if "/" in fps_str:
                num, den = fps_str.split("/", 1)
                try:
                    num_f, den_f = float(num), float(den)
                    if den_f > 0:
                        info["fps"] = round(num_f / den_f, 2)
                except (ValueError, ZeroDivisionError):
                    info["fps"] = 30.0
            else:
                try:
                    info["fps"] = float(fps_str)
                except ValueError:
                    info["fps"] = 30.0
        elif ctype == "audio":
            info["has_audio"] = True

    _VIDEO_INFO_CACHE[cache_key] = dict(info)
    return info


def extract_video_frame(video_path: str | Path, timestamp: float = 0.0) -> Image.Image:
    """
    Extract a single representative video frame as a PIL Image at the given timestamp.
    Uses ffmpeg image2 pipe to avoid heavy video decoding dependencies.
    """
    p = Path(video_path)
    if not p.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    ts = max(0.0, float(timestamp or 0.0))
    command = [
        find_tool("ffmpeg"),
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-ss", f"{ts:.3f}",
        "-i", str(p),
        "-frames:v", "1",
        "-f", "image2",
        "pipe:1",
    ]
    result = subprocess.run(command, capture_output=True, check=True, timeout=60)
    if not result.stdout:
        raise ValueError(f"Failed to extract frame from {video_path} at {ts:.3f}s")
    return Image.open(io.BytesIO(result.stdout)).convert("RGB")


