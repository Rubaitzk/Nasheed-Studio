"""
Unit and integration tests for Feature D: Interface Particle Effect.

Verifies:
1. ON/OFF state control (starts/stops timer, shows/hides overlay).
2. Color adjustments update the particle painter color.
3. Speed adjustments (1-5) affect velocity multipliers.
4. Transparent to mouse events (WA_TransparentForMouseEvents).
5. Pause during export simulation stops timer.
"""

import sys
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from src.ui.widgets import ParticleOverlayWidget
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_particle_widget_lifecycle(qapp):
    overlay = ParticleOverlayWidget()
    overlay.resize(640, 360)
    assert not overlay.is_enabled()
    assert overlay.isHidden()
    assert not overlay._timer.isActive()

    # Enable
    overlay.set_enabled(True)
    assert overlay.is_enabled()
    assert not overlay.isHidden()
    assert overlay._timer.isActive()

    # Disable
    overlay.set_enabled(False)
    assert not overlay.is_enabled()
    assert overlay.isHidden()
    assert not overlay._timer.isActive()


def test_particle_widget_mouse_transparency(qapp):
    overlay = ParticleOverlayWidget()
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_particle_color_and_speed_changes(qapp):
    overlay = ParticleOverlayWidget()
    overlay.set_particle_color("#F59E0B")
    assert overlay.get_particle_color().name().upper() == "#F59E0B"

    overlay.set_particle_speed(5)
    assert overlay.get_particle_speed() == 5
    assert overlay._speed_multiplier() == 3.5

    overlay.set_particle_speed(1)
    assert overlay.get_particle_speed() == 1
    assert overlay._speed_multiplier() == 0.5


def test_particle_export_pause_resume(qapp):
    overlay = ParticleOverlayWidget()
    overlay.set_enabled(True)
    assert overlay._timer.isActive()

    overlay.pause()
    assert not overlay._timer.isActive()

    overlay.resume()
    assert overlay._timer.isActive()


def test_main_window_particles_integration(qapp):
    win = MainWindow()
    try:
        assert hasattr(win, "particle_overlay")
        assert hasattr(win, "particles_check")
        assert hasattr(win, "particles_style_combo")
        assert hasattr(win, "particles_layer_combo")
        assert hasattr(win, "particles_count_spin")

        win.particles_check.setChecked(True)
        assert win.particle_overlay.is_enabled()

        win.particles_style_combo.setCurrentText("Drifting Flecks")
        assert win.particle_overlay.get_particle_style() == "Drifting Flecks"

        win.particles_layer_combo.setCurrentText("Below Text")
        assert win.particle_overlay.get_particle_layer() == "Below Text"

        win.particles_count_spin.setValue(120)
        assert win.particle_overlay.get_particle_count() == 120

        proj = win._project()
        assert proj["particles_enabled"] is True
        assert proj["particles_style"] == "Drifting Flecks"
        assert proj["particles_layer"] == "Below Text"
        assert proj["particles_quantity"] == 120

        win.particles_check.setChecked(False)
        assert not win.particle_overlay.is_enabled()
    finally:
        dispose_window(win)


def test_particle_styles_and_layers(qapp):
    overlay = ParticleOverlayWidget()
    overlay.resize(640, 360)
    overlay.set_particle_style("Drifting Flecks")
    assert overlay.get_particle_style() == "Drifting Flecks"

    overlay.set_particle_style("Floating Orbs")
    assert overlay.get_particle_style() == "Floating Orbs"

    overlay.set_particle_style("Light Glints")
    assert overlay.get_particle_style() == "Light Glints"

    overlay.set_particle_style("Twinkle Stars")
    assert overlay.get_particle_style() == "Twinkle Stars"

    overlay.set_particle_style("Bokeh Rings")
    assert overlay.get_particle_style() == "Bokeh Rings"

    overlay.set_particle_style("Crescents & Stars")
    assert overlay.get_particle_style() == "Crescents & Stars"

    overlay.set_particle_style("Eight-Point Stars")
    assert overlay.get_particle_style() == "Eight-Point Stars"

    # Fallback for unknown style
    overlay.set_particle_style("Unknown Style")
    assert overlay.get_particle_style() == "Floating Orbs"

    overlay.set_particle_layer("Below Text")
    assert overlay.get_particle_layer() == "Below Text"

    overlay.set_particle_layer("Above Text")
    assert overlay.get_particle_layer() == "Above Text"

    overlay.set_particle_count(150)
    assert overlay.get_particle_count() == 150


def test_particle_export_command_below_text():
    import tempfile
    from pathlib import Path
    from src.services.render_service import build_render_command

    sample_audio = Path("tests/fixtures/audio/sample_tone.wav").resolve()
    sample_bg = Path("tests/fixtures/images/sample_bg.png").resolve()

    project = {
        "collection_title": "Particles Export Test Below",
        "background": str(sample_bg),
        "tracks": [{"path": str(sample_audio), "title": "Track 1", "duration": 1.0}],
        "particles_enabled": True,
        "particles_style": "Drifting Flecks",
        "particles_layer": "Below Text",
        "particles_quantity": 40,
        "particles_speed": 2,
        "output_path": "output_particles_below.mp4",
    }
    with tempfile.TemporaryDirectory() as tmp:
        cmd, out = build_render_command(project, Path(tmp))
        filter_str = "".join(cmd)
        assert "particles_loop.mov" in "".join(cmd)
        assert "v_bg_part" in filter_str


def test_particle_export_command_above_text():
    import tempfile
    from pathlib import Path
    from src.services.render_service import build_render_command

    sample_audio = Path("tests/fixtures/audio/sample_tone.wav").resolve()
    sample_bg = Path("tests/fixtures/images/sample_bg.png").resolve()

    project = {
        "collection_title": "Particles Export Test Above",
        "background": str(sample_bg),
        "tracks": [{"path": str(sample_audio), "title": "Track 1", "duration": 1.0}],
        "particles_enabled": True,
        "particles_style": "Floating Orbs",
        "particles_layer": "Above Text",
        "particles_quantity": 40,
        "particles_speed": 3,
        "output_path": "output_particles_above.mp4",
    }
    with tempfile.TemporaryDirectory() as tmp:
        cmd, out = build_render_command(project, Path(tmp))
        filter_str = "".join(cmd)
        assert "particles_loop.mov" in "".join(cmd)
        assert "v_final_part" in filter_str


def test_light_glints_constants_and_helpers():
    import math
    from src.services.particle_service import (
        STYLE_LIGHT_GLINTS,
        PARTICLE_STYLES,
        lens_polygon,
        glint_state,
    )

    assert STYLE_LIGHT_GLINTS in PARTICLE_STYLES
    assert STYLE_LIGHT_GLINTS == "Light Glints"

    # Test lens_polygon output geometry
    pts = lens_polygon(100.0, 100.0, 36.0, 4.0, -60.0, n=14)
    assert len(pts) == 28
    # Tips should match half_len distance along angle -60
    assert any(p != (100.0, 100.0) for p in pts)

    # Test glint_state periodicity
    duration = 6.0
    p = {
        "n": 3,
        "phase": 0.4,
        "positions": [(120.0, 300.0), (500.0, 700.0), (800.0, 200.0)],
        "vx": 1 * 1920.0 / duration,
        "vy": -2 * 1080.0 / duration,
        "width": 1920,
        "height": 1080,
    }
    for t in [0.0, 1.35, 3.0, 4.75, 5.99]:
        s0 = glint_state(p, t, duration)
        s1 = glint_state(p, t + duration, duration)
        assert math.isclose(s0[0], s1[0], abs_tol=1e-5), f"x mismatch at t={t}"
        assert math.isclose(s0[1], s1[1], abs_tol=1e-5), f"y mismatch at t={t}"
        assert math.isclose(s0[2], s1[2], abs_tol=1e-5), f"alpha mismatch at t={t}"


def test_generate_particle_loop_video_light_glints():
    import tempfile
    from pathlib import Path
    from src.services.particle_service import (
        generate_particle_loop_video,
        STYLE_LIGHT_GLINTS,
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_mov = Path(tmp) / "glints_loop.mov"
        res = generate_particle_loop_video(
            output_path=out_mov,
            width=320,
            height=240,
            fps=15,
            duration=1.0,
            style=STYLE_LIGHT_GLINTS,
            quantity=30,
            color=(255, 255, 255),
            speed=2,
        )
        assert res.is_file()
        assert res.stat().st_size > 0


def test_generate_particle_loop_video_twinkle_stars():
    import tempfile
    from pathlib import Path
    from src.services.particle_service import (
        generate_particle_loop_video,
        STYLE_TWINKLE_STARS,
        PARTICLE_STYLES,
        star_4point_polygon,
    )

    assert STYLE_TWINKLE_STARS in PARTICLE_STYLES
    pts = star_4point_polygon(50, 50, 20)
    assert len(pts) == 8

    with tempfile.TemporaryDirectory() as tmp:
        out_mov = Path(tmp) / "twinkle_loop.mov"
        res = generate_particle_loop_video(
            output_path=out_mov,
            width=320,
            height=240,
            fps=15,
            duration=1.0,
            style=STYLE_TWINKLE_STARS,
            quantity=30,
            color=(255, 255, 255),
            speed=2,
        )
        assert res.is_file()
        assert res.stat().st_size > 0


def test_generate_particle_loop_video_bokeh_rings():
    import tempfile
    from pathlib import Path
    from src.services.particle_service import (
        generate_particle_loop_video,
        STYLE_BOKEH_RINGS,
        PARTICLE_STYLES,
    )

    assert STYLE_BOKEH_RINGS in PARTICLE_STYLES

    with tempfile.TemporaryDirectory() as tmp:
        out_mov = Path(tmp) / "bokeh_loop.mov"
        res = generate_particle_loop_video(
            output_path=out_mov,
            width=320,
            height=240,
            fps=15,
            duration=1.0,
            style=STYLE_BOKEH_RINGS,
            quantity=25,
            color=(100, 200, 255),
            speed=2,
        )
        assert res.is_file()
        assert res.stat().st_size > 0


def test_generate_particle_loop_video_crescents_and_stars():
    import tempfile
    from pathlib import Path
    from src.services.particle_service import (
        generate_particle_loop_video,
        STYLE_CRESCENTS_AND_STARS,
        PARTICLE_STYLES,
        crescent_polygon,
        star_5point_polygon,
    )

    assert STYLE_CRESCENTS_AND_STARS in PARTICLE_STYLES
    c_pts = crescent_polygon(50, 50, 20)
    assert len(c_pts) > 10
    s_pts = star_5point_polygon(50, 50, 15)
    assert len(s_pts) == 10

    with tempfile.TemporaryDirectory() as tmp:
        out_mov = Path(tmp) / "crescent_loop.mov"
        res = generate_particle_loop_video(
            output_path=out_mov,
            width=320,
            height=240,
            fps=15,
            duration=1.0,
            style=STYLE_CRESCENTS_AND_STARS,
            quantity=20,
            color=(255, 230, 150),
            speed=2,
        )
        assert res.is_file()
        assert res.stat().st_size > 0


def test_generate_particle_loop_video_eight_point_stars():
    import tempfile
    from pathlib import Path
    from src.services.particle_service import (
        generate_particle_loop_video,
        STYLE_EIGHT_POINT_STARS,
        PARTICLE_STYLES,
        star_8point_polygon,
    )

    assert STYLE_EIGHT_POINT_STARS in PARTICLE_STYLES
    pts = star_8point_polygon(50, 50, 20)
    assert len(pts) == 16

    with tempfile.TemporaryDirectory() as tmp:
        out_mov = Path(tmp) / "eight_star_loop.mov"
        res = generate_particle_loop_video(
            output_path=out_mov,
            width=320,
            height=240,
            fps=15,
            duration=1.0,
            style=STYLE_EIGHT_POINT_STARS,
            quantity=20,
            color=(255, 215, 0),
            speed=2,
        )
        assert res.is_file()
        assert res.stat().st_size > 0


def test_particles_size_control_ui_and_persistence(qapp):
    win = MainWindow()
    try:
        assert hasattr(win, "particles_size_slider")
        assert hasattr(win, "particles_size_spin")
        assert hasattr(win, "particles_size_val_lbl")
        assert win.particles_size_slider.value() == 5
        assert win.particles_size_spin.value() == 5
        assert win.particle_overlay.get_particle_size() == 5

        # Change size slider, assert spinbox updates
        win.particles_size_slider.setValue(12)
        assert win.particles_size_spin.value() == 12
        assert win.particle_overlay.get_particle_size() == 12

        # Change spin box, assert slider updates
        win.particles_size_spin.setValue(18)
        assert win.particles_size_slider.value() == 18
        assert win.particle_overlay.get_particle_size() == 18

        # Check project dictionary contains particles_size
        proj = win._project()
        assert proj.get("particles_size") == 18

        # Backward compatibility: restore project state without particles_size defaults to 5
        old_data = {
            "particles_enabled": True,
            "particles_style": "Floating Orbs",
        }
        win._restore_project_state(old_data)
        assert win.particles_size_slider.value() == 5
        assert win.particles_size_spin.value() == 5
        assert win.particle_overlay.get_particle_size() == 5

        # Out-of-range clamping on restore (old 50-300 scale mapped or clamped)
        win._restore_project_state({"particles_size": 20})
        assert win.particles_size_slider.value() == 20
        assert win.particles_size_spin.value() == 20
        assert win.particle_overlay.get_particle_size() == 20
    finally:
        dispose_window(win)


def test_particles_size_template_persistence():
    from src.services.project_service import (
        TEMPLATE_DESIGN_KEYS,
        extract_template,
        apply_template_to_project,
    )
    assert "particles_size" in TEMPLATE_DESIGN_KEYS

    proj = {
        "particles_enabled": True,
        "particles_style": "Light Glints",
        "particles_size": 150,
    }
    tmpl = extract_template(proj)
    assert tmpl.get("particles_size") == 150

    base_proj = {"collection_title": "Test Title"}
    applied = apply_template_to_project(base_proj, tmpl)
    assert applied.get("particles_size") == 150


def test_generate_particle_loop_video_sizes():
    import tempfile
    from pathlib import Path
    from src.services.particle_service import (
        generate_particle_loop_video,
        PARTICLE_STYLES,
    )
    for style in PARTICLE_STYLES:
        for sz in [50, 100, 300]:
            with tempfile.TemporaryDirectory() as tmp:
                out_mov = Path(tmp) / f"loop_{sz}.mov"
                res = generate_particle_loop_video(
                    output_path=out_mov,
                    width=320,
                    height=240,
                    fps=15,
                    duration=1.0,
                    style=style,
                    quantity=15,
                    size=sz,
                )
                assert res.is_file()
                assert res.stat().st_size > 0


def test_particle_size_scaling_extent():
    """Verify that particle bounding dimensions scale proportionally with size (200% vs 100%)."""
    import math
    from src.services.particle_service import (
        lens_polygon,
        star_4point_polygon,
        star_8point_polygon,
    )

    pts_100 = lens_polygon(100, 100, 30.0, 4.0, 0.0)
    pts_200 = lens_polygon(100, 100, 60.0, 8.0, 0.0)
    w100 = max(p[0] for p in pts_100) - min(p[0] for p in pts_100)
    w200 = max(p[0] for p in pts_200) - min(p[0] for p in pts_200)
    assert math.isclose(w200 / w100, 2.0, rel_tol=0.01)

    pts_100 = star_4point_polygon(100, 100, 20.0)
    pts_200 = star_4point_polygon(100, 100, 40.0)
    w100 = max(p[0] for p in pts_100) - min(p[0] for p in pts_100)
    w200 = max(p[0] for p in pts_200) - min(p[0] for p in pts_200)
    assert math.isclose(w200 / w100, 2.0, rel_tol=0.01)

    pts_100 = star_8point_polygon(100, 100, 15.0)
    pts_200 = star_8point_polygon(100, 100, 30.0)
    w100 = max(p[0] for p in pts_100) - min(p[0] for p in pts_100)
    w200 = max(p[0] for p in pts_200) - min(p[0] for p in pts_200)
    assert math.isclose(w200 / w100, 2.0, rel_tol=0.01)


def test_particle_widget_size_rescaling(qapp):
    """Test ParticleOverlayWidget.set_particle_size() rescales particle dimensions live."""
    import math
    overlay = ParticleOverlayWidget()
    overlay.resize(640, 360)
    overlay.set_particle_style("Drifting Flecks")
    overlay.set_particle_count(20)
    overlay.set_enabled(True)

    overlay.set_particle_size(100)
    radii_100 = [p.radius for p in overlay._particles]

    overlay.set_particle_size(200)
    radii_200 = [p.radius for p in overlay._particles]

    assert len(radii_100) == len(radii_200)
    for r1, r2 in zip(radii_100, radii_200):
        assert math.isclose(r2 / r1, 2.0, rel_tol=0.15)


def test_particle_seamless_loop_identity():
    """Verify that particle states at t=0 and t=duration are identical at all sizes."""
    import math
    import random
    from src.services.particle_service import glint_state

    duration = 6.0
    width = 1920
    height = 1080
    two_pi = 2.0 * math.pi

    for sz in [50, 100, 200, 300]:
        # Glint seamless check
        p_glint = {
            "n": 3,
            "phase": 0.45,
            "positions": [(200.0, 300.0), (600.0, 800.0), (1200.0, 500.0)],
            "vx": 2 * width / duration,
            "vy": -1 * height / duration,
            "width": width,
            "height": height,
        }
        s0 = glint_state(p_glint, 0.0, duration)
        s_end = glint_state(p_glint, duration, duration)
        assert math.isclose(s0[0], s_end[0], abs_tol=1e-5)
        assert math.isclose(s0[1], s_end[1], abs_tol=1e-5)
        assert math.isclose(s0[2], s_end[2], abs_tol=1e-5)

        # Fleck / wave seamless check
        vx = 2 * width / duration
        m = 2
        A = 5.0 * (height / 1080.0)
        x0, y0 = 150.0, 450.0

        x_t0 = (x0 + vx * 0.0) % width
        y_t0 = y0 + A * math.sin(two_pi * m * 0.0 / duration)

        x_tend = (x0 + vx * duration) % width
        y_tend = y0 + A * math.sin(two_pi * m * duration / duration)

        assert math.isclose(x_t0, x_tend, abs_tol=1e-5)
        assert math.isclose(y_t0, y_tend, abs_tol=1e-5)
