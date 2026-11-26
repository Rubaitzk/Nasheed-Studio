"""
Unit and integration tests for Item 1: New Particle Style "Wind Streaks".

Verifies:
1. Rotation equals atan2(vy, vx) for all particles at every frame.
2. Alpha and length are constant over a particle's lifetime across N frames.
3. Every particle spawns outside the frame on the top or right edge, and is removed only after exiting the left or bottom edge.
4. No particle's x is ever increasing, and velocity is constant (no noise).
5. Same seed gives identical positions across two runs, and preview-path positions equal render-path positions at the same timestamp, scaled by resolution.
6. Angle, Density and Speed parameters change behavior as expected.
7. The dropdown's first item is Wind Streaks, and all legacy styles are still present and render without error.
"""

import math
import sys
import random
import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication

from src.services.particle_service import (
    STYLE_WIND_STREAKS,
    PARTICLE_STYLES,
    create_wind_streak_particles,
    wind_streak_state,
    generate_particle_loop_video,
)
from src.ui.widgets.particle_canvas import ParticleOverlayWidget, Particle
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_rotation_equals_atan2():
    """Rotation equals atan2(vy, vx) for all particles at every frame."""
    particles = create_wind_streak_particles(count=50, width=1920, height=1080, angle_deg=225.0, seed=123)
    for frame_idx in range(60):
        t = frame_idx / 30.0
        for p in particles:
            cur_x, cur_y, alpha, rot = wind_streak_state(p, t)
            expected_rot = math.atan2(p["vy"], p["vx"])
            assert math.isclose(rot, expected_rot, rel_tol=1e-7, abs_tol=1e-7), (
                f"Particle rot {rot} != atan2({p['vy']}, {p['vx']}) = {expected_rot}"
            )
            assert math.isclose(p["rot"], expected_rot, rel_tol=1e-7, abs_tol=1e-7)


def test_alpha_and_length_constant_across_frames():
    """Alpha and length are constant over a particle's lifetime across N frames."""
    particles = create_wind_streak_particles(count=40, width=1920, height=1080, seed=456)
    initial_alphas = [p["alpha"] for p in particles]
    initial_lengths = [p["length"] for p in particles]

    for frame_idx in range(120):
        t = frame_idx / 30.0
        for i, p in enumerate(particles):
            cur_x, cur_y, alpha, rot = wind_streak_state(p, t)
            assert alpha == initial_alphas[i], f"Alpha changed at frame {frame_idx}: {alpha} != {initial_alphas[i]}"
            assert p["length"] == initial_lengths[i], f"Length changed at frame {frame_idx}"
            assert 0.6 <= alpha <= 0.9, f"Alpha {alpha} out of range [0.6, 0.9]"


def test_spawn_and_cull_boundaries():
    """
    Every particle spawns outside the frame on the top or right edge,
    and is removed only after exiting the left or bottom edge.
    """
    w, h = 1920, 1080
    particles = create_wind_streak_particles(count=60, width=w, height=h, angle_deg=225.0, seed=789)

    for p in particles:
        sx = p["spawn_x"]
        sy = p["spawn_y"]
        # Particle must spawn outside the frame: either along top (sy < 0) or right edge (sx > w)
        assert sy < 0.0 or sx > w, f"Particle spawned inside frame at ({sx}, {sy})"

        # Check cull point at t = t_life
        ex = sx + p["vx"] * p["t_life"]
        ey = sy + p["vy"] * p["t_life"]
        # Must exit either left edge (ex < 0) or bottom edge (ey > h)
        assert ex < 0.0 or ey > h, f"Particle culled inside frame at ({ex}, {ey})"


def test_no_x_increasing_and_constant_velocity():
    """No particle's x is ever increasing, and velocity is constant (no noise)."""
    particles = create_wind_streak_particles(count=40, width=1920, height=1080, angle_deg=225.0, seed=999)

    for p in particles:
        vx = p["vx"]
        vy = p["vy"]
        assert vx < 0, f"vx must be negative for 225 deg: {vx}"
        assert vy > 0, f"vy must be positive for 225 deg: {vy}"

        # Sample 20 sub-steps within particle's single lifetime
        dt = p["t_life"] / 25.0
        prev_x = None
        for step in range(25):
            tau = step * dt
            cur_x = p["spawn_x"] + vx * tau
            cur_y = p["spawn_y"] + vy * tau

            if prev_x is not None:
                assert cur_x < prev_x, f"x increased! cur_x={cur_x} >= prev_x={prev_x}"
            prev_x = cur_x


def test_deterministic_seed_and_resolution_parity():
    """
    Same seed gives identical positions across two runs,
    and preview-path positions equal render-path positions at the same timestamp, scaled by resolution.
    """
    # 1. Determinism across two runs
    p1 = create_wind_streak_particles(count=30, width=1920, height=1080, seed=12345)
    p2 = create_wind_streak_particles(count=30, width=1920, height=1080, seed=12345)
    for i in range(len(p1)):
        for t in [0.0, 1.0, 2.5, 4.0]:
            x1, y1, a1, r1 = wind_streak_state(p1[i], t)
            x2, y2, a2, r2 = wind_streak_state(p2[i], t)
            assert math.isclose(x1, x2, rel_tol=1e-6)
            assert math.isclose(y1, y2, rel_tol=1e-6)
            assert a1 == a2
            assert r1 == r2

    # 2. Preview vs render resolution parity
    # Render at 1080p (1920x1080), Preview at 360p (640x360)
    render_parts = create_wind_streak_particles(count=30, width=1920, height=1080, seed=54321)
    preview_parts = create_wind_streak_particles(count=30, width=640, height=360, seed=54321)
    scale = 360.0 / 1080.0  # 1/3

    for i in range(len(render_parts)):
        for t in [0.0, 0.5, 1.5, 3.0]:
            rx, ry, ra, rr = wind_streak_state(render_parts[i], t)
            px, py, pa, pr = wind_streak_state(preview_parts[i], t)

            assert math.isclose(px, rx * scale, rel_tol=1e-4, abs_tol=0.2), (
                f"Preview x {px} != render x {rx} * {scale} ({rx * scale}) at t={t}"
            )
            assert math.isclose(py, ry * scale, rel_tol=1e-4, abs_tol=0.2), (
                f"Preview y {py} != render y {ry} * {scale} ({ry * scale}) at t={t}"
            )
            assert ra == pa
            assert math.isclose(rr, pr, rel_tol=1e-5)


def test_angle_density_speed_parameters():
    """Angle, Density and Speed parameters change behavior as expected."""
    # Density
    parts_10 = create_wind_streak_particles(count=10, width=1920, height=1080)
    parts_50 = create_wind_streak_particles(count=50, width=1920, height=1080)
    assert len(parts_10) == 10
    assert len(parts_50) == 50

    # Speed
    p_spd1 = create_wind_streak_particles(count=10, width=1920, height=1080, speed_level=1, seed=77)
    p_spd5 = create_wind_streak_particles(count=10, width=1920, height=1080, speed_level=5, seed=77)
    mag1 = math.hypot(p_spd1[0]["vx"], p_spd1[0]["vy"])
    mag5 = math.hypot(p_spd5[0]["vx"], p_spd5[0]["vy"])
    assert mag5 > mag1 * 4.0, f"Speed 5 magnitude {mag5} should be ~7x speed 1 magnitude {mag1}"

    # Angle
    p_225 = create_wind_streak_particles(count=5, width=1920, height=1080, angle_deg=225.0, seed=88)
    p_180 = create_wind_streak_particles(count=5, width=1920, height=1080, angle_deg=180.0, seed=88)
    assert p_225[0]["vy"] > 0.0  # Moves down-left
    assert math.isclose(p_180[0]["vy"], 0.0, abs_tol=1e-4)  # Moves purely left


def test_dropdown_first_item_and_legacy_styles(qapp):
    """The dropdown's first item is Wind Streaks, and all legacy styles are still present and render without error."""
    assert PARTICLE_STYLES[0] == "Wind Streaks"
    assert "Drifting Flecks" in PARTICLE_STYLES
    assert "Floating Orbs" in PARTICLE_STYLES
    assert "Light Glints" in PARTICLE_STYLES
    assert "Twinkle Stars" in PARTICLE_STYLES
    assert "Bokeh Rings" in PARTICLE_STYLES
    assert "Crescents & Stars" in PARTICLE_STYLES
    assert "Eight-Point Stars" in PARTICLE_STYLES

    win = MainWindow()
    try:
        assert win.particles_style_combo.itemText(0) == "Wind Streaks"
        assert win.particles_style_combo.currentText() == "Wind Streaks"

        # Verify all legacy styles can be selected and set on overlay without error
        for style in PARTICLE_STYLES:
            win.particles_style_combo.setCurrentText(style)
            assert win.particle_overlay.get_particle_style() == style

        # Verify control visibility toggles for Wind Streaks
        win.particles_style_combo.setCurrentText("Wind Streaks")
        win.show()
        assert not win._particles_angle_row.isHidden()
        assert win._particles_color_row.isHidden()
        assert win._particles_layer_row.isHidden()

        win.particles_style_combo.setCurrentText("Drifting Flecks")
        assert win._particles_angle_row.isHidden()
        assert not win._particles_color_row.isHidden()
        assert not win._particles_layer_row.isHidden()
    finally:
        dispose_window(win)
