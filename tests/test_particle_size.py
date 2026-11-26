import sys
import math
import random
import pytest
from PySide6.QtWidgets import QApplication

from src.services.particle_service import (
    PARTICLE_STYLES,
    create_wind_streak_particles,
    generate_particle_loop_video,
)
from src.ui.widgets.particle_canvas import ParticleOverlayWidget, Particle
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _get_particle_dimension(particle: Particle) -> float:
    """Return the primary geometric dimension of a particle."""
    if hasattr(particle, "thickness") and particle.thickness:
        return particle.thickness
    if hasattr(particle, "length") and particle.length:
        return particle.length
    return particle.radius


def test_particle_dimensions_scale_linearly_for_all_styles():
    """For each style, rendered particle pixel dimensions scale linearly with the size setting."""
    for style in PARTICLE_STYLES:
        sizes = [1, 2, 5, 10, 15, 20]
        dims = []
        for s in sizes:
            p = Particle(
                1920,
                1080,
                style,
                1.0,
                size_factor=s / 5.0,
                rng=random.Random(42),
                angle=225.0,
            )
            dims.append(_get_particle_dimension(p))

        base_dim = dims[2]  # size = 5 (factor 1.0)
        assert base_dim > 0, f"Base dimension for {style} must be positive"

        for s, d in zip(sizes, dims):
            expected = base_dim * (s / 5.0)
            assert math.isclose(d, expected, rel_tol=1e-5), (
                f"Style {style} size {s} dimension {d} does not scale linearly (expected {expected})"
            )


def test_preview_vs_render_particle_size_ratio_within_5_percent():
    """
    Preview vs. render particle size ratio relative to canvas height is within 5%
    at 1080p and at a smaller preview size (e.g. 360p and 540p).
    """
    for preview_h in [360, 480, 540, 720]:
        preview_w = int(preview_h * 16 / 9)
        for style in PARTICLE_STYLES:
            for size_setting in [1, 3, 5, 10, 20]:
                factor = size_setting / 5.0
                p_prev = Particle(
                    preview_w,
                    preview_h,
                    style,
                    1.0,
                    size_factor=factor,
                    rng=random.Random(123),
                    angle=225.0,
                )
                p_rend = Particle(
                    1920,
                    1080,
                    style,
                    1.0,
                    size_factor=factor,
                    rng=random.Random(123),
                    angle=225.0,
                )

                d_prev = _get_particle_dimension(p_prev)
                d_rend = _get_particle_dimension(p_rend)

                ratio_prev = d_prev / float(preview_h)
                ratio_rend = d_rend / 1080.0

                diff_pct = abs(ratio_prev - ratio_rend) / ratio_rend * 100.0
                assert diff_pct < 5.0, (
                    f"Style {style} at size {size_setting} preview {preview_h}p vs 1080p "
                    f"ratio difference is {diff_pct:.2f}% (exceeds 5% tolerance)"
                )


def test_slider_and_spin_box_sync_and_defaults(qapp):
    """The slider and spin box stay in sync and have a small sensible default (5)."""
    win = MainWindow()
    try:
        assert hasattr(win, "particles_size_slider")
        assert hasattr(win, "particles_size_spin")

        # Range and default checks
        assert win.particles_size_slider.minimum() == 1
        assert win.particles_size_slider.maximum() == 20
        assert win.particles_size_spin.minimum() == 1
        assert win.particles_size_spin.maximum() == 20
        assert win.particles_size_slider.value() == 5
        assert win.particles_size_spin.value() == 5
        assert win.particle_overlay.get_particle_size() == 5

        # Move slider -> spin box must follow
        win.particles_size_slider.setValue(14)
        assert win.particles_size_spin.value() == 14
        assert win.particle_overlay.get_particle_size() == 14

        # Move spin box -> slider must follow
        win.particles_size_spin.setValue(2)
        assert win.particles_size_slider.value() == 2
        assert win.particle_overlay.get_particle_size() == 2
    finally:
        dispose_window(win)


def test_save_load_round_trip_and_legacy_default(qapp):
    """A save/load round trip preserves the value, and a legacy project file without the field loads with default."""
    win = MainWindow()
    try:
        win.particles_size_spin.setValue(13)
        proj_dict = win._project()
        assert proj_dict["particles_size"] == 13

        # Simulate loading into another state
        win.particles_size_spin.setValue(2)
        win._restore_project_state(proj_dict)
        assert win.particles_size_spin.value() == 13
        assert win.particles_size_slider.value() == 13

        # Legacy project without particles_size
        legacy_dict = {
            "collection_title": "Legacy Project",
            "particles_enabled": True,
            "particles_style": "Drifting Flecks",
        }
        win._restore_project_state(legacy_dict)
        assert win.particles_size_spin.value() == 5
        assert win.particles_size_slider.value() == 5
        assert win.particle_overlay.get_particle_size() == 5
    finally:
        dispose_window(win)
