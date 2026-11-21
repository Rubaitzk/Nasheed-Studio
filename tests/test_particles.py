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

        win.particles_check.setChecked(True)
        assert win.particle_overlay.is_enabled()

        proj = win._project()
        assert proj["particles_enabled"] is True

        win.particles_check.setChecked(False)
        assert not win.particle_overlay.is_enabled()
    finally:
        dispose_window(win)
