"""
Reproduce and document baseline divergence for ITEM 1D: Particle motion mismatch.
"""
import os
import sys
import math
import random
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QImage, QPainter, QColor, QFont
from PySide6.QtWidgets import QApplication

from src.services.particle_service import (
    STYLE_CRESCENTS_AND_STARS,
    STYLE_EIGHT_POINT_STARS,
    STYLE_FLOATING_ORBS,
    STYLE_DRIFTING_FLECKS,
    STYLE_BOKEH_RINGS,
    STYLE_TWINKLE_STARS,
    STYLE_LIGHT_GLINTS,
    STYLE_WIND_STREAKS,
    generate_particle_loop_video,
    draw_particle_shape,
)
from src.ui.widgets.particle_canvas import ParticleOverlayWidget, Particle

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    out_dir = Path("tests/artifacts/particles_parity").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Use Crescents and Stars (snowflake/star style mentioned in issue)
    style = STYLE_CRESCENTS_AND_STARS
    width = 1920
    height = 1080
    count = 20
    speed = 2
    size = 5
    fps = 30
    timestamps = [0.0, 2.0, 5.0, 10.0]

    print(f"--- Reproducing Baseline Divergence for {style} ---")

    # 1. Preview Widget Simulation at 1920x1080
    widget = ParticleOverlayWidget()
    widget.resize(width, height)
    widget.set_particle_style(style)
    widget.set_particle_count(count)
    widget.set_particle_speed(speed)
    widget.set_particle_size(size)
    widget.set_enabled(True)

    preview_trajectory = {i: [] for i in range(5)}
    preview_frames = {}

    # Step through 10 seconds at 30 fps (300 frames)
    total_frames = int(10.0 * fps)
    for f in range(total_frames + 1):
        t_curr = f / float(fps)
        if any(math.isclose(t_curr, ts, abs_tol=1e-3) for ts in timestamps):
            ts_matched = [ts for ts in timestamps if math.isclose(t_curr, ts, abs_tol=1e-3)][0]
            # Record positions of first 5 particles
            for i in range(5):
                p = widget._particles[i]
                preview_trajectory[i].append((t_curr, p.x, p.y))
            # Grab frame
            img = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(0)
            widget.render(img, QPoint())
            preview_frames[ts_matched] = img

        # Advance widget one tick
        widget._update_particles()

    # 2. Render Path Simulation (using generate_particle_loop_video logic)
    # The render path generates a 6s loop video and loops it
    duration = 6.0
    rng = random.Random(42 + count + speed)
    cresc_count = max(8, int(count * 0.7))
    res_scale = height / 1080.0
    geom_scale = res_scale * (size / 5.0)
    sm = 1.0  # speed multiplier for speed=2

    render_particles = []
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
        render_particles.append({
            "x0": x0, "y0": y0, "vy": vy, "m": m, "A": A,
            "radius": radius, "angle_deg": angle, "alpha": alpha,
            "sub_type": "crescent" if is_cresc else "star5"
        })

    render_trajectory = {i: [] for i in range(5)}
    render_frames = {}
    two_pi = 2.0 * math.pi

    for ts in timestamps:
        t_mod = ts % duration
        img = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for idx, p in enumerate(render_particles):
            cur_y = (p["y0"] + p["vy"] * t_mod) % height
            cur_x = (p["x0"] + p["A"] * math.sin(two_pi * p["m"] * t_mod / duration)) % width
            if idx < 5:
                render_trajectory[idx].append((ts, cur_x, cur_y))
            draw_particle_shape(
                painter,
                style,
                cur_x,
                cur_y,
                radius=p["radius"],
                angle_deg=p["angle_deg"],
                alpha=p["alpha"],
                sub_type=p["sub_type"],
                base_color_rgb=(56, 189, 248),
            )
        painter.end()
        render_frames[ts] = img

    # 3. Print Data & Tabulate Divergence
    print("\n--- Particle Tracking Table (Preview vs. Render) ---")
    print(f"{'Particle':<10} | {'Time (s)':<8} | {'Preview (x, y)':<22} | {'Render (x, y)':<22} | {'Delta X (px)':<12} | {'Delta Y (px)':<12}")
    print("-" * 95)

    delta_xs = []
    delta_ys = []
    prev_x_spreads = []
    rend_x_spreads = []

    for i in range(5):
        p_prev = preview_trajectory[i]
        p_rend = render_trajectory[i]
        xs_prev = [pt[1] for pt in p_prev]
        xs_rend = [pt[1] for pt in p_rend]
        prev_x_spreads.append(max(xs_prev) - min(xs_prev))
        rend_x_spreads.append(max(xs_rend) - min(xs_rend))

        for j, ts in enumerate(timestamps):
            px, py = p_prev[j][1], p_prev[j][2]
            rx, ry = p_rend[j][1], p_rend[j][2]
            dx = abs(px - rx)
            dy = abs(py - ry)
            delta_xs.append(dx)
            delta_ys.append(dy)
            print(f"P{i+1:<9} | {ts:<8.1f} | ({px:7.1f}, {py:7.1f})   | ({rx:7.1f}, {ry:7.1f})   | {dx:10.1f}   | {dy:10.1f}")
        print("-" * 95)

    print(f"\nAverage |Δx|: {np.mean(delta_xs):.1f} px | Max |Δx|: {np.max(delta_xs):.1f} px")
    print(f"Average |Δy|: {np.mean(delta_ys):.1f} px | Max |Δy|: {np.max(delta_ys):.1f} px")
    print(f"Average Preview Horizontal Range (Sway/Drift): {np.mean(prev_x_spreads):.1f} px")
    print(f"Average Render Horizontal Range (Straight Fall): {np.mean(rend_x_spreads):.1f} px")

    # 4. Save side-by-side contact sheet and path traces
    # Contact sheet: 4 timestamps x 2 (preview left, render right)
    sheet_w = width * 2
    sheet_h = height * 4
    sheet = Image.new("RGB", (sheet_w // 2, sheet_h // 2), (20, 24, 33))
    draw = ImageDraw.Draw(sheet)

    half_w = width // 2
    half_h = height // 2

    for row, ts in enumerate(timestamps):
        p_pil = Image.fromqimage(preview_frames[ts]).resize((half_w, half_h))
        r_pil = Image.fromqimage(render_frames[ts]).resize((half_w, half_h))

        y_offset = row * half_h
        sheet.paste(p_pil, (0, y_offset))
        sheet.paste(r_pil, (half_w, y_offset))

        draw.text((20, y_offset + 20), f"Preview (t={ts:.1f}s)", fill=(255, 255, 255))
        draw.text((half_w + 20, y_offset + 20), f"Render Export (t={ts:.1f}s)", fill=(255, 255, 255))

    sheet.save(out_dir / "baseline_contact_sheet_crescents.png")

    # Path trace image (0 to 10s trajectories)
    trace_img = Image.new("RGB", (width, height), (15, 23, 42))
    trace_draw = ImageDraw.Draw(trace_img)
    # Draw preview trajectories in cyan/green, render in red/orange
    colors_prev = [(56, 189, 248), (52, 211, 153), (129, 140, 248), (251, 146, 60), (232, 121, 249)]
    colors_rend = [(239, 68, 68), (249, 115, 22), (234, 179, 8), (236, 72, 153), (168, 85, 247)]

    # Draw legend
    trace_draw.text((40, 30), "BASELINE TRAJECTORIES (0s to 10s)", fill=(255, 255, 255))
    trace_draw.text((40, 60), "Cyan/Green/Purple = Preview paths (swaying/drifting)", fill=(56, 189, 248))
    trace_draw.text((40, 90), "Red/Orange = Render paths (nearly straight vertical fall)", fill=(239, 68, 68))

    for i in range(5):
        # Preview line
        pts_prev = [(pt[1], pt[2]) for pt in preview_trajectory[i]]
        trace_draw.line(pts_prev, fill=colors_prev[i], width=3)
        # Render line
        pts_rend = [(pt[1], pt[2]) for pt in render_trajectory[i]]
        trace_draw.line(pts_rend, fill=colors_rend[i], width=3)

    trace_img.save(out_dir / "baseline_path_trace_crescents.png")
    print(f"Saved baseline artifacts to {out_dir}")

if __name__ == "__main__":
    main()
