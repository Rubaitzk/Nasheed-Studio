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


def resolve_resolution(res: str) -> tuple[int, int]:
    """Resolve resolution label or alias string to (width, height)."""
    if res in RESOLUTIONS:
        return RESOLUTIONS[res]
    norm = str(res or "").lower().strip()
    if "4k" in norm or "2160" in norm or "uhd" in norm:
        return (3840, 2160)
    if "1440" in norm or "2k" in norm or "qhd" in norm:
        return (2560, 1440)
    if "1080" in norm or "fhd" in norm:
        return (1920, 1080)
    if "720" in norm or "hd" in norm:
        return (1280, 720)
    return (1920, 1080)


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
    target_path: Path | None = None,
) -> tuple[list[str], Path]:
    """
    Prepare assets and return ``(ffmpeg_command, output_path)``.

    The work_dir is owned by the caller; this function writes intermediate
    PNG files there. The caller is responsible for cleanup.
    If target_path is specified, FFmpeg writes to target_path (e.g. staging file).
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
    website_show = bool(project.get("website_show", True) if "website_show" in project else True)
    website_opacity = float(project.get("website_opacity", 1.0) if project.get("website_opacity") is not None else 1.0)

    # Intro & SFX settings
    intro_enabled = bool(project.get("intro_enabled", False))
    intro_dur = float(project.get("intro_duration", 3.0) or 3.0) if intro_enabled else 0.0
    intro_anim = project.get("intro_animation", "Fade in / out")

    sfx_enabled = bool(project.get("transition_sfx_enabled", False)) and len(tracks) > 1
    sfx_path = project.get("transition_sfx_path", "")
    sfx_vol = float(project.get("transition_sfx_volume", 0.7) if project.get("transition_sfx_volume") is not None else 0.7)
    if sfx_enabled and (not sfx_path or not Path(sfx_path).is_file()):
        sfx_enabled = False

    width, height = resolve_resolution(project.get("resolution", "1080p · Full HD"))
    nominal_out = Path(project.get("output_path") or "nasheed_collection.mp4").expanduser().resolve()
    effective_out = Path(target_path).expanduser().resolve() if target_path is not None else nominal_out
    effective_out.parent.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    if progress_callback:
        progress_callback("Building composition…")

    # Build timeline offset by intro duration
    timeline = build_timeline(tracks, intro_duration=intro_dur)

    # Layout, typography, transparency, and styling
    playlist_position = project.get("playlist_position", "Left")
    playlist_x_offset = int(project.get("playlist_x_offset", 0) or 0)
    playlist_y_offset = int(project.get("playlist_y_offset", 0) or 0)
    playlist_width_ratio = float(project.get("playlist_width_ratio", 0.47) or 0.47)
    playlist_columns = int(project.get("playlist_columns", 1) or 1)
    playlist_row_spacing = float(project.get("playlist_row_spacing", 1.85) or 1.85)
    playlist_bg_opacity = float(project.get("playlist_bg_opacity", 0.0) if project.get("playlist_bg_opacity") is not None else 0.0)
    playlist_bg_color = project.get("playlist_bg_color", (0, 0, 0))
    playlist_bg_radius = int(project.get("playlist_bg_radius", 6) or 6)
    track_wrap_text = bool(project.get("track_wrap_text", False))
    title_position = project.get("title_position", "Top-Center")
    title_margin = int(project.get("title_margin", 12) or 12)
    title_show = bool(project.get("title_show", True) if "title_show" in project else True)
    title_color = project.get("title_color", (255, 255, 248))
    title_outline_color = project.get("title_outline_color", (0, 0, 0))
    title_outline_width = int(project.get("title_outline_width", 2) if "title_outline_width" in project else 2)
    title_shadow = bool(project.get("title_shadow", True) if "title_shadow" in project else True)
    track_color = project.get("track_color", (242, 243, 231))
    track_outline_color = project.get("track_outline_color", (0, 0, 0))
    track_outline_width = int(project.get("track_outline_width", 1) if "track_outline_width" in project else 1)
    track_shadow = bool(project.get("track_shadow", True) if "track_shadow" in project else True)
    highlight_style = project.get("highlight_style", "Pill")
    highlight_color = project.get("highlight_color", (248, 220, 139))
    highlight_bg_opacity = float(project.get("highlight_bg_opacity", 0.25) if "highlight_bg_opacity" in project else 0.25)
    logo_cleanup_mode = project.get("logo_cleanup_mode", "auto")
    logo_scale = float(project.get("logo_scale", 1.0) or 1.0)

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
        website_show=website_show,
        website_opacity=website_opacity,
        playlist_position=playlist_position,
        playlist_x_offset=playlist_x_offset,
        playlist_y_offset=playlist_y_offset,
        playlist_width_ratio=playlist_width_ratio,
        playlist_columns=playlist_columns,
        playlist_row_spacing=playlist_row_spacing,
        playlist_bg_opacity=playlist_bg_opacity,
        playlist_bg_color=playlist_bg_color,
        playlist_bg_radius=playlist_bg_radius,
        track_wrap_text=track_wrap_text,
        title_position=title_position,
        title_margin=title_margin,
        title_show=title_show,
        title_color=title_color,
        title_outline_color=title_outline_color,
        title_outline_width=title_outline_width,
        title_shadow=title_shadow,
        track_color=track_color,
        track_outline_color=track_outline_color,
        track_outline_width=track_outline_width,
        track_shadow=track_shadow,
        active_track_color=project.get("active_track_color", None),
        highlight_style=highlight_style,
        highlight_color=highlight_color,
        highlight_bg_opacity=highlight_bg_opacity,
        logo_cleanup_mode=logo_cleanup_mode,
        logo_scale=logo_scale,
    )

    ffmpeg = find_tool("ffmpeg")
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
               "-progress", "pipe:1", "-nostats",
               "-loop", "1", "-framerate", "30", "-i", base]
    current_input_idx = 1

    # Overlays
    overlay_input_indices = []
    if overlays:
        for overlay in overlays:
            command += ["-loop", "1", "-framerate", "1", "-i", overlay]
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
            website_show=website_show,
            website_opacity=website_opacity,
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
    # Normalize each track to 44.1kHz stereo with exact presentation timestamps and boundary padding/trimming
    for i, in_idx in enumerate(track_input_indices):
        track_dur = float(tracks[i].get("duration", 0) or 0.0)
        dur_clause = f",apad=whole_dur={track_dur:.3f},atrim=0:{track_dur:.3f}" if track_dur > 0 else ""
        filters.append(
            f"[{in_idx}:a:0]asetpts=PTS-STARTPTS{dur_clause},"
            f"aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a_norm_{i}]"
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
        # Trim SFX to maximum 2.5s with a 0.5s fade-out so it never bleeds across subsequent track audio
        filters.append(
            f"[{sfx_input_idx}:a:0]atrim=0:2.5,afade=t=out:st=2.0:d=0.5,"
            f"aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume={sfx_vol:.2f}[sfx_prep]"
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

    # Resource Profile Configuration
    resource_profile = str(project.get("resource_profile") or "Balanced").strip()
    cpu_cores = __import__("os").cpu_count() or 4
    if resource_profile == "Background-friendly":
        profile_threads = 2
        profile_preset = "faster"
    elif resource_profile == "Maximum-speed":
        profile_threads = max(4, cpu_cores)
        profile_preset = "veryfast"
    else:  # "Balanced" (default)
        profile_threads = max(2, cpu_cores // 2)
        profile_preset = "veryfast"

    # Resolution-tuned CRF
    res_str = str(project.get("resolution", "")).lower()
    if "4k" in res_str:
        crf_val = "18"
    elif "1440" in res_str:
        crf_val = "19"
    else:
        crf_val = "20"

    command += [
        "-filter_complex", ";".join(filters),
        "-map", video_out, "-map", final_audio,
        "-c:v", "libx264", "-preset", profile_preset, "-threads", str(profile_threads), "-crf", crf_val,
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-shortest",
        str(effective_out),
    ]
    return command, effective_out


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
