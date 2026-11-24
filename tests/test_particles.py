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
