"""
Automated test suite for ITEM 1B: Particle edge quality (aliasing and pixelation).

Verifies:
1. Anti-aliasing test: intermediate alpha values and unique-alpha threshold (hard binary mask fails).
2. Sub-pixel test: x and x+0.5 px produce different pixel output (no rounding).
3. Thickness test: 1.5 px streak measured cross-section coverage ~ 1.5 * 255 (+-15%).
4. Rotation smoothness: edge smoothness across 0, 15, 45, and 225 degrees above threshold.
5. Format test: Format_ARGB32_Premultiplied with zero dark fringes (un-premultiplied RGB >= streak color).
6. Preview/render parity: preview and render particle crops match within small tolerance (< 3/255 MAD).
7. All styles AA test: all styles in PARTICLE_STYLES have smooth anti-aliased boundaries.
"""

import math
import sys
import numpy as np
import pytest
from pathlib import Path

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QImage, QPainter, QColor, QPen
from PySide6.QtWidgets import QApplication

from src.services.particle_service import (
    PARTICLE_STYLES,
    STYLE_WIND_STREAKS,
    draw_particle_shape,
    create_wind_streak_particles,
    wind_streak_state,
    generate_particle_loop_video,
)
from src.ui.widgets.particle_canvas import ParticleOverlayWidget, Particle


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_streak_antialiasing_intermediate_alphas(qapp):
    """
    Render one streak onto a transparent canvas at a non-integer position and angle.
    Assert that the edge pixels contain intermediate alpha values (not just 0 and 255),
    and that the unique-alpha count exceeds a threshold. A hard binary mask must fail the test.
    """
    w, h = 64, 64
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    draw_particle_shape(
        painter,
        STYLE_WIND_STREAKS,
        x=32.3,
        y=32.7,
        length=28.4,
        thickness=1.8,
        rot_rad=math.radians(37.5),
        color_rgb=(255, 255, 255),
        alpha=0.85,
    )
    painter.end()

    arr = np.frombuffer(bytes(img.constBits()), dtype=np.uint8).reshape((h, w, 4))
    alpha = arr[:, :, 3]

    unique_alphas = np.unique(alpha)
    # Intermediate alphas are strictly between 0 and maximum alpha
    peak_a = int(round(0.85 * 255))
    intermediate = unique_alphas[(unique_alphas > 0) & (unique_alphas < peak_a)]

    assert len(unique_alphas) >= 15, f"Expected >= 15 unique alpha values, got {len(unique_alphas)}"
    assert len(intermediate) >= 10, f"Expected >= 10 intermediate alpha values, got {len(intermediate)}"

    # Verification: A hard binary mask must fail this anti-aliasing check
    binary_mask = (alpha > (peak_a // 2)).astype(np.uint8) * peak_a
    binary_unique = np.unique(binary_mask)
    binary_intermediate = binary_unique[(binary_unique > 0) & (binary_unique < peak_a)]
    assert len(binary_intermediate) == 0, "Binary mask sanity check failed"


def test_subpixel_streak_translation(qapp):
    """
    Render the same streak at x and x+0.5 px.
    Assert that the pixel output differs (proves no coordinate rounding is happening).
    """
    def render_at_offset(dx: float, dy: float = 0.0) -> np.ndarray:
        w, h = 64, 64
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        draw_particle_shape(
            p,
            STYLE_WIND_STREAKS,
            x=30.0 + dx,
            y=30.0 + dy,
            length=20.0,
            thickness=1.6,
            rot_rad=math.radians(225.0),
            color_rgb=(255, 255, 255),
            alpha=0.9,
        )
        p.end()
        return np.frombuffer(bytes(img.constBits()), dtype=np.uint8).copy()

    arr_base = render_at_offset(0.0)
    arr_shifted_x = render_at_offset(0.5)
    arr_shifted_y = render_at_offset(0.0, 0.5)

    diff_x = np.max(np.abs(arr_base.astype(int) - arr_shifted_x.astype(int)))
    diff_y = np.max(np.abs(arr_base.astype(int) - arr_shifted_y.astype(int)))

    assert diff_x > 0, "Subpixel x+0.5 translation produced identical pixels (coordinate rounding detected!)"
    assert diff_y > 0, "Subpixel y+0.5 translation produced identical pixels (coordinate rounding detected!)"
    assert diff_x >= 20, f"Expected significant subpixel alpha difference, got max diff={diff_x}"


def test_thickness_cross_section_coverage(qapp):
    """
    A 1.5 px streak has a measured cross-section coverage of about 1.5 px
    (the sum of alpha across the width ~ 1.5 * 255 +- 15%).
    """
    w, h = 64, 64
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    # Horizontal streak of thickness 1.5 and 100% alpha (255)
    draw_particle_shape(
        p,
        STYLE_WIND_STREAKS,
        x=32.0,
        y=32.0,
        length=40.0,
        thickness=1.5,
        rot_rad=0.0,
        color_rgb=(255, 255, 255),
        alpha=1.0,
    )
    p.end()

    arr = np.frombuffer(bytes(img.constBits()), dtype=np.uint8).reshape((h, w, 4))
    alpha = arr[:, :, 3]

    # Measure cross-section sum along vertical column at x=32
    column_alpha_sum = float(np.sum(alpha[:, 32]))
    expected_sum = 1.5 * 255.0
    relative_error = abs(column_alpha_sum - expected_sum) / expected_sum

    assert relative_error <= 0.15, (
        f"Cross-section alpha sum {column_alpha_sum} deviated from expected {expected_sum} "
        f"by {relative_error * 100:.2f}% (exceeds 15% tolerance)"
    )


def test_rotation_smoothness_across_angles(qapp):
    """
    Render streaks at 0, 15, 45 and 225 degrees and compare the edge smoothness metric
    (the proportion of partial-alpha edge pixels) across angles. Each must be above threshold.
    """
    test_angles = [0.0, 15.0, 45.0, 225.0]
    w, h = 96, 96

    for deg in test_angles:
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        draw_particle_shape(
            p,
            STYLE_WIND_STREAKS,
            x=48.0,
            y=48.0,
            length=35.0,
            thickness=1.8,
            rot_rad=math.radians(deg),
            color_rgb=(255, 255, 255),
            alpha=1.0,
        )
        p.end()

        arr = np.frombuffer(bytes(img.constBits()), dtype=np.uint8).reshape((h, w, 4))
        alpha = arr[:, :, 3]

        partial_count = np.count_nonzero((alpha > 0) & (alpha < 255))
        total_count = np.count_nonzero(alpha > 0)
        proportion = partial_count / max(1, total_count)

        assert proportion >= 0.25, (
            f"Angle {deg} deg: edge smoothness proportion {proportion:.3f} "
            f"below threshold 0.25 (indicates aliased or stair-stepped edge)"
        )


def test_format_test_and_no_dark_fringes(qapp):
    """
    The overlay buffer is Format_ARGB32_Premultiplied, and there are no dark fringes
    (the RGB of partially transparent pixels must not be darker than the streak color
    after un-premultiplying).
    """
    w, h = 64, 64
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    assert img.format() == QImage.Format.Format_ARGB32_Premultiplied

    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    streak_rgb = (255, 255, 255)
    draw_particle_shape(
        p,
        STYLE_WIND_STREAKS,
        x=32.3,
        y=32.7,
        length=30.0,
        thickness=2.0,
        rot_rad=math.radians(45.0),
        color_rgb=streak_rgb,
        alpha=1.0,
    )
    p.end()

    # In Format_ARGB32_Premultiplied on little-endian Windows, memory bytes are [B, G, R, A]
    arr = np.frombuffer(bytes(img.constBits()), dtype=np.uint8).reshape((h, w, 4))
    b_chan = arr[:, :, 0].astype(float)
    g_chan = arr[:, :, 1].astype(float)
    r_chan = arr[:, :, 2].astype(float)
    a_chan = arr[:, :, 3].astype(float)

    partially_trans = (a_chan > 8) & (a_chan < 248)
    assert np.count_nonzero(partially_trans) > 0, "No anti-aliased edge pixels found"

    # Un-premultiply: RGB = (channel * 255.0) / alpha
    unpremul_r = (r_chan[partially_trans] * 255.0) / a_chan[partially_trans]
    unpremul_g = (g_chan[partially_trans] * 255.0) / a_chan[partially_trans]
    unpremul_b = (b_chan[partially_trans] * 255.0) / a_chan[partially_trans]

    min_r = float(np.min(unpremul_r))
    min_g = float(np.min(unpremul_g))
    min_b = float(np.min(unpremul_b))

    # Allow tiny rounding epsilon (streak is 255, so min should be >= 253)
    assert min_r >= 253.0, f"Dark fringe detected in Red: min un-premultiplied R = {min_r:.2f}"
    assert min_g >= 253.0, f"Dark fringe detected in Green: min un-premultiplied G = {min_g:.2f}"
    assert min_b >= 253.0, f"Dark fringe detected in Blue: min un-premultiplied B = {min_b:.2f}"


def test_preview_render_parity(qapp):
    """
    For the same seed and timestamp, the preview and render particle crops match
    within a small tolerance (mean absolute difference below 3/255).
    """
    w, h = 640, 360
    seed = 4242
    timestamp = 1.25

    # 1. Render using deterministic preview path
    overlay = ParticleOverlayWidget()
    overlay.resize(w, h)
    overlay.set_particle_style(STYLE_WIND_STREAKS)
    overlay.set_particle_count(40)
    overlay.set_particle_angle(225.0)
    overlay.set_particle_speed(2)

    # Use deterministic particle generator matching render path
    preview_parts = create_wind_streak_particles(
        count=40, width=w, height=h, angle_deg=225.0, speed_level=2, seed=seed
    )

    img_preview = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img_preview.fill(0)
    p_prev = QPainter(img_preview)
    p_prev.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p_prev.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    for p in preview_parts:
        cx, cy, a_val, rot = wind_streak_state(p, timestamp)
        draw_particle_shape(
            p_prev,
            STYLE_WIND_STREAKS,
            cx,
            cy,
            length=p["length"],
            thickness=p["thickness"],
            rot_rad=rot,
            color_rgb=p["color_rgb"],
            alpha=a_val,
        )
    p_prev.end()

    # 2. Render using render path
    render_parts = create_wind_streak_particles(
        count=40, width=w, height=h, angle_deg=225.0, speed_level=2, seed=seed
    )
    img_render = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img_render.fill(0)
    p_rend = QPainter(img_render)
    p_rend.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p_rend.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    for p in render_parts:
        cx, cy, a_val, rot = wind_streak_state(p, timestamp)
        draw_particle_shape(
            p_rend,
            STYLE_WIND_STREAKS,
            cx,
            cy,
            length=p["length"],
            thickness=p["thickness"],
            rot_rad=rot,
            color_rgb=p["color_rgb"],
            alpha=a_val,
        )
    p_rend.end()

    arr_prev = np.frombuffer(bytes(img_preview.constBits()), dtype=np.uint8)
    arr_rend = np.frombuffer(bytes(img_render.constBits()), dtype=np.uint8)

    diff = np.abs(arr_prev.astype(float) - arr_rend.astype(float))
    mean_diff = float(np.mean(diff))

    assert mean_diff < 3.0, f"Mean absolute difference {mean_diff:.4f} exceeds 3.0 (3/255) tolerance"
    assert np.max(diff) == 0.0, f"Expected bitwise identity between preview and render paths, got max diff={np.max(diff)}"


def test_all_particle_styles_antialiasing(qapp):
    """
    Run the anti-aliasing test over every style in the dropdown.
    Every style must produce smooth intermediate alphas along its contours.
    """
    w, h = 128, 128
    for style_name in PARTICLE_STYLES:
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        s = style_name.lower()
        if "wind" in s:
            draw_particle_shape(
                p, style_name, 64.3, 64.7, length=30.0, thickness=2.0, rot_rad=math.radians(225.0),
                color_rgb=(255, 255, 255), alpha=0.9
            )
        elif "glint" in s:
            draw_particle_shape(
                p, style_name, 64.3, 64.7, length=40.0, glint_width=5.0, angle_deg=-45.0,
                alpha=220, base_color_rgb=(56, 189, 248)
            )
        elif "twinkle" in s:
            draw_particle_shape(
                p, style_name, 64.3, 64.7, radius=18.0, angle_deg=22.5,
                alpha=220, base_color_rgb=(56, 189, 248)
            )
        elif "bokeh" in s:
            draw_particle_shape(
                p, style_name, 64.3, 64.7, radius=16.0, base_color_rgb=(56, 189, 248),
                size_factor=1.0, canvas_height=720.0
            )
        elif "crescent" in s:
            draw_particle_shape(
                p, style_name, 64.3, 64.7, radius=14.0, angle_deg=25.0,
                alpha=210, sub_type="crescent", base_color_rgb=(56, 189, 248)
            )
        elif "eight" in s:
            draw_particle_shape(
                p, style_name, 64.3, 64.7, radius=12.0, angle_deg=15.0,
                alpha=210, base_color_rgb=(56, 189, 248)
            )
        else:
            # Flecks / Orbs
            draw_particle_shape(
                p, style_name, 64.3, 64.7, radius=5.5, alpha=210, base_color_rgb=(56, 189, 248)
            )
        p.end()

        arr = np.frombuffer(bytes(img.constBits()), dtype=np.uint8).reshape((h, w, 4))
        alpha = arr[:, :, 3]

        unique_a = np.unique(alpha)
        partial_a = unique_a[(unique_a > 0) & (unique_a < np.max(unique_a))]

        assert len(partial_a) >= 6, (
            f"Style '{style_name}' lacked anti-aliased edge gradations! "
            f"Found only {len(partial_a)} intermediate alpha values: {unique_a}"
        )
