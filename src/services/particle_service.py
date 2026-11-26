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

import functools
import math
import os
import random
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image, ImageDraw

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QImage, QPainter, QColor, QPen, QBrush, QPolygonF

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


def draw_particle_shape(
    painter: QPainter,
    style: str,
    x: float,
    y: float,
    *,
    length: float = 0.0,
    thickness: float = 0.0,
    radius: float = 0.0,
    glint_width: float = 0.0,
    angle_deg: float = 0.0,
    rot_rad: float = 0.0,
    color_rgb: Tuple[int, int, int] = (255, 255, 255),
    alpha: float = 1.0,
    sub_type: str = "default",
    base_color_rgb: Optional[Tuple[int, int, int]] = None,
    size_factor: float = 1.0,
    canvas_height: float = 1080.0,
) -> None:
    """
    Unified anti-aliased vector particle drawing function used by both
    the interactive UI preview (ParticleOverlayWidget) and the MP4 export
    render pipeline (generate_particle_loop_video).

    Guarantees:
    - Pure vector drawing at true angle with floating-point sub-pixel coordinates.
    - Continuous floating-point thickness (no integer rounding).
    - QPen with RoundCap for Wind Streaks capsules.
    - Full Antialiasing, SmoothPixmapTransform and TextAntialiasing hints.
    - Zero dark fringes with Format_ARGB32_Premultiplied compositing.
    """
    s = str(style).lower()
    r_base, g_base, b_base = base_color_rgb or color_rgb

    if "wind" in s:
        cr, cg, cb = color_rgb
        a = max(0, min(255, int(round(alpha * 255.0))))
        if a <= 0:
            return
        pen = QPen(
            QColor(cr, cg, cb, a),
            max(0.1, float(thickness)),
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
        )
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        half_d = max(0.0, (float(length) - float(thickness)) / 2.0)
        cos_r = math.cos(rot_rad)
        sin_r = math.sin(rot_rad)
        x1 = x - half_d * cos_r
        y1 = y - half_d * sin_r
        x2 = x + half_d * cos_r
        y2 = y + half_d * sin_r
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    elif "glint" in s:
        r_out = int(round(r_base * 0.4 + 255 * 0.6))
        g_out = int(round(g_base * 0.4 + 255 * 0.6))
        b_out = int(round(b_base * 0.4 + 255 * 0.6))
        eff_alpha = max(0, min(255, int(round(alpha if alpha > 1.0 else alpha * 255.0))))
        if eff_alpha <= 4:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        # Outer lens sliver
        painter.setBrush(QColor(r_out, g_out, b_out, eff_alpha))
        pts = lens_polygon(x, y, length, glint_width, angle_deg)
        painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in pts]))

        # Core bright center (glow)
        core_alpha = min(255, int(round(eff_alpha * 1.15)))
        painter.setBrush(QColor(255, 255, 255, core_alpha))
        core_pts = lens_polygon(x, y, length * 0.65, glint_width * 0.45, angle_deg)
        painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in core_pts]))

    elif "twinkle" in s:
        r_out = int(round(r_base * 0.4 + 255 * 0.6))
        g_out = int(round(g_base * 0.4 + 255 * 0.6))
        b_out = int(round(b_base * 0.4 + 255 * 0.6))
        eff_alpha = max(0, min(255, int(round(alpha if alpha > 1.0 else alpha * 255.0))))
        if eff_alpha <= 4:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(r_out, g_out, b_out, eff_alpha))
        pts = star_4point_polygon(x, y, radius, radius * 0.18, angle_deg)
        painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in pts]))

        core_alpha = min(255, int(round(eff_alpha * 1.15)))
        painter.setBrush(QColor(255, 255, 255, core_alpha))
        core_pts = star_4point_polygon(x, y, radius * 0.45, radius * 0.10, angle_deg)
        painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in core_pts]))

    elif "bokeh" in s:
        r_edge = int(round(r_base * 0.3 + 255 * 0.7))
        g_edge = int(round(g_base * 0.3 + 255 * 0.7))
        b_edge = int(round(b_base * 0.3 + 255 * 0.7))
        pen_w = max(0.5, 1.8 * (canvas_height / 1080.0) * size_factor)
        pen = QPen(QColor(r_edge, g_edge, b_edge, 210), pen_w)
        brush = QBrush(QColor(r_base, g_base, b_base, 55))
        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawEllipse(QPointF(x, y), float(radius), float(radius))

    elif "crescent" in s:
        r_out = int(round(r_base * 0.35 + 255 * 0.65))
        g_out = int(round(g_base * 0.35 + 255 * 0.65))
        b_out = int(round(b_base * 0.35 + 255 * 0.65))
        painter.setPen(Qt.PenStyle.NoPen)
        a_val = max(0, min(255, int(round(alpha if alpha > 1.0 else alpha * 240.0))))
        painter.setBrush(QColor(r_out, g_out, b_out, a_val))
        if sub_type == "crescent":
            pts = crescent_polygon(x, y, radius, angle_deg)
        else:
            pts = star_5point_polygon(x, y, radius, angle_deg=angle_deg)
        painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in pts]))

    elif "eight" in s:
        r_out = int(round(r_base * 0.35 + 255 * 0.65))
        g_out = int(round(g_base * 0.35 + 255 * 0.65))
        b_out = int(round(b_base * 0.35 + 255 * 0.65))
        painter.setPen(Qt.PenStyle.NoPen)
        a_val = max(0, min(255, int(round(alpha if alpha > 1.0 else alpha * 240.0))))
        painter.setBrush(QColor(r_out, g_out, b_out, a_val))
        pts = star_8point_polygon(x, y, radius, angle_deg=angle_deg)
        painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in pts]))

    else:
        # Drifting Flecks and Floating Orbs
        a_val = max(0, min(255, int(round(alpha if alpha > 1.0 else alpha * 240.0))))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(r_base, g_base, b_base, a_val))
        painter.drawEllipse(QPointF(x, y), float(radius), float(radius))


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


class ParticleState:
    """
    Structured particle state container representing all particle states at timestamp t.
    Can be unpacked as a 4-tuple: positions, angles, sizes, alphas = particle_state(...)
    or accessed directly via .positions, .angles, .sizes, .alphas, .particles.
    """
    __slots__ = ("positions", "angles", "sizes", "alphas", "particles")

    def __init__(
        self,
        positions: List[Tuple[float, float]],
        angles: List[float],
        sizes: List[float],
        alphas: List[float],
        particles: List[dict],
    ):
        self.positions = positions
        self.angles = angles
        self.sizes = sizes
        self.alphas = alphas
        self.particles = particles

    def __iter__(self):
        return iter((self.positions, self.angles, self.sizes, self.alphas))

    def __getitem__(self, idx):
        return (self.positions, self.angles, self.sizes, self.alphas)[idx]

    def __len__(self):
        return 4


@functools.lru_cache(maxsize=64)
def _get_base_particle_descriptors(
    style: str,
    count: int,
    speed_level: int,
    size_val: int,
    angle_deg: float,
    seed: int,
    duration: float,
) -> Tuple[dict, ...]:
    count = max(1, min(50000, int(count)))
    sm = _speed_multiplier(speed_level)
    size_factor = (size_val / 5.0) if (1 <= size_val <= 20) else (size_val / 100.0)
    rng = random.Random(seed)
    W_ref = 1920.0
    H_ref = 1080.0
    two_pi = 2.0 * math.pi
    s = str(style).lower()

    if "wind" in s:
        ws_particles = create_wind_streak_particles(
            count=count,
            width=W_ref,
            height=H_ref,
            angle_deg=angle_deg,
            speed_level=speed_level,
            size_factor=size_factor,
            seed=seed,
        )
        return tuple(ws_particles)

    elif "fleck" in s:
        descriptors = []
        for _ in range(count):
            depth = rng.uniform(0.35, 1.0)
            base_rad = (1.2 + depth * 1.8) * size_factor
            k_choices = [1, 2] if sm <= 1.0 else ([1, 2, 3] if sm <= 2.0 else [2, 3, 4])
            k = rng.choice(k_choices)
            vx = k * W_ref / duration
            m = rng.choice([1, 2, 3])
            A = rng.uniform(15.0, 45.0) * sm
            phi = rng.uniform(0.0, two_pi)
            x0 = rng.uniform(0.0, W_ref)
            y0 = rng.uniform(H_ref * 0.05, H_ref * 0.95)
            alpha = int(round(rng.uniform(120, 245) * (0.4 + 0.6 * depth)))
            descriptors.append({
                "x0": x0, "y0": y0, "vx": vx, "m": m, "A": A, "phi": phi,
                "base_radius": base_rad, "alpha": alpha, "depth": depth,
            })
        return tuple(descriptors)

    elif "glint" in s:
        descriptors = []
        kx_choices = [1] if sm <= 1.0 else ([1, 2] if sm <= 3.0 else [2, 3])
        ky_choices = [-1] if sm <= 1.0 else ([-2, -1] if sm <= 3.0 else [-3, -2])
        for _ in range(count):
            depth = rng.uniform(0.35, 1.0)
            base_len = rng.uniform(14.0, 48.0) * size_factor
            w_ratio = rng.uniform(7.0, 11.0)
            base_glint_w = base_len / w_ratio
            angle = -60.0 + rng.uniform(-14.0, 14.0)
            n_val = rng.choice([2, 3, 4])
            phase = rng.uniform(0.0, 1.0)
            peak_alpha = int(round(rng.uniform(150, 255) * (0.5 + 0.5 * depth)))
            positions = tuple((rng.uniform(0.0, W_ref), rng.uniform(0.0, H_ref)) for _ in range(n_val))
            kx = rng.choice(kx_choices)
            ky = rng.choice(ky_choices)
            vx = kx * W_ref / duration
            vy = ky * H_ref / duration
            descriptors.append({
                "n": n_val, "phase": phase, "positions": positions,
                "vx": vx, "vy": vy, "peak_alpha": peak_alpha,
                "base_length": base_len, "base_glint_width": base_glint_w,
                "angle_deg": angle, "width": W_ref, "height": H_ref,
                "depth": depth,
            })
        return tuple(descriptors)

    elif "twinkle" in s:
        descriptors = []
        kx_choices = [1] if sm <= 1.0 else ([1, 2] if sm <= 3.0 else [2, 3])
        ky_choices = [-1, 0, 1]
        for _ in range(count):
            depth = rng.uniform(0.35, 1.0)
            base_rad = rng.uniform(8.0, 24.0) * size_factor
            angle = rng.uniform(0.0, 45.0)
            n_val = rng.choice([2, 3, 4])
            phase = rng.uniform(0.0, 1.0)
            peak_alpha = int(round(rng.uniform(150, 255) * (0.5 + 0.5 * depth)))
            positions = tuple((rng.uniform(0.0, W_ref), rng.uniform(0.0, H_ref)) for _ in range(n_val))
            kx = rng.choice(kx_choices)
            ky = rng.choice(ky_choices)
            vx = kx * W_ref / duration
            vy = ky * H_ref / duration
            descriptors.append({
                "n": n_val, "phase": phase, "positions": positions,
                "vx": vx, "vy": vy, "peak_alpha": peak_alpha,
                "base_radius": base_rad, "angle_deg": angle,
                "width": W_ref, "height": H_ref, "depth": depth,
            })
        return tuple(descriptors)

    elif "bokeh" in s:
        descriptors = []
        for _ in range(count):
            depth = rng.uniform(0.35, 1.0)
            base_rad = rng.uniform(6.0, 22.0) * size_factor
            k_choices = [1] if sm <= 1.5 else [1, 2]
            k = rng.choice(k_choices)
            vy = k * H_ref / duration
            m = rng.choice([1, 2])
            A_sway = rng.uniform(90.0, 200.0) * sm
            phi = rng.uniform(0.0, two_pi)
            x0 = rng.uniform(0.0, W_ref)
            y0 = rng.uniform(0.0, H_ref)
            descriptors.append({
                "x0": x0, "y0": y0, "vy": vy, "m": m,
                "A_sway": A_sway, "phi": phi,
                "base_radius": base_rad, "depth": depth,
            })
        return tuple(descriptors)

    elif "crescent" in s:
        descriptors = []
        cresc_count = max(8, int(count * 0.7))
        for i in range(cresc_count):
            depth = rng.uniform(0.35, 1.0)
            is_cresc = (i % 2 == 0)
            base_rad = (rng.uniform(7.0, 15.0) if is_cresc else rng.uniform(4.0, 9.0)) * size_factor
            angle = rng.uniform(-15.0, 35.0) if is_cresc else rng.uniform(0.0, 72.0)
            k_choices = [1] if sm <= 1.5 else [1, 2]
            k = rng.choice(k_choices)
            vy = k * H_ref / duration
            m1 = rng.choice([1, 2])
            m2 = rng.choice([2, 3])
            A_sway = rng.uniform(120.0, 260.0) * sm
            A_swirl = rng.uniform(60.0, 140.0) * sm
            phi1 = rng.uniform(0.0, two_pi)
            phi2 = rng.uniform(0.0, two_pi)
            x0 = rng.uniform(0.0, W_ref)
            y0 = rng.uniform(0.0, H_ref)
            alpha = int(round(rng.uniform(160, 245) * (0.5 + 0.5 * depth)))
            descriptors.append({
                "x0": x0, "y0": y0, "vy": vy, "m1": m1, "m2": m2,
                "A_sway": A_sway, "A_swirl": A_swirl, "phi1": phi1, "phi2": phi2,
                "base_radius": base_rad, "angle_deg": angle, "alpha": alpha,
                "sub_type": "crescent" if is_cresc else "star5",
                "depth": depth,
            })
        return tuple(descriptors)

    elif "eight" in s:
        descriptors = []
        count_8 = max(8, int(count * 0.65))
        for _ in range(count_8):
            depth = rng.uniform(0.35, 1.0)
            base_rad = rng.uniform(5.0, 13.0) * size_factor
            angle = rng.uniform(0.0, 45.0)
            k_choices = [1] if sm <= 1.5 else [1, 2]
            k = rng.choice(k_choices)
            vy = k * H_ref / duration
            m1 = rng.choice([1, 2])
            m2 = rng.choice([2, 3])
            A_sway = rng.uniform(120.0, 260.0) * sm
            A_swirl = rng.uniform(60.0, 140.0) * sm
            phi1 = rng.uniform(0.0, two_pi)
            phi2 = rng.uniform(0.0, two_pi)
            x0 = rng.uniform(0.0, W_ref)
            y0 = rng.uniform(0.0, H_ref)
            alpha = int(round(rng.uniform(160, 245) * (0.5 + 0.5 * depth)))
            descriptors.append({
                "x0": x0, "y0": y0, "vy": vy, "m1": m1, "m2": m2,
                "A_sway": A_sway, "A_swirl": A_swirl, "phi1": phi1, "phi2": phi2,
                "base_radius": base_rad, "angle_deg": angle, "alpha": alpha,
                "sub_type": "star8",
                "depth": depth,
            })
        return tuple(descriptors)

    else:  # Floating Orbs
        descriptors = []
        for _ in range(count):
            depth = rng.uniform(0.3, 1.0)
            base_rad = (1.8 + depth * 3.2) * size_factor
            k_choices = [1, 2] if sm <= 1.0 else ([1, 2, 3] if sm <= 2.0 else [2, 3, 4])
            k = rng.choice(k_choices)
            vy = k * H_ref / duration
            m1 = rng.choice([1, 2])
            m2 = rng.choice([2, 3])
            A_sway = rng.uniform(80.0, 180.0) * sm
            A_drift = rng.uniform(30.0, 80.0) * sm
            phi1 = rng.uniform(0.0, two_pi)
            phi2 = rng.uniform(0.0, two_pi)
            x0 = rng.uniform(0.0, W_ref)
            y0 = rng.uniform(0.0, H_ref)
            alpha = int(round(rng.uniform(100, 225) * (0.35 + 0.65 * depth)))
            descriptors.append({
                "x0": x0, "y0": y0, "vy": vy, "m1": m1, "m2": m2,
                "A_sway": A_sway, "A_drift": A_drift, "phi1": phi1, "phi2": phi2,
                "base_radius": base_rad, "alpha": alpha, "depth": depth,
            })
        return tuple(descriptors)


def particle_state(
    style: str,
    params: Optional[dict] = None,
    seed: Optional[int] = None,
    t: float = 0.0,
    canvas_size: Tuple[float, float] = (1920.0, 1080.0),
) -> ParticleState:
    """
    Unified stateless particle motion engine used by both the in-app preview
    and the MP4 render export.

    Returns ParticleState with positions, angles, sizes, alphas, and particles.
    Can be unpacked as: positions, angles, sizes, alphas = particle_state(...)
    """
    if params is None:
        params = {}

    count = int(params.get("count", params.get("quantity", 80)) or 80)
    speed_level = int(params.get("speed", 2) or 2)
    raw_size = params.get("size")
    if raw_size is not None and 1 <= int(raw_size) <= 20:
        size_val = int(raw_size)
    elif raw_size is not None and int(raw_size) > 20:
        size_val = max(1, min(20, int(round(int(raw_size) / 20.0))))
    else:
        size_val = 5

    angle_deg = float(params.get("angle", 225.0) or 225.0)
    duration = float(params.get("duration", 6.0) or 6.0)
    raw_color = params.get("color", (56, 189, 248))
    if isinstance(raw_color, str):
        c_str = raw_color.lstrip("#")
        if len(c_str) == 6:
            color_rgb = (int(c_str[0:2], 16), int(c_str[2:4], 16), int(c_str[4:6], 16))
        else:
            color_rgb = (56, 189, 248)
    elif isinstance(raw_color, (tuple, list)) and len(raw_color) >= 3:
        color_rgb = (int(raw_color[0]), int(raw_color[1]), int(raw_color[2]))
    else:
        color_rgb = (56, 189, 248)

    if seed is None:
        seed = int(params.get("seed", 42 + count + speed_level + int(angle_deg)))

    canvas_w, canvas_h = canvas_size
    scale_x = float(canvas_w) / 1920.0
    scale_y = float(canvas_h) / 1080.0
    W_ref = 1920.0
    H_ref = 1080.0
    two_pi = 2.0 * math.pi

    descriptors = _get_base_particle_descriptors(
        style=str(style),
        count=count,
        speed_level=speed_level,
        size_val=size_val,
        angle_deg=angle_deg,
        seed=seed,
        duration=duration,
    )

    positions: List[Tuple[float, float]] = []
    angles: List[float] = []
    sizes: List[float] = []
    alphas: List[float] = []
    particles: List[dict] = []

    s = str(style).lower()

    if "wind" in s:
        for p in descriptors:
            cur_x_c, cur_y_c, alpha_val, rot = wind_streak_state(p, t)
            x = cur_x_c * scale_x
            y = cur_y_c * scale_y
            L = p["length"] * scale_y
            T = p["thickness"] * scale_y
            ang = math.degrees(rot)
            positions.append((x, y))
            angles.append(ang)
            sizes.append(L)
            alphas.append(alpha_val)
            particles.append({
                "x": x,
                "y": y,
                "length": L,
                "thickness": T,
                "rot_rad": rot,
                "angle_deg": ang,
                "color_rgb": p.get("color_rgb", (255, 255, 255)),
                "alpha": alpha_val,
                "size": L,
                "radius": T,
            })
    elif "fleck" in s:
        for p in descriptors:
            cur_x_c = (p["x0"] + p["vx"] * t) % W_ref
            cur_y_c = p["y0"] + p["A"] * math.sin(two_pi * p["m"] * t / duration + p["phi"])
            x = cur_x_c * scale_x
            y = cur_y_c * scale_y
            rad = p["base_radius"] * scale_y
            alp = p["alpha"] / 255.0
            positions.append((x, y))
            angles.append(0.0)
            sizes.append(rad)
            alphas.append(alp)
            particles.append({
                "x": x,
                "y": y,
                "radius": rad,
                "alpha": alp,
                "color_rgb": color_rgb,
                "size": rad,
            })
    elif "glint" in s:
        for p in descriptors:
            cur_x_c, cur_y_c, alpha_factor = glint_state(p, t, duration)
            x = cur_x_c * scale_x
            y = cur_y_c * scale_y
            L = p["base_length"] * scale_y
            gw = p["base_glint_width"] * scale_y
            eff_alpha = (p["peak_alpha"] * alpha_factor) / 255.0
            ang = p["angle_deg"]
            positions.append((x, y))
            angles.append(ang)
            sizes.append(L)
            alphas.append(eff_alpha)
            particles.append({
                "x": x,
                "y": y,
                "length": L,
                "glint_width": gw,
                "radius": gw,
                "angle_deg": ang,
                "alpha": eff_alpha,
                "color_rgb": color_rgb,
                "size": L,
            })
    elif "twinkle" in s:
        for p in descriptors:
            cur_x_c, cur_y_c, alpha_factor = glint_state(p, t, duration)
            x = cur_x_c * scale_x
            y = cur_y_c * scale_y
            rad = p["base_radius"] * scale_y
            eff_alpha = (p["peak_alpha"] * alpha_factor) / 255.0
            ang = p["angle_deg"]
            positions.append((x, y))
            angles.append(ang)
            sizes.append(rad)
            alphas.append(eff_alpha)
            particles.append({
                "x": x,
                "y": y,
                "radius": rad,
                "angle_deg": ang,
                "alpha": eff_alpha,
                "color_rgb": color_rgb,
                "size": rad,
            })
    elif "bokeh" in s:
        for p in descriptors:
            cur_x_c = (p["x0"] + p["A_sway"] * math.sin(two_pi * p["m"] * t / duration + p["phi"])) % W_ref
            cur_y_c = (p["y0"] + p["vy"] * t) % H_ref
            x = cur_x_c * scale_x
            y = cur_y_c * scale_y
            rad = p["base_radius"] * scale_y
            positions.append((x, y))
            angles.append(0.0)
            sizes.append(rad)
            alphas.append(1.0)
            particles.append({
                "x": x,
                "y": y,
                "radius": rad,
                "alpha": 1.0,
                "color_rgb": color_rgb,
                "size": rad,
            })
    elif "crescent" in s:
        for p in descriptors:
            cur_x_c = (p["x0"] + p["A_sway"] * math.sin(two_pi * p["m1"] * t / duration + p["phi1"]) +
                       p["A_swirl"] * math.cos(two_pi * p["m2"] * t / duration + p["phi2"])) % W_ref
            cur_y_c = (p["y0"] + p["vy"] * t) % H_ref
            x = cur_x_c * scale_x
            y = cur_y_c * scale_y
            rad = p["base_radius"] * scale_y
            ang = p["angle_deg"]
            alp = p["alpha"] / 255.0
            positions.append((x, y))
            angles.append(ang)
            sizes.append(rad)
            alphas.append(alp)
            particles.append({
                "x": x,
                "y": y,
                "radius": rad,
                "angle_deg": ang,
                "alpha": alp,
                "sub_type": p["sub_type"],
                "color_rgb": color_rgb,
                "size": rad,
            })
    elif "eight" in s:
        for p in descriptors:
            cur_x_c = (p["x0"] + p["A_sway"] * math.sin(two_pi * p["m1"] * t / duration + p["phi1"]) +
                       p["A_swirl"] * math.cos(two_pi * p["m2"] * t / duration + p["phi2"])) % W_ref
            cur_y_c = (p["y0"] + p["vy"] * t) % H_ref
            x = cur_x_c * scale_x
            y = cur_y_c * scale_y
            rad = p["base_radius"] * scale_y
            ang = p["angle_deg"]
            alp = p["alpha"] / 255.0
            positions.append((x, y))
            angles.append(ang)
            sizes.append(rad)
            alphas.append(alp)
            particles.append({
                "x": x,
                "y": y,
                "radius": rad,
                "angle_deg": ang,
                "alpha": alp,
                "sub_type": "star8",
                "color_rgb": color_rgb,
                "size": rad,
            })
    else:  # Floating Orbs
        for p in descriptors:
            cur_x_c = (p["x0"] + p["A_sway"] * math.sin(two_pi * p["m1"] * t / duration + p["phi1"]) +
                       p["A_drift"] * math.cos(two_pi * p["m2"] * t / duration + p["phi2"])) % W_ref
            cur_y_c = (p["y0"] + p["vy"] * t) % H_ref
            x = cur_x_c * scale_x
            y = cur_y_c * scale_y
            rad = p["base_radius"] * scale_y
            alp = p["alpha"] / 255.0
            positions.append((x, y))
            angles.append(0.0)
            sizes.append(rad)
            alphas.append(alp)
            particles.append({
                "x": x,
                "y": y,
                "radius": rad,
                "alpha": alp,
                "color_rgb": color_rgb,
                "size": rad,
            })

    return ParticleState(positions, angles, sizes, alphas, particles)


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
    Uses unified particle_state engine to ensure 100% motion parity with preview.
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

    count = max(10, min(300, int(quantity)))
    size_factor = (size / 5.0) if (1 <= size <= 20) else (size / 100.0)

    params = {
        "count": count,
        "speed": speed,
        "size": size,
        "angle": angle,
        "duration": duration,
        "color": (r, g, b),
    }
    seed = 42 + count + speed + int(angle)

    cmd = [
        ffmpeg_bin, "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "bgra",
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

    base_col = (r, g, b)
    qimg = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)

    for frame_idx in range(num_frames):
        t = frame_idx / float(fps)
        qimg.fill(0)
        painter = QPainter(qimg)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        p_state = particle_state(style, params, seed, t, (width, height))
        for p in p_state.particles:
            cur_x = p["x"]
            cur_y = p["y"]
            L = p.get("length", 0.0)
            T = p.get("thickness", 0.0)
            margin_check = L + T + 10.0
            if cur_x < -margin_check or cur_x > width + margin_check or cur_y < -margin_check or cur_y > height + margin_check:
                continue

            draw_particle_shape(
                painter,
                style,
                cur_x,
                cur_y,
                length=L,
                thickness=T,
                radius=p.get("radius", 0.0),
                glint_width=p.get("glint_width", 0.0),
                angle_deg=p.get("angle_deg", 0.0),
                rot_rad=p.get("rot_rad", 0.0),
                color_rgb=p.get("color_rgb", base_col),
                alpha=p.get("alpha", 1.0),
                sub_type=p.get("sub_type", "default"),
                base_color_rgb=base_col,
                size_factor=size_factor,
                canvas_height=height,
            )

        painter.end()
        proc.stdin.write(bytes(qimg.constBits()))

    proc.stdin.close()
    _, stderr_bytes = proc.communicate()

    if proc.returncode != 0:
        err_msg = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else "Unknown error"
        raise RuntimeError(f"FFmpeg particle generation failed: {err_msg}")

    return out_file
