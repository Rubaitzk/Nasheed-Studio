"""FFmpeg rendering pipeline for the current MVP.

``render_project`` returns the FFmpeg command list and the work directory
path so that the caller (``ExportJob``) owns process creation and cleanup.
``build_render_command`` is a pure function and is independently testable.
"""
from pathlib import Path
from .media_probe import find_tool
from .timeline import build_timeline
from .compositor import create_composition, INDICATOR_MODES

RESOLUTIONS = {
    "1080p · Full HD": (1920, 1080),
    "1440p · QHD": (2560, 1440),
    "4K UHD": (3840, 2160),
}


def validate_project(project: dict) -> None:
    """Raise ValueError/FileNotFoundError for any unusable project state."""
    tracks = project.get("tracks", [])
    if not tracks:
        raise ValueError("Add at least one audio track before exporting.")
    for track in tracks:
        if not Path(track["path"]).is_file():
            raise FileNotFoundError(f"Audio file not found: {track['path']}")
        if float(track.get("duration", 0) or 0) <= 0:
            raise ValueError(
                f"Track duration is missing for {track.get('title', track['path'])}"
            )
    bg = project.get("background", "")
    if not bg or not Path(bg).is_file():
        raise ValueError("Choose a valid background image first.")
    logo = project.get("logo", "") or None
    if logo and not Path(logo).is_file():
        raise FileNotFoundError(f"Logo file not found: {logo}")

    cursor = project.get("cursor_path", "") or None
    if cursor:
        p = Path(cursor)
        if not p.is_file():
            raise FileNotFoundError(f"Custom cursor file not found: {cursor}")
        supported = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        if p.suffix.lower() not in supported:
            raise ValueError(f"Unsupported cursor format: {p.suffix}. Supported: SVG, PNG, JPG, WEBP, BMP.")


def build_render_command(
    project: dict,
    work_dir: Path,
    progress_callback=None,
) -> tuple[list[str], Path]:
    """
    Prepare assets and return ``(ffmpeg_command, output_path)``.

    The work_dir is owned by the caller; this function writes intermediate
    PNG files there. The caller is responsible for cleanup.
    """
    validate_project(project)

    tracks = project["tracks"]
    bg = project["background"]
    logo = project.get("logo") or None
    indicator_mode = project.get("indicator_mode", "both")
    cursor_path = project.get("cursor_path") or None
    cursor_size = int(project.get("cursor_size", 32) or 32)

    width, height = RESOLUTIONS.get(project.get("resolution", "1080p · Full HD"), (1920, 1080))
    out_path = Path(project.get("output_path") or "nasheed_collection.mp4").expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    if progress_callback:
        progress_callback("Building composition…")

    timeline = build_timeline(tracks)
    base, overlays = create_composition(
        width=width,
        height=height,
        background_path=bg,
        logo_path=logo,
        collection_title=project.get("collection_title") or "Nasheed Collection",
        track_titles=[t.title for t in timeline],
        template=project.get("template", "Cinematic"),
        out_dir=str(work_dir),
        indicator_mode=indicator_mode,
        cursor_path=cursor_path,
        cursor_size=cursor_size,
    )

    ffmpeg = find_tool("ffmpeg")
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
               "-loop", "1", "-framerate", "30", "-i", base]

    if overlays:
        for overlay in overlays:
            command += ["-loop", "1", "-framerate", "30", "-i", overlay]
        audio_start = 1 + len(overlays)
    else:
        audio_start = 1

    for track in tracks:
        command += ["-i", track["path"]]

    filters: list[str] = []

    # 1. Video stream chain
    if overlays:
        current = "0:v"
        for i, entry in enumerate(timeline):
            next_label = f"v{i + 1}"
            start = f"{entry.start:.3f}".rstrip("0").rstrip(".") or "0"
            end = f"{entry.end:.3f}".rstrip("0").rstrip(".") or "0"
            filters.append(
                f"[{current}][{1 + i}:v]overlay=0:0:enable='between(t\\,{start}\\,{end})'[{next_label}]"
            )
            current = next_label
        video_out = f"[{current}]"
    else:
        video_out = "0:v"

    # 2. Audio stream chain: normalize sample rate & channels before concat
    for i in range(len(tracks)):
        filters.append(
            f"[{audio_start + i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}]"
        )
    audio_inputs = "".join(f"[a{i}]" for i in range(len(tracks)))
    filters.append(f"{audio_inputs}concat=n={len(tracks)}:v=0:a=1[aout]")

    command += [
        "-filter_complex", ";".join(filters),
        "-map", video_out, "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-shortest",
        str(out_path),
    ]
    return command, out_path


# ---------------------------------------------------------------------------
# Legacy synchronous entry point (kept for backward-compat / headless tests).
# New code should use ExportJob directly.
# ---------------------------------------------------------------------------

def render_project(project: dict, progress_callback=None) -> str:
    """Synchronous, blocking render. Deprecated in favour of ExportJob."""
    import tempfile, subprocess
    with tempfile.TemporaryDirectory(prefix="nasheed_render_") as tmp:
        work_dir = Path(tmp)
        command, out_path = build_render_command(project, work_dir, progress_callback)
        if progress_callback:
            progress_callback("Rendering video with FFmpeg…")
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "FFmpeg failed to render the video.")
        if progress_callback:
            progress_callback("Export complete")
        return str(out_path)
