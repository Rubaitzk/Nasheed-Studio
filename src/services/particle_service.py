"""
Particle simulation and video generation service for Nasheed Studio.

Supports:
- Style 1: "Drifting Flecks" (horizontal drifting flecks/specks with gentle natural float, inspired by client reference).
- Style 2: "Floating Orbs" (vertical atmospheric float with sinusoidal sway).
- Style 3: "Light Glints" (thin white glint/flick slivers drifting diagonally with pulsating flash).
- Layering: "Below Text" (under typography/tracklist) vs "Above Text" (over all layers).
- Seamless mathematical looping for zero-overhead FFmpeg export.
"""

from __future__ import annotations

import math
import os
import random
import subprocess
from pathlib import Path
from typing import Any, List, Tuple, Union
from PIL import Image, ImageDraw

STYLE_WIND_STREAKS = "Wind Streaks"
STYLE_DRIFTING_FLECKS = "Drifting Flecks"
STYLE_FLOATING_ORBS = "Floating Orbs"
STYLE_LIGHT_GLINTS = "Light Glints"
STYLE_TWINKLE_STARS = "Twinkle Stars"
STYLE_BOKEH_RINGS = "Bokeh Rings"
STYLE_CRESCENTS_AND_STARS = "Crescents & Stars"
STYLE_EIGHT_POINT_STARS = "Eight-Point Stars"

LAYER_BELOW_TEXT = "Below Text"
LAYER_ABOVE_TEXT = "Above Text"

PARTICLE_STYLES = [
    STYLE_WIND_STREAKS,
    STYLE_DRIFTING_FLECKS,
    STYLE_FLOATING_ORBS,
    STYLE_LIGHT_GLINTS,
    STYLE_TWINKLE_STARS,
    STYLE_BOKEH_RINGS,
    STYLE_CRESCENTS_AND_STARS,
    STYLE_EIGHT_POINT_STARS,
]
PARTICLE_LAYERS = [LAYER_BELOW_TEXT, LAYER_ABOVE_TEXT]


def lens_polygon(
    cx: float,
    cy: float,
    length: float,
    width: float,
    angle_deg: float,
    n: int = 14,
) -> List[Tuple[float, float]]:
    """
    Generate points of a pointed lens/sliver shape.
    Two mirrored curves with half_width(u) = (width / 2) * (1 - |u|)**0.8 for u in [-1, 1],
    rotated by angle_deg about (cx, cy). Both preview and export use the same helper so the shapes match.
    """
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    half_len = length / 2.0
    half_w = width / 2.0

    pts: List[Tuple[float, float]] = []
    # Top curve: u from -1.0 to 1.0
    for i in range(n + 1):
        u = -1.0 + 2.0 * i / n
        w = half_w * ((1.0 - abs(u)) ** 0.8)
        x_loc = u * half_len
        y_loc = w
        px = cx + x_loc * cos_a - y_loc * sin_a
        py = cy + x_loc * sin_a + y_loc * cos_a
        pts.append((px, py))

    # Bottom curve: u from 1.0 back down to -1.0 (skipping endpoints to prevent duplicate vertices)
    for i in range(1, n):
        u = 1.0 - 2.0 * i / n
        w = -half_w * ((1.0 - abs(u)) ** 0.8)
        x_loc = u * half_len
        y_loc = w
        px = cx + x_loc * cos_a - y_loc * sin_a
        py = cy + x_loc * sin_a + y_loc * cos_a
        pts.append((px, py))

    return pts


def star_4point_polygon(
    cx: float,
    cy: float,
    r_outer: float,
    r_inner: Optional[float] = None,
    angle_deg: float = 0.0,
) -> List[Tuple[float, float]]:
    """
    Generate points of a 4-point star with long thin arms.
    """
    if r_inner is None:
        r_inner = r_outer * 0.18
    pts: List[Tuple[float, float]] = []
    base_rad = math.radians(angle_deg)
    for i in range(8):
        angle = base_rad + i * (math.pi / 4.0)
        r = r_outer if (i % 2 == 0) else r_inner
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts


def crescent_polygon(
    cx: float,
    cy: float,
    r_outer: float,
    angle_deg: float = 25.0,
    n: int = 12,
) -> List[Tuple[float, float]]:
    """
    Generate points of a crescent moon shape.
    Outer arc with radius r_outer, inner arc offset to form a pointed crescent.
    """
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    pts: List[Tuple[float, float]] = []
    # Outer arc
    for i in range(n + 1):
        theta = -math.pi / 2.0 + (math.pi * i / n)
        x_loc = r_outer * math.cos(theta)
        y_loc = r_outer * math.sin(theta)
        px = cx + x_loc * cos_a - y_loc * sin_a
        py = cy + x_loc * sin_a + y_loc * cos_a
        pts.append((px, py))
    # Inner arc (offset toward positive x_loc)
    r_inner = r_outer * 0.85
    ox = r_outer * 0.45
    for i in range(1, n):
        theta = math.pi / 2.0 - (math.pi * i / n)
        x_loc = ox + r_inner * math.cos(theta)
        y_loc = r_inner * math.sin(theta)
        px = cx + x_loc * cos_a - y_loc * sin_a
        py = cy + x_loc * sin_a + y_loc * cos_a
        pts.append((px, py))
    return pts


def star_5point_polygon(
    cx: float,
    cy: float,
    r_outer: float,
    r_inner: Optional[float] = None,
    angle_deg: float = 0.0,
) -> List[Tuple[float, float]]:
    """
    Generate points of a 5-point star.
    """
    if r_inner is None:
        r_inner = r_outer * 0.42
    pts: List[Tuple[float, float]] = []
    base_rad = math.radians(angle_deg - 90.0)
    for i in range(10):
        angle = base_rad + i * (math.pi / 5.0)
        r = r_outer if (i % 2 == 0) else r_inner
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts


def star_8point_polygon(
    cx: float,
    cy: float,
    r_outer: float,
    r_inner: Optional[float] = None,
    angle_deg: float = 0.0,
) -> List[Tuple[float, float]]:
    """
    Generate points of an 8-point Islamic star (Rub el Hizb: two overlaid rotated squares).
    """
    if r_inner is None:
        r_inner = r_outer * 0.76536686
    pts: List[Tuple[float, float]] = []
    base_rad = math.radians(angle_deg)
    for i in range(16):
        angle = base_rad + i * (math.pi / 8.0)
        r = r_outer if (i % 2 == 0) else r_inner
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts


def glint_state(p: Union[dict, Any], t: float, duration: float) -> Tuple[float, float, float]:
    """
    Compute position (x, y) and alpha_factor for a glint particle at time t.
    Returns (x, y, alpha_factor) where alpha_factor is in [0.0, 1.0].
    Seamlessly loops over duration with period matching integer n flashes and integer drift.
    """
    n = p["n"] if isinstance(p, dict) else getattr(p, "n", 2)
    phase_init = p["phase"] if isinstance(p, dict) else getattr(p, "phase", 0.0)
    val = (t / duration) * n + phase_init
    phase = val % 1.0
    cycle = math.floor(val)
    alpha_factor = math.sin(math.pi * phase) ** 2

    positions = p["positions"] if isinstance(p, dict) else getattr(p, "positions")
    base_pos = positions[cycle % n]
    vx = p.get("vx", 0.0) if isinstance(p, dict) else getattr(p, "vx", 0.0)
    vy = p.get("vy", 0.0) if isinstance(p, dict) else getattr(p, "vy", 0.0)
    w = p.get("width", 1920) if isinstance(p, dict) else getattr(p, "width", 1920)
    h = p.get("height", 1080) if isinstance(p, dict) else getattr(p, "height", 1080)

    x = (base_pos[0] + vx * t) % w
    y = (base_pos[1] + vy * t) % h
    return x, y, alpha_factor


def capsule_polygon(
    cx: float,
    cy: float,
    length: float,
    thickness: float,
    angle_rad: float,
    n_arc: int = 8,
) -> List[Tuple[float, float]]:
    """
    Generate vertices of a solid capsule (rectangle with semicircular caps at both ends).
    """
    half_t = max(0.4, thickness / 2.0)
    half_l = max(0.1, (length - thickness) / 2.0)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    pts: List[Tuple[float, float]] = []
    # Cap 2 (positive x local, from -pi/2 to +pi/2)
    for i in range(n_arc + 1):
        theta = -math.pi / 2.0 + math.pi * i / n_arc
        lx = half_l + half_t * math.cos(theta)
        ly = half_t * math.sin(theta)
        px = cx + lx * cos_a - ly * sin_a
        py = cy + lx * sin_a + ly * cos_a
        pts.append((px, py))

    # Cap 1 (negative x local, from +pi/2 to 3*pi/2)
    for i in range(n_arc + 1):
        theta = math.pi / 2.0 + math.pi * i / n_arc
        lx = -half_l + half_t * math.cos(theta)
        ly = half_t * math.sin(theta)
        px = cx + lx * cos_a - ly * sin_a
        py = cy + lx * sin_a + ly * cos_a
        pts.append((px, py))

    return pts


def wind_streak_state(p: Union[dict, Any], t: float) -> Tuple[float, float, float, float]:
    """
    Compute (x, y, alpha, rot) for a Wind Streaks particle at time t.
    Returns:
        x (float): current center x
        y (float): current center y
        alpha (float): constant per-particle alpha [0.6, 0.9]
        rot (float): constant rotation angle = math.atan2(vy, vx)
    """
    t_life = p["t_life"] if isinstance(p, dict) else getattr(p, "t_life")
    t_phase = p["phase"] if isinstance(p, dict) else getattr(p, "phase")
    sx = p["spawn_x"] if isinstance(p, dict) else getattr(p, "spawn_x")
    sy = p["spawn_y"] if isinstance(p, dict) else getattr(p, "spawn_y")
    vx = p["vx"] if isinstance(p, dict) else getattr(p, "vx")
    vy = p["vy"] if isinstance(p, dict) else getattr(p, "vy")
    alpha = p["alpha"] if isinstance(p, dict) else getattr(p, "base_alpha")

    tau = (t_phase + t) % t_life
    cur_x = sx + vx * tau
    cur_y = sy + vy * tau
    rot = math.atan2(vy, vx)
    return cur_x, cur_y, alpha, rot


def create_wind_streak_particles(
    count: int,
    width: float,
    height: float,
    angle_deg: float = 225.0,
    speed_level: int = 2,
    size_factor: float = 1.0,
    seed: Optional[int] = None,
) -> List[dict]:
    """
    Deterministic particle generator for Wind Streaks.
    Used by both preview (ParticleOverlayWidget) and render (generate_particle_loop_video)
    to guarantee identical behavior and resolution-independent parity.
    """
    res_scale = max(10.0, height) / 1080.0
    geom_scale = res_scale * size_factor
    sm = _speed_multiplier(speed_level)

    rng_seed = seed if seed is not None else (4242 + int(count) + int(speed_level) + int(angle_deg))
    rng = random.Random(rng_seed)

    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    # Reference speed magnitude at 1080p: ~254.55844 px/s
    # At default 225 deg: vx = -180.0, vy = +180.0 px/s with sm=1.0
    speed_mag_ref = 254.558441227 * sm
    base_vx = speed_mag_ref * cos_a
    base_vy = -speed_mag_ref * sin_a

    margin = 50.0 * res_scale
    w_box = width + 2.0 * margin
    h_box = height + 2.0 * margin

    particles = []
    for _ in range(count):
        speed_var = rng.uniform(0.85, 1.15)
        vx = base_vx * speed_var * res_scale
        vy = base_vy * speed_var * res_scale

        if vx <= 0 and vy >= 0:
            l_spawn = w_box + h_box
            u = rng.uniform(0.0, l_spawn)
            if u < w_box:
                sx = -margin + u
                sy = -margin
            else:
                sx = width + margin
                sy = -margin + (u - w_box)
            tx = (-margin - sx) / vx if vx < 0 else 1e9
            ty = (height + margin - sy) / vy if vy > 0 else 1e9
            t_life = max(0.2, min(tx, ty))
        else:
            sx_edge = (width + margin) if vx < 0 else -margin
            sy_edge = -margin if vy > 0 else (height + margin)
            cx_edge = -margin if vx < 0 else (width + margin)
            cy_edge = (height + margin) if vy > 0 else -margin

            l_spawn = w_box + h_box
            u = rng.uniform(0.0, l_spawn)
            if u < w_box:
                sx = -margin + u
                sy = sy_edge
            else:
                sx = sx_edge
                sy = -margin + (u - w_box)
            tx = (cx_edge - sx) / vx if abs(vx) > 1e-4 else 1e9
            ty = (cy_edge - sy) / vy if abs(vy) > 1e-4 else 1e9
            t_life = max(0.2, min(tx, ty))

        t_phase = rng.uniform(0.0, t_life)

        base_len = rng.uniform(6.0, 14.0)
        base_thick = rng.uniform(1.5, 2.0)
        length = max(1.0, base_len * geom_scale)
        thickness = max(0.8, base_thick * geom_scale)

        alpha = rng.uniform(0.6, 0.9)
        color_rgb = rng.choice([(255, 255, 255), (224, 224, 224)])
        rot = math.atan2(vy, vx)

        particles.append({
            "spawn_x": sx,
            "spawn_y": sy,
            "vx": vx,
            "vy": vy,
            "t_life": t_life,
            "phase": t_phase,
            "length": length,
            "thickness": thickness,
            "base_length": base_len,
            "base_thickness": base_thick,
            "alpha": alpha,
            "color_rgb": color_rgb,
            "rot": rot,
            "angle_deg": math.degrees(rot),
        })

    return particles


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
    style: str = STYLE_WIND_STREAKS,
    quantity: int = 80,
    color: Union[Tuple[int, int, int], str] = (56, 189, 248),
    speed: int = 2,
    size: int = 100,
    angle: float = 225.0,
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
    size_val = max(50, min(300, int(size)))
    geom_scale = res_scale * (size_val / 100.0)
    sm = _speed_multiplier(speed)
    count = max(10, min(300, int(quantity)))

    # Seed deterministic pseudo-random sequence for repeatability per project settings
    rng = random.Random(42 + count + speed)

    particles = []
    is_wind = (style == STYLE_WIND_STREAKS or "wind" in str(style).lower())
    is_glints = (style == STYLE_LIGHT_GLINTS or "glint" in str(style).lower())
    is_stars = (style == STYLE_TWINKLE_STARS or "twinkle" in str(style).lower())
    is_bokeh = (style == STYLE_BOKEH_RINGS or "bokeh" in str(style).lower())
    is_crescents = (style == STYLE_CRESCENTS_AND_STARS or "crescent" in str(style).lower())
    is_eight_stars = (style == STYLE_EIGHT_POINT_STARS or "eight" in str(style).lower())
    is_flecks = (style == STYLE_DRIFTING_FLECKS or "fleck" in str(style).lower())

    base_sprites = {}
    alpha_cache = {}

    if is_wind:
        particles = create_wind_streak_particles(
            count=count,
            width=width,
            height=height,
            angle_deg=angle,
            speed_level=speed,
            size_factor=size_val / 100.0,
            seed=42 + count + speed + int(angle),
        )
    elif is_glints:
        # Light Glints: thin tapered white sliver / flick drifting slowly with flashing glint
        r_out = int(round(r * 0.4 + 255 * 0.6))
        g_out = int(round(g * 0.4 + 255 * 0.6))
        b_out = int(round(b * 0.4 + 255 * 0.6))

        kx_choices = [1] if sm <= 1.0 else ([1, 2] if sm <= 3.0 else [2, 3])
        ky_choices = [-1] if sm <= 1.0 else ([-2, -1] if sm <= 3.0 else [-3, -2])

        for _ in range(count):
            depth = rng.uniform(0.35, 1.0)
            length = rng.uniform(14.0, 48.0) * geom_scale
            w_ratio = rng.uniform(7.0, 11.0)
            g_width = length / w_ratio
            angle = -60.0 + rng.uniform(-14.0, 14.0)
            n_val = rng.choice([2, 3, 4])
            phase = rng.uniform(0.0, 1.0)
            peak_alpha = int(round(rng.uniform(150, 255) * (0.5 + 0.5 * depth)))

            positions = [
                (rng.uniform(0, width), rng.uniform(0, height))
                for _ in range(n_val)
            ]
            kx = rng.choice(kx_choices)
            ky = rng.choice(ky_choices)
            vx = kx * width / duration
            vy = ky * height / duration

            # Quantize length and angle into buckets to maximize sprite reuse
            len_b = int(round(length / 2.0)) * 2
            ang_b = int(round(angle / 2.0)) * 2
            b_key = ("glint", len_b, ang_b)

            if b_key not in base_sprites:
                b_width = len_b / 9.0
                pad = int(math.ceil(max(len_b, b_width))) + 8
                SS = 4
                im_ss = Image.new("RGBA", (pad * SS, pad * SS), (0, 0, 0, 0))
                d_ss = ImageDraw.Draw(im_ss)
                cx_ss = pad * SS / 2.0
                cy_ss = pad * SS / 2.0
                p_out = lens_polygon(cx_ss, cy_ss, len_b * SS, b_width * SS, ang_b)
                d_ss.polygon(p_out, fill=(r_out, g_out, b_out, 255))
                p_in = lens_polygon(cx_ss, cy_ss, len_b * SS * 0.65, b_width * SS * 0.45, ang_b)
                d_ss.polygon(p_in, fill=(255, 255, 255, 255))
                spr = im_ss.resize((pad, pad), Image.Resampling.LANCZOS)
                base_sprites[b_key] = (spr, pad)

            particles.append({
                "n": n_val,
                "phase": phase,
                "positions": positions,
                "vx": vx,
                "vy": vy,
                "width": width,
                "height": height,
                "peak_alpha": peak_alpha,
                "b_key": b_key,
                "length": length,
                "glint_width": g_width,
                "angle_deg": angle,
            })
    elif is_stars:
        # Twinkle Stars: 4-point diamond star with long thin arms flashing in and out
        r_out = int(round(r * 0.4 + 255 * 0.6))
        g_out = int(round(g * 0.4 + 255 * 0.6))
        b_out = int(round(b * 0.4 + 255 * 0.6))

        kx_choices = [1] if sm <= 1.0 else ([1, 2] if sm <= 3.0 else [2, 3])
        ky_choices = [-1, 0, 1]

        for _ in range(count):
            depth = rng.uniform(0.35, 1.0)
            radius = rng.uniform(8.0, 24.0) * geom_scale
            angle = rng.uniform(0.0, 45.0)
            n_val = rng.choice([2, 3, 4])
            phase = rng.uniform(0.0, 1.0)
            peak_alpha = int(round(rng.uniform(150, 255) * (0.5 + 0.5 * depth)))

            positions = [
                (rng.uniform(0, width), rng.uniform(0, height))
                for _ in range(n_val)
            ]
            kx = rng.choice(kx_choices)
            ky = rng.choice(ky_choices)
            vx = kx * width / duration
            vy = ky * height / duration

            r_b = int(round(radius / 2.0)) * 2
            ang_b = int(round(angle / 5.0)) * 5
            b_key = ("star", r_b, ang_b)

            if b_key not in base_sprites:
                pad = r_b * 2 + 10
                SS = 4
                im_ss = Image.new("RGBA", (pad * SS, pad * SS), (0, 0, 0, 0))
                d_ss = ImageDraw.Draw(im_ss)
                cx_ss = pad * SS / 2.0
                cy_ss = pad * SS / 2.0
                p_out = star_4point_polygon(cx_ss, cy_ss, r_b * SS, r_b * SS * 0.18, ang_b)
                d_ss.polygon(p_out, fill=(r_out, g_out, b_out, 255))
                p_in = star_4point_polygon(cx_ss, cy_ss, r_b * SS * 0.45, r_b * SS * 0.10, ang_b)
                d_ss.polygon(p_in, fill=(255, 255, 255, 255))
                spr = im_ss.resize((pad, pad), Image.Resampling.LANCZOS)
                base_sprites[b_key] = (spr, pad)

            particles.append({
                "n": n_val,
                "phase": phase,
                "positions": positions,
                "vx": vx,
                "vy": vy,
                "width": width,
                "height": height,
                "peak_alpha": peak_alpha,
                "b_key": b_key,
                "radius": radius,
                "angle_deg": angle,
            })
    elif is_bokeh:
        # Bokeh Rings: soft translucent circle with a brighter edge ring, larger and slower
        r_edge = int(round(r * 0.3 + 255 * 0.7))
        g_edge = int(round(g * 0.3 + 255 * 0.7))
        b_edge = int(round(b * 0.3 + 255 * 0.7))

        for _ in range(count):
            depth = rng.uniform(0.35, 1.0)
            radius = rng.uniform(6.0, 22.0) * geom_scale
            k_choices = [1] if sm <= 1.5 else [1, 2]
            k = rng.choice(k_choices)
            vy = k * height / duration
            m = rng.choice([1, 2])
            A = rng.uniform(5.0, 16.0) * res_scale
            x0 = rng.uniform(0, width)
            y0 = rng.uniform(0, height)

            r_b = int(round(radius / 2.0)) * 2
            b_key = ("bokeh", r_b)

            if b_key not in base_sprites:
                pad = r_b * 2 + 10
                SS = 4
                im_ss = Image.new("RGBA", (pad * SS, pad * SS), (0, 0, 0, 0))
                d_ss = ImageDraw.Draw(im_ss)
                cx_ss = pad * SS / 2.0
                cy_ss = pad * SS / 2.0
                rb_ss = r_b * SS
                # Soft translucent fill
                d_ss.ellipse(
                    [cx_ss - rb_ss, cy_ss - rb_ss, cx_ss + rb_ss, cy_ss + rb_ss],
                    fill=(r, g, b, 55),
                )
                # Brighter edge ring
                d_ss.ellipse(
                    [cx_ss - rb_ss, cy_ss - rb_ss, cx_ss + rb_ss, cy_ss + rb_ss],
                    outline=(r_edge, g_edge, b_edge, 215),
                    width=max(1, int(1.8 * SS)),
                )
                spr = im_ss.resize((pad, pad), Image.Resampling.LANCZOS)
                base_sprites[b_key] = (spr, pad)

            particles.append({
                "x0": x0, "y0": y0, "vy": vy, "m": m, "A": A,
                "radius": radius, "b_key": b_key,
            })
    elif is_crescents:
        # Crescents & Stars: small crescent moons and 5-point stars, sparse and slow
        r_out = int(round(r * 0.35 + 255 * 0.65))
        g_out = int(round(g * 0.35 + 255 * 0.65))
        b_out = int(round(b * 0.35 + 255 * 0.65))
        cresc_count = max(8, int(count * 0.7))

        for i in range(cresc_count):
            depth = rng.uniform(0.35, 1.0)
            is_cresc = (i % 2 == 0)
            radius = (rng.uniform(7.0, 15.0) if is_cresc else rng.uniform(4.0, 9.0)) * geom_scale
            angle = rng.uniform(-15.0, 35.0) if is_cresc else rng.uniform(0.0, 72.0)
            k_choices = [1] if sm <= 1.5 else [1, 2]
            k = rng.choice(k_choices)
            vy = k * height / duration
            m = rng.choice([1, 2])
            A = rng.uniform(4.0, 12.0) * res_scale
            x0 = rng.uniform(0, width)
            y0 = rng.uniform(0, height)
            alpha = int(round(rng.uniform(160, 245) * (0.5 + 0.5 * depth)))

            r_b = int(round(radius / 2.0)) * 2
            ang_b = int(round(angle / 5.0)) * 5
            shape_type = "cresc" if is_cresc else "star5"
            b_key = (shape_type, r_b, ang_b)

            if b_key not in base_sprites:
                pad = r_b * 2 + 10
                SS = 4
                im_ss = Image.new("RGBA", (pad * SS, pad * SS), (0, 0, 0, 0))
                d_ss = ImageDraw.Draw(im_ss)
                cx_ss = pad * SS / 2.0
                cy_ss = pad * SS / 2.0
                if is_cresc:
                    pts = crescent_polygon(cx_ss, cy_ss, r_b * SS, ang_b)
                else:
                    pts = star_5point_polygon(cx_ss, cy_ss, r_b * SS, angle_deg=ang_b)
                d_ss.polygon(pts, fill=(r_out, g_out, b_out, alpha))
                spr = im_ss.resize((pad, pad), Image.Resampling.LANCZOS)
                base_sprites[b_key] = (spr, pad)

            particles.append({
                "x0": x0, "y0": y0, "vy": vy, "m": m, "A": A,
                "radius": radius, "b_key": b_key,
            })
    elif is_eight_stars:
        # Eight-Point Stars: small Islamic-style stars (two overlaid squares), sparse and slow
        r_out = int(round(r * 0.35 + 255 * 0.65))
        g_out = int(round(g * 0.35 + 255 * 0.65))
        b_out = int(round(b * 0.35 + 255 * 0.65))
        count_8 = max(8, int(count * 0.65))

        for _ in range(count_8):
            depth = rng.uniform(0.35, 1.0)
            radius = rng.uniform(5.0, 13.0) * geom_scale
            angle = rng.uniform(0.0, 45.0)
            k_choices = [1] if sm <= 1.5 else [1, 2]
            k = rng.choice(k_choices)
            vy = k * height / duration
            m = rng.choice([1, 2])
            A = rng.uniform(4.0, 12.0) * res_scale
            x0 = rng.uniform(0, width)
            y0 = rng.uniform(0, height)
            alpha = int(round(rng.uniform(160, 245) * (0.5 + 0.5 * depth)))

            r_b = int(round(radius / 2.0)) * 2
            ang_b = int(round(angle / 5.0)) * 5
            b_key = ("star8", r_b, ang_b)

            if b_key not in base_sprites:
                pad = r_b * 2 + 10
                SS = 4
                im_ss = Image.new("RGBA", (pad * SS, pad * SS), (0, 0, 0, 0))
                d_ss = ImageDraw.Draw(im_ss)
                cx_ss = pad * SS / 2.0
                cy_ss = pad * SS / 2.0
                pts = star_8point_polygon(cx_ss, cy_ss, r_b * SS, angle_deg=ang_b)
                d_ss.polygon(pts, fill=(r_out, g_out, b_out, alpha))
                spr = im_ss.resize((pad, pad), Image.Resampling.LANCZOS)
                base_sprites[b_key] = (spr, pad)

            particles.append({
                "x0": x0, "y0": y0, "vy": vy, "m": m, "A": A,
                "radius": radius, "b_key": b_key,
            })
    elif is_flecks:
        # Drifting Flecks: Horizontal drift with subtle vertical undulating wave
        for _ in range(count):
            depth = rng.uniform(0.35, 1.0)
            radius = max(0.5, (1.2 + depth * 1.8) * geom_scale)
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
            radius = max(0.8, (1.8 + depth * 3.2) * geom_scale)
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
        "-loglevel", "error",
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

        if is_wind:
            draw = ImageDraw.Draw(img)
            for p in particles:
                cur_x, cur_y, alpha_val, rot = wind_streak_state(p, t)
                L = p["length"]
                T = p["thickness"]
                margin_check = L + T + 4.0
                if cur_x < -margin_check or cur_x > width + margin_check or cur_y < -margin_check or cur_y > height + margin_check:
                    continue
                half_d = max(0.1, (L - T) / 2.0)
                cos_r = math.cos(rot)
                sin_r = math.sin(rot)
                x1 = cur_x - half_d * cos_r
                y1 = cur_y - half_d * sin_r
                x2 = cur_x + half_d * cos_r
                y2 = cur_y + half_d * sin_r
                cr, cg, cb = p["color_rgb"]
                ca = int(round(alpha_val * 255))
                fill_color = (cr, cg, cb, ca)
                draw.line([(x1, y1), (x2, y2)], fill=fill_color, width=max(1, int(round(T))))
                r_cap = max(0.5, T / 2.0)
                draw.ellipse([x1 - r_cap, y1 - r_cap, x1 + r_cap, y1 + r_cap], fill=fill_color)
                draw.ellipse([x2 - r_cap, y2 - r_cap, x2 + r_cap, y2 + r_cap], fill=fill_color)
        elif is_glints or is_stars:
            for p in particles:
                cur_x, cur_y, alpha_factor = glint_state(p, t, duration)
                eff_alpha = int(p["peak_alpha"] * alpha_factor)
                if eff_alpha < 4:
                    continue
                q_level = int(round(eff_alpha / 17.0))
                if q_level <= 0:
                    continue
                q_alpha = min(255, q_level * 17)

                b_key = p["b_key"]
                ckey = (b_key, q_level)
                if ckey not in alpha_cache:
                    base_spr, pad = base_sprites[b_key]
                    r_ch, g_ch, b_ch, a_ch = base_spr.split()
                    scale = q_alpha / 255.0
                    a_ch = a_ch.point(lambda val: int(val * scale))
                    alpha_cache[ckey] = (Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch)), pad)

                spr, pad = alpha_cache[ckey]
                dest_x = int(round(cur_x - pad / 2.0))
                dest_y = int(round(cur_y - pad / 2.0))

                if dest_x + pad <= 0 or dest_y + pad <= 0 or dest_x >= width or dest_y >= height:
                    continue

                img.alpha_composite(spr, dest=(dest_x, dest_y))
        elif is_bokeh or is_crescents or is_eight_stars:
            for p in particles:
                cur_y = (p["y0"] + p["vy"] * t) % height
                cur_x = (p["x0"] + p["A"] * math.sin(two_pi * p["m"] * t / duration)) % width
                b_key = p["b_key"]
                spr, pad = base_sprites[b_key]
                dest_x = int(round(cur_x - pad / 2.0))
                dest_y = int(round(cur_y - pad / 2.0))
                if dest_x + pad <= 0 or dest_y + pad <= 0 or dest_x >= width or dest_y >= height:
                    continue
                img.alpha_composite(spr, dest=(dest_x, dest_y))
        elif is_flecks:
            draw = ImageDraw.Draw(img)
            for p in particles:
                cur_x = (p["x0"] + p["vx"] * t) % width
                cur_y = p["y0"] + p["A"] * math.sin(two_pi * p["m"] * t / duration)
                r_val = p["radius"]
                draw.ellipse(
                    [cur_x - r_val, cur_y - r_val, cur_x + r_val, cur_y + r_val],
                    fill=(r, g, b, p["alpha"]),
                )
        else:
            draw = ImageDraw.Draw(img)
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
