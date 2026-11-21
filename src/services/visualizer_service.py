"""
Audio analysis and reactive visualizer service for Nasheed Studio.

Provides audio feature extraction (FFT spectrum, waveform, envelope) and
renders real-time audio-reactive visualizers in two styles:
1. "Standard (Horizontal Bars)": Multi-element frequency bars reacting to audio spectrum.
2. "Heartbeat": Audio-reactive waveform / rhythmic pulse line.

Supports appearance customization:
- Color (RGB)
- Element count (number of bars or sample points)
- Element size (bar thickness / stroke width)
- Width & Position (X, Y)
- Amplitude scaling
- Direction: Upward, Downward, Bidirectional

Provides both single-frame rendering for GUI preview and high-throughput
stream rendering into transparent RGBA video for FFmpeg overlay composition.
"""

from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image

# Audio sample rate for analysis
ANALYSIS_SR = 44100
_AUDIO_CACHE: Dict[Tuple[str, float], np.ndarray] = {}


def _hex_or_tuple_to_rgb(val: Union[str, tuple, list], default: Tuple[int, int, int] = (56, 189, 248)) -> Tuple[int, int, int]:
    """Parse color into (R, G, B) tuple."""
    if isinstance(val, (tuple, list)) and len(val) >= 3:
        return (int(val[0]), int(val[1]), int(val[2]))
    if isinstance(val, str):
        s = val.strip().lstrip("#")
        if len(s) == 6:
            try:
                return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
            except ValueError:
                pass
    return default


def load_audio_samples(audio_path: str, target_sr: int = ANALYSIS_SR) -> np.ndarray:
    """
    Decode audio file into a 1D float32 numpy array normalized to [-1.0, 1.0].
    Caches decoded audio in memory by path and mtime.
    """
    p = Path(audio_path)
    if not p.is_file():
        return np.zeros(0, dtype=np.float32)

    mtime = p.stat().st_mtime
    cache_key = (str(p.resolve()), mtime)
    if cache_key in _AUDIO_CACHE:
        return _AUDIO_CACHE[cache_key]

    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-i", str(p),
        "-f", "f32le",
        "-ac", "1",
        "-ar", str(target_sr),
        "pipe:1"
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        samples = np.frombuffer(proc.stdout, dtype=np.float32)
    except Exception:
        samples = np.zeros(0, dtype=np.float32)

    _AUDIO_CACHE[cache_key] = samples
    return samples


def build_timeline_audio(
    tracks: List[dict],
    intro_duration: float = 0.0,
    target_sr: int = ANALYSIS_SR,
) -> np.ndarray:
    """
    Assemble complete continuous mono audio for the timeline, matching
    track durations and intro offset.
    """
    segments: List[np.ndarray] = []

    if intro_duration > 0:
        intro_samples = int(round(intro_duration * target_sr))
        segments.append(np.zeros(intro_samples, dtype=np.float32))

    for tr in tracks:
        path = tr.get("path", "")
        nominal_dur = float(tr.get("duration", 0.0) or 0.0)
        expected_len = int(round(nominal_dur * target_sr)) if nominal_dur > 0 else 0

        raw = load_audio_samples(path, target_sr)
        if expected_len > 0:
            if len(raw) < expected_len:
                padded = np.zeros(expected_len, dtype=np.float32)
                padded[:len(raw)] = raw
                segments.append(padded)
            else:
                segments.append(raw[:expected_len])
        else:
            segments.append(raw)

    if not segments:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(segments)


def extract_audio_features(
    audio: np.ndarray,
    time_sec: float,
    window_sec: float = 0.05,
    sample_rate: int = ANALYSIS_SR,
    num_bins: int = 32,
) -> Tuple[np.ndarray, float]:
    """
    Extract frequency band magnitudes and RMS amplitude at a given time.
    Returns:
        (band_magnitudes, rms_amplitude)
    """
    if len(audio) == 0 or time_sec < 0:
        return np.zeros(num_bins, dtype=np.float32), 0.0

    center_idx = int(round(time_sec * sample_rate))
    half_win = int(round((window_sec / 2.0) * sample_rate))
    start_idx = max(0, center_idx - half_win)
    end_idx = min(len(audio), center_idx + half_win)

    if start_idx >= end_idx:
        return np.zeros(num_bins, dtype=np.float32), 0.0

    chunk = audio[start_idx:end_idx]
    if len(chunk) < 64:
        return np.zeros(num_bins, dtype=np.float32), 0.0

    rms = float(np.sqrt(np.mean(chunk ** 2)))

    # Windowed FFT
    win = np.hanning(len(chunk))
    fft_vals = np.abs(np.fft.rfft(chunk * win))
    freqs = np.fft.rfftfreq(len(chunk), d=1.0 / sample_rate)

    # Group into logarithmic frequency bins between 50 Hz and 8000 Hz
    min_freq = 50.0
    max_freq = min(8000.0, sample_rate / 2.0)
    log_edges = np.geomspace(min_freq, max_freq, num_bins + 1)

    bins = np.zeros(num_bins, dtype=np.float32)
    for b in range(num_bins):
        low, high = log_edges[b], log_edges[b + 1]
        mask = (freqs >= low) & (freqs < high)
        if np.any(mask):
            bins[b] = np.mean(fft_vals[mask])
        else:
            # Interpolate from adjacent
            idx = np.searchsorted(freqs, (low + high) / 2.0)
            idx = min(len(fft_vals) - 1, max(0, idx))
            bins[b] = fft_vals[idx]

    # Normalize bins to a reasonable baseline
    max_b = np.max(bins)
    if max_b > 1e-6:
        bins = bins / (max_b + 1e-4) * min(1.0, rms * 15.0)
    else:
        bins.fill(0.0)

    return bins, rms


def render_visualizer_frame(
    canvas_w: int,
    canvas_h: int,
    audio: np.ndarray,
    time_sec: float,
    settings: dict,
) -> np.ndarray:
    """
    Render a single transparent RGBA frame containing the audio visualizer.
    Returns:
        np.ndarray of shape (canvas_h, canvas_w, 4) in uint8 RGBA format.
    """
    frame = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)

    enabled = bool(settings.get("visualizer_enabled", False))
    if not enabled:
        return frame

    style = str(settings.get("visualizer_style", "Standard (Horizontal Bars)")).strip()
    color_rgb = _hex_or_tuple_to_rgb(settings.get("visualizer_color", (56, 189, 248)))
    color_rgba = (int(color_rgb[0]), int(color_rgb[1]), int(color_rgb[2]), 255)

    direction = str(settings.get("visualizer_direction", "Bidirectional")).strip().capitalize()
    if direction not in ("Upward", "Downward", "Bidirectional"):
        direction = "Bidirectional"

    elem_count = max(4, min(256, int(settings.get("visualizer_element_count", 32) or 32)))
    elem_size = max(1, min(100, int(settings.get("visualizer_element_size", 8) or 8)))
    vis_width = max(50, min(canvas_w, int(settings.get("visualizer_width", 800) or 800)))

    # X position: if visualizer_x is 0, center horizontally
    x_offset = int(settings.get("visualizer_x", 0) or 0)
    start_x = int((canvas_w - vis_width) / 2) + x_offset

    # Y position: default to 80% down the screen
    default_y = int(canvas_h * 0.78)
    base_y = int(settings.get("visualizer_y", default_y) or default_y)
    base_y = max(10, min(canvas_h - 10, base_y))

    amplitude = max(0.1, min(10.0, float(settings.get("visualizer_amplitude", 1.0) or 1.0)))

    # Extract audio data
    bins, rms = extract_audio_features(audio, time_sec, num_bins=elem_count)

    # OpenCV uses BGRA by default when drawing on arrays
    b_col = int(color_rgb[2])
    g_col = int(color_rgb[1])
    r_col = int(color_rgb[0])
    draw_color = (b_col, g_col, r_col, 255)

    # Frame is RGBA: we draw with R, G, B in slots 0, 1, 2 and A in slot 3
    # We will construct in a temporary uint8 BGRA buffer and swap channels, or draw directly
    cv_color = (int(color_rgb[0]), int(color_rgb[1]), int(color_rgb[2]), 255)

    if "heartbeat" in style.lower():
        # -------------------------------------------------------------
        # Style: Heartbeat (Audio-reactive waveform / pulse)
        # -------------------------------------------------------------
        # Generate a pulse line across vis_width with elem_count points
        points: List[Tuple[int, int]] = []
        max_height = int(canvas_h * 0.22 * amplitude)
        max_height = max(10, min(canvas_h // 2, max_height))

        # Modulate waveform using audio envelope + frequency energy
        energy = min(1.0, rms * 10.0 * amplitude)

        for i in range(elem_count):
            frac = i / max(1, elem_count - 1)
            px = int(start_x + frac * vis_width)

            # Center pulse shape (EKG heartbeat envelope centered at frac=0.5)
            dist_from_center = abs(frac - 0.5) * 2.0  # 0 at center, 1 at edges
            envelope = math.exp(-6.0 * (dist_from_center ** 2))

            # Audio-driven oscillations: combination of frequency bin and envelope
            bin_idx = min(len(bins) - 1, int(i % len(bins)))
            sample_val = bins[bin_idx] if len(bins) > 0 else 0.0

            # Dynamic wave displacement
            wave_mod = math.sin(frac * math.pi * 8.0 + time_sec * 6.0)
            displacement = (sample_val * 0.7 + energy * 0.3) * envelope * wave_mod * max_height

            # Subtle baseline pulse during silence
            if energy < 0.02:
                displacement = math.sin(frac * math.pi * 4.0) * 2.0 * envelope

            if direction == "Upward":
                py = int(base_y - abs(displacement))
            elif direction == "Downward":
                py = int(base_y + abs(displacement))
            else:  # Bidirectional
                py = int(base_y - displacement)

            py = max(0, min(canvas_h - 1, py))
            points.append((px, py))

        if len(points) >= 2:
            pts_arr = np.array(points, dtype=np.int32).reshape((-1, 1, 2))
            thickness = max(1, elem_size)
            cv2.polylines(frame, [pts_arr], isClosed=False, color=cv_color, thickness=thickness, lineType=cv2.LINE_AA)

    else:
        # -------------------------------------------------------------
        # Style: Standard (Horizontal Frequency Bars)
        # -------------------------------------------------------------
        max_bar_h = int(canvas_h * 0.25 * amplitude)
        max_bar_h = max(10, min(canvas_h // 2, max_bar_h))

        bar_slot = vis_width / float(elem_count)
        bar_w = max(1, min(int(bar_slot) - 2, elem_size))

        for i in range(elem_count):
            mag = float(bins[i]) if i < len(bins) else 0.0
            # Height responds to audio magnitude scaled by amplitude
            bar_h = int(mag * max_bar_h)
            # Minimum baseline dot/bar of 2px for visual continuity
            bar_h = max(2, bar_h)

            cx = int(start_x + i * bar_slot + (bar_slot - bar_w) / 2.0)
            x1 = cx
            x2 = cx + bar_w

            if direction == "Upward":
                y1 = base_y - bar_h
                y2 = base_y
            elif direction == "Downward":
                y1 = base_y
                y2 = base_y + bar_h
            else:  # Bidirectional
                half = bar_h // 2
                y1 = base_y - half
                y2 = base_y + half

            y1 = max(0, min(canvas_h - 1, y1))
            y2 = max(0, min(canvas_h - 1, y2))
            if y2 < y1:
                y1, y2 = y2, y1

            cv2.rectangle(frame, (x1, y1), (x2, y2), cv_color, -1)

    return frame


def render_visualizer_preview_image(
    canvas_w: int,
    canvas_h: int,
    project: dict,
    preview_time: float = 0.0,
) -> Optional[Image.Image]:
    """
    Generate a PIL RGBA Image of the visualizer for GUI preview overlay.
    Returns None if visualizer is disabled.
    """
    if not project.get("visualizer_enabled"):
        return None

    tracks = project.get("tracks", [])
    intro_dur = float(project.get("intro_duration", 3.0) or 3.0) if project.get("intro_enabled") else 0.0
    audio = build_timeline_audio(tracks, intro_duration=intro_dur)

    frame = render_visualizer_frame(
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        audio=audio,
        time_sec=preview_time,
        settings=project,
    )
    return Image.fromarray(frame, mode="RGBA")


def generate_visualizer_video(
    project: dict,
    total_duration: float,
    canvas_w: int,
    canvas_h: int,
    output_path: Path,
    fps: int = 30,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Path:
    """
    Stream-generate a transparent QuickTime Animation (qtrle) or ProRes video
    containing the visualizer over the exact duration of the timeline.
    """
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tracks = project.get("tracks", [])
    intro_dur = float(project.get("intro_duration", 3.0) or 3.0) if project.get("intro_enabled") else 0.0
    audio = build_timeline_audio(tracks, intro_duration=intro_dur)

    total_frames = max(1, int(math.ceil(total_duration * fps)))

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo",
        "-pix_fmt", "rgba",
        "-s", f"{canvas_w}x{canvas_h}",
        "-r", str(fps),
        "-i", "pipe:0",
        "-c:v", "qtrle",
        "-r", str(fps),
        str(output_path),
    ]

    if progress_callback:
        progress_callback(f"Generating audio visualizer ({total_frames} frames)…")

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    try:
        assert proc.stdin is not None
        for f in range(total_frames):
            t_sec = f / float(fps)
            rgba_frame = render_visualizer_frame(
                canvas_w=canvas_w,
                canvas_h=canvas_h,
                audio=audio,
                time_sec=t_sec,
                settings=project,
            )
            proc.stdin.write(rgba_frame.tobytes())

            if progress_callback and (f % (fps * 5) == 0):
                pct = int((f / total_frames) * 100)
                progress_callback(f"Rendering visualizer: {pct}% ({f}/{total_frames} frames)")

        proc.stdin.close()
        proc.wait()
        if proc.returncode != 0:
            err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else "Unknown error"
            raise RuntimeError(f"FFmpeg visualizer generation failed: {err}")
    except Exception as exc:
        proc.kill()
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        raise exc

    return output_path
