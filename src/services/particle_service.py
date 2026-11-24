"""
Particle simulation and video generation service for Nasheed Studio.

Supports:
- Style 1: "Drifting Flecks" (horizontal drifting flecks/specks with gentle natural float, inspired by client reference).
- Style 2: "Floating Orbs" (vertical atmospheric float with sinusoidal sway).
- Layering: "Below Text" (under typography/tracklist) vs "Above Text" (over all layers).
- Seamless mathematical looping for zero-overhead FFmpeg export.
"""

from __future__ import annotations

import math
import os
import random
import subprocess
from pathlib import Path
from typing import List, Tuple, Union
from PIL import Image, ImageDraw

STYLE_DRIFTING_FLECKS = "Drifting Flecks"
STYLE_FLOATING_ORBS = "Floating Orbs"

LAYER_BELOW_TEXT = "Below Text"
LAYER_ABOVE_TEXT = "Above Text"

PARTICLE_STYLES = [STYLE_DRIFTING_FLECKS, STYLE_FLOATING_ORBS]
PARTICLE_LAYERS = [LAYER_BELOW_TEXT, LAYER_ABOVE_TEXT]


def _speed_multiplier(speed_level: int) -> float:
    # 1: 0.5x, 2: 1.0x, 3: 1.6x, 4: 2.4x, 5: 3.5x
    multipliers = {1: 0.5, 2: 1.0, 3: 1.6, 4: 2.4, 5: 3.5}
    return multipliers.get(max(1, min(5, int(speed_level))), 1.0)


def generate_particle_loop_video(
    output_path: Union[str, Path],
    width: int,
    height: int,
    fps: int = 30,
    duration: float = 6.0,
    style: str = STYLE_DRIFTING_FLECKS,
    quantity: int = 80,
    color: Union[Tuple[int, int, int], str] = (56, 189, 248),
    speed: int = 2,
    ffmpeg_bin: str = "ffmpeg",
) -> Path:
    """
    Generate a seamless looping transparent QuickTime Animation (qtrle) video file.
    The video has full alpha transparency and loops mathematically without seam artifacts.
    """
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Parse color
    if isinstance(color, str):
        c_str = color.lstrip("#")
        if len(c_str) == 6:
            r, g, b = int(c_str[0:2], 16), int(c_str[2:4], 16), int(c_str[4:6], 16)
        else:
            r, g, b = 56, 189, 248
    elif isinstance(color, (tuple, list)) and len(color) >= 3:
        r, g, b = int(color[0]), int(color[1]), int(color[2])
    else:
        r, g, b = 56, 189, 248

    num_frames = int(round(fps * duration))
    if num_frames < 30:
        num_frames = 30
        duration = num_frames / float(fps)

    res_scale = height / 1080.0
    sm = _speed_multiplier(speed)
    count = max(10, min(300, int(quantity)))

    # Seed deterministic pseudo-random sequence for repeatability per project settings
    rng = random.Random(42 + count + speed)

    particles = []
    is_flecks = (style == STYLE_DRIFTING_FLECKS or "fleck" in str(style).lower())

    if is_flecks:
        # Drifting Flecks: Horizontal drift with subtle vertical undulating wave
        for _ in range(count):
            depth = rng.uniform(0.35, 1.0)
            radius = max(1.0, (1.2 + depth * 1.8) * res_scale)
            # Integer screen widths per loop (1, 2, or 3) scaled by speed factor
            k_choices = [1, 2] if sm <= 1.0 else ([1, 2, 3] if sm <= 2.0 else [2, 3, 4])
            k = rng.choice(k_choices)
            vx = k * width / duration
            m = rng.choice([1, 2, 3])  # integer wave cycles per loop
            A = rng.uniform(2.5, 7.5) * res_scale
            x0 = rng.uniform(0, width)
            y0 = rng.uniform(height * 0.05, height * 0.95)
            alpha = int(round(rng.uniform(120, 245) * (0.4 + 0.6 * depth)))
            particles.append({
                "x0": x0, "y0": y0, "vx": vx, "m": m, "A": A,
                "radius": radius, "alpha": alpha
            })
    else:
        # Floating Orbs: Vertical float with sinusoidal sway
        for _ in range(count):
            depth = rng.uniform(0.3, 1.0)
            radius = max(1.5, (1.8 + depth * 3.2) * res_scale)
            k_choices = [1, 2] if sm <= 1.0 else ([1, 2, 3] if sm <= 2.0 else [2, 3, 4])
            k = rng.choice(k_choices)
            vy = k * height / duration
            m = rng.choice([1, 2, 3])
            A = rng.uniform(4.0, 14.0) * res_scale
            x0 = rng.uniform(0, width)
            y0 = rng.uniform(0, height)
            alpha = int(round(rng.uniform(100, 225) * (0.35 + 0.65 * depth)))
            particles.append({
                "x0": x0, "y0": y0, "vy": vy, "m": m, "A": A,
                "radius": radius, "alpha": alpha
            })

    cmd = [
        ffmpeg_bin, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "rgba",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "qtrle",
        "-pix_fmt", "argb",
        str(out_file),
    ]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    two_pi = 2.0 * math.pi

    for frame_idx in range(num_frames):
        t = frame_idx / float(fps)
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if is_flecks:
            for p in particles:
                cur_x = (p["x0"] + p["vx"] * t) % width
                cur_y = p["y0"] + p["A"] * math.sin(two_pi * p["m"] * t / duration)
                r_val = p["radius"]
                draw.ellipse(
                    [cur_x - r_val, cur_y - r_val, cur_x + r_val, cur_y + r_val],
                    fill=(r, g, b, p["alpha"]),
                )
        else:
            for p in particles:
                cur_y = (p["y0"] + p["vy"] * t) % height
                cur_x = (p["x0"] + p["A"] * math.sin(two_pi * p["m"] * t / duration)) % width
                r_val = p["radius"]
                draw.ellipse(
                    [cur_x - r_val, cur_y - r_val, cur_x + r_val, cur_y + r_val],
                    fill=(r, g, b, p["alpha"]),
                )

        proc.stdin.write(img.tobytes())

    proc.stdin.close()
    _, stderr_bytes = proc.communicate()

    if proc.returncode != 0:
        err_msg = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else "Unknown error"
        raise RuntimeError(f"FFmpeg particle generation failed: {err_msg}")

    return out_file
