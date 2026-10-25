"""FFmpeg rendering pipeline for video composition with typography, watermarks, intro sequences, and transition SFX.

``render_project`` returns the FFmpeg command list and the work directory
path so that the caller (``ExportJob``) owns process creation and cleanup.
``build_render_command`` is a pure function and is independently testable.
"""
from pathlib import Path
from .media_probe import find_tool
from .timeline import build_timeline
from .compositor import create_composition, create_intro_card, INDICATOR_MODES

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

    # Validate optional intro
    if project.get("intro_enabled"):
        intro_dur = float(project.get("intro_duration", 3.0) or 3.0)
        if not (1.0 <= intro_dur <= 10.0):
            raise ValueError(f"Intro duration must be between 1.0 and 10.0 seconds (got {intro_dur})")
        anim = project.get("intro_animation", "Fade in / out")
        if anim not in ("Fade in / out", "Zoom in", "Slide"):
            raise ValueError(f"Unknown intro animation: {anim}")

    # Validate transition sound effect
    if project.get("transition_sfx_enabled"):
        sfx_path = project.get("transition_sfx_path", "")
        if not sfx_path or not Path(sfx_path).is_file():
            raise FileNotFoundError(f"Transition sound effect file not found: {sfx_path}")
        vol = float(project.get("transition_sfx_volume", 0.7) if project.get("transition_sfx_volume") is not None else 0.7)
        if not (0.0 <= vol <= 1.0):
            raise ValueError(f"Transition SFX volume must be between 0.0 and 1.0 (got {vol})")


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

    # Typography & watermarking
    title_font_family = project.get("title_font_family", "Segoe UI")
    title_font_style = project.get("title_font_style", "Bold")
    title_font_size = int(project.get("title_font_size", 46) or 46)
    track_font_family = project.get("track_font_family", "Segoe UI")
    track_font_style = project.get("track_font_style", "Bold")
    track_font_size = int(project.get("track_font_size", 22) or 22)
    logo_position = project.get("logo_position", "Bottom-Right")
    website_text = project.get("website_text", "")
    website_position = project.get("website_position", "Top-Right")
    website_font_size = int(project.get("website_font_size", 18) or 18)

    # Intro & SFX settings
    intro_enabled = bool(project.get("intro_enabled", False))
    intro_dur = float(project.get("intro_duration", 3.0) or 3.0) if intro_enabled else 0.0
    intro_anim = project.get("intro_animation", "Fade in / out")

    sfx_enabled = bool(project.get("transition_sfx_enabled", False)) and len(tracks) > 1
    sfx_path = project.get("transition_sfx_path", "")
    sfx_vol = float(project.get("transition_sfx_volume", 0.7) if project.get("transition_sfx_volume") is not None else 0.7)
    if sfx_enabled and (not sfx_path or not Path(sfx_path).is_file()):
        sfx_enabled = False

    width, height = RESOLUTIONS.get(project.get("resolution", "1080p · Full HD"), (1920, 1080))
    out_path = Path(project.get("output_path") or "nasheed_collection.mp4").expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    if progress_callback:
        progress_callback("Building composition…")

    # Build timeline offset by intro duration
    timeline = build_timeline(tracks, intro_duration=intro_dur)

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
        title_font_family=title_font_family,
        title_font_style=title_font_style,
        title_font_size=title_font_size,
        track_font_family=track_font_family,
        track_font_style=track_font_style,
        track_font_size=track_font_size,
        logo_position=logo_position,
        website_text=website_text,
        website_position=website_position,
        website_font_size=website_font_size,
    )

    ffmpeg = find_tool("ffmpeg")
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
               "-loop", "1", "-framerate", "30", "-i", base]
    current_input_idx = 1

    # Overlays
    overlay_input_indices = []
    if overlays:
        for overlay in overlays:
            command += ["-loop", "1", "-framerate", "30", "-i", overlay]
            overlay_input_indices.append(current_input_idx)
            current_input_idx += 1

    # Intro Card
    intro_input_idx = None
    if intro_enabled:
        intro_card = create_intro_card(
            width=width,
            height=height,
            background_path=bg,
            logo_path=logo,
            collection_title=project.get("collection_title") or "Nasheed Collection",
            template=project.get("template", "Cinematic"),
            out_dir=str(work_dir),
            title_font_family=title_font_family,
            title_font_style=title_font_style,
            title_font_size=max(32, int(title_font_size * 1.25)),
            website_text=website_text,
        )
        command += ["-loop", "1", "-framerate", "30", "-i", intro_card]
        intro_input_idx = current_input_idx
        current_input_idx += 1

    # Audio Tracks
    track_input_indices = []
    for track in tracks:
        command += ["-i", track["path"]]
        track_input_indices.append(current_input_idx)
        current_input_idx += 1

    # Transition SFX
    sfx_input_idx = None
    if sfx_enabled:
        command += ["-i", sfx_path]
        sfx_input_idx = current_input_idx
        current_input_idx += 1

    filters: list[str] = []

    # ------------------------------------------------------------------
    # 1. Video Filter Graph Construction
    # ------------------------------------------------------------------
    current_v = "0:v"

    # Intro presentation overlay
    if intro_enabled and intro_input_idx is not None:
        intro_fade_d = min(0.5, intro_dur / 3.0)
        intro_out_st = max(0.0, intro_dur - intro_fade_d)

        if intro_anim == "Zoom in":
            filters.append(
                f"[{intro_input_idx}:v]trim=duration={intro_dur:.3f},"
                f"scale=w='iw*(1+0.06*t/{intro_dur:.3f})':h='ih*(1+0.06*t/{intro_dur:.3f})':eval=frame,"
                f"crop={width}:{height},"
                f"fade=t=out:st={intro_out_st:.3f}:d={intro_fade_d:.3f}:alpha=1[intro_fx]"
            )
            filters.append(
                f"[{current_v}][intro_fx]overlay=0:0:enable='between(t\\,0\\,{intro_dur:.3f})'[v_intro]"
            )
        elif intro_anim == "Slide":
            filters.append(f"[{intro_input_idx}:v]trim=duration={intro_dur:.3f}[intro_fx]")
            slide_st = max(0.0, intro_dur - 0.5)
            filters.append(
                f"[{current_v}][intro_fx]overlay=x=0:y='if(gte(t\\,{slide_st:.3f})\\,-(t-{slide_st:.3f})/0.5*{height}\\,0)':"
                f"enable='between(t\\,0\\,{intro_dur:.3f})'[v_intro]"
            )
        else:  # "Fade in / out" (default)
            filters.append(
                f"[{intro_input_idx}:v]trim=duration={intro_dur:.3f},"
                f"fade=t=in:st=0:d={intro_fade_d:.3f}:alpha=1,"
                f"fade=t=out:st={intro_out_st:.3f}:d={intro_fade_d:.3f}:alpha=1[intro_fx]"
            )
            filters.append(
                f"[{current_v}][intro_fx]overlay=0:0:enable='between(t\\,0\\,{intro_dur:.3f})'[v_intro]"
            )
        current_v = "v_intro"

    # Playlist Track Overlays (cursor / highlight)
    if overlays:
        for i, entry in enumerate(timeline):
            next_label = f"v{i + 1}"
            start = f"{entry.start:.3f}".rstrip("0").rstrip(".") or "0"
            end = f"{entry.end:.3f}".rstrip("0").rstrip(".") or "0"
            filters.append(
                f"[{current_v}][{overlay_input_indices[i]}:v]overlay=0:0:enable='between(t\\,{start}\\,{end})'[{next_label}]"
            )
            current_v = next_label

    video_out = f"[{current_v}]" if current_v != "0:v" else "0:v"

    # ------------------------------------------------------------------
    # 2. Audio Filter Graph Construction
    # ------------------------------------------------------------------
    # Normalize each track to 44.1kHz stereo
    for i, in_idx in enumerate(track_input_indices):
        filters.append(
            f"[{in_idx}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a_norm_{i}]"
        )

    concat_inputs = []
    if intro_enabled:
        # Prepend exact silence during intro
        filters.append(
            f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=duration={intro_dur:.3f}[a_intro_silence]"
        )
        concat_inputs.append("[a_intro_silence]")

    for i in range(len(tracks)):
        concat_inputs.append(f"[a_norm_{i}]")

    concat_label = "base_audio" if (sfx_enabled and sfx_input_idx is not None) else "aout"
    concat_filter = "".join(concat_inputs) + f"concat=n={len(concat_inputs)}:v=0:a=1[{concat_label}]"
    filters.append(concat_filter)

    # Transition Sound Effects (SFX) Mixing
    final_audio = f"[{concat_label}]"
    if sfx_enabled and sfx_input_idx is not None:
        num_transitions = len(tracks) - 1
        filters.append(
            f"[{sfx_input_idx}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume={sfx_vol:.2f}[sfx_prep]"
        )
        if num_transitions > 1:
            split_labels = "".join(f"[sfx_{k}]" for k in range(num_transitions))
            filters.append(f"[sfx_prep]asplit={num_transitions}{split_labels}")
            sfx_stream_labels = [f"sfx_{k}" for k in range(num_transitions)]
        else:
            sfx_stream_labels = ["sfx_prep"]

        # Delay each SFX to match the start timestamp of track 1, 2, ..., N-1
        delayed_labels = []
        for k in range(num_transitions):
            transition_time = timeline[k + 1].start
            delay_ms = int(round(transition_time * 1000.0))
            filters.append(f"[{sfx_stream_labels[k]}]adelay={delay_ms}|{delay_ms}[sfx_del_{k}]")
            delayed_labels.append(f"[sfx_del_{k}]")

        # Mix master base audio with delayed transition SFX
        mix_inputs = "[base_audio]" + "".join(delayed_labels)
        filters.append(
            f"{mix_inputs}amix=inputs={1 + num_transitions}:duration=first:dropout_transition=0:normalize=0[aout]"
        )
        final_audio = "[aout]"

    command += [
        "-filter_complex", ";".join(filters),
        "-map", video_out, "-map", final_audio,
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
