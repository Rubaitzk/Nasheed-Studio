"""
Lightweight interface particle overlay widget for Nasheed Studio preview area.

Features:
- Completely mouse-transparent (WA_TransparentForMouseEvents) so clicks pass through to transport and canvas.
- Configurable color, speed (1-5), and ON/OFF state.
- Zero CPU usage when disabled (QTimer is completely stopped).
- Auto-pause during video export and window minimization.
"""

from __future__ import annotations

import math
import random
from typing import List, Tuple, Union
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

math_sin = math.sin


class Particle:
    __slots__ = (
        "x", "y", "speed_y", "sway_phase", "sway_speed",
        "sway_amp", "radius", "base_alpha", "depth"
    )

    def __init__(self, w: int, h: int, speed_factor: float = 1.0):
        self.depth = random.uniform(0.3, 1.0)
        self.x = random.uniform(0, max(10, w))
        self.y = random.uniform(0, max(10, h))
        # Atmospheric depth: closer particles (depth -> 1) fall faster and are larger/brighter
        self.speed_y = (0.4 + self.depth * 0.9) * speed_factor
        self.sway_phase = random.uniform(0, 6.28318)
        self.sway_speed = random.uniform(0.015, 0.045)
        self.sway_amp = (0.3 + self.depth * 0.8)
        self.radius = 1.2 + self.depth * 2.5
        self.base_alpha = 0.2 + self.depth * 0.55


class ParticleOverlayWidget(QWidget):
    """
    Transparent visual particle canvas overlay that floats over the video preview.
    Does not capture or block mouse events.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._enabled: bool = False
        self._is_paused: bool = False
        self._speed_level: int = 2  # 1 to 5
        self._color: QColor = QColor(56, 189, 248)  # Default cyan accent

        self._particles: List[Particle] = []
        self._num_particles: int = 55

        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 FPS
        self._timer.timeout.connect(self._update_particles)

        self.hide()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable particle rendering."""
        self._enabled = bool(enabled)
        if self._enabled:
            self._ensure_particles()
            self.show()
            self.raise_()
            if not self._is_paused:
                self._timer.start()
        else:
            self._timer.stop()
            self.hide()
        self.update()

    def is_enabled(self) -> bool:
        return self._enabled

    def pause(self) -> None:
        """Temporarily pause animation (e.g. during video export)."""
        self._is_paused = True
        self._timer.stop()

    def resume(self) -> None:
        """Resume animation if enabled."""
        self._is_paused = False
        if self._enabled:
            self._timer.start()

    def set_particle_color(self, color: Union[QColor, str, Tuple[int, int, int]]) -> None:
        """Set particle primary color."""
        if isinstance(color, QColor):
            self._color = color
        elif isinstance(color, (tuple, list)) and len(color) >= 3:
            self._color = QColor(int(color[0]), int(color[1]), int(color[2]))
        elif isinstance(color, str):
            self._color = QColor(color)
        self.update()

    def get_particle_color(self) -> QColor:
        return self._color

    def set_particle_speed(self, speed: int) -> None:
        """Set animation speed factor (1 to 5)."""
        self._speed_level = max(1, min(5, int(speed)))
        self._reseed_velocities()

    def get_particle_speed(self) -> int:
        return self._speed_level

    def _speed_multiplier(self) -> float:
        # Scale: 1 -> 0.5x, 2 -> 1.0x, 3 -> 1.6x, 4 -> 2.4x, 5 -> 3.5x
        rates = {1: 0.5, 2: 1.0, 3: 1.6, 4: 2.4, 5: 3.5}
        return rates.get(self._speed_level, 1.0)

    def _ensure_particles(self) -> None:
        w = max(100, self.width())
        h = max(100, self.height())
        sm = self._speed_multiplier()
        if len(self._particles) != self._num_particles:
            self._particles = [Particle(w, h, sm) for _ in range(self._num_particles)]

    def _reseed_velocities(self) -> None:
        sm = self._speed_multiplier()
        for p in self._particles:
            p.speed_y = (0.4 + p.depth * 0.9) * sm

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._ensure_particles()

    def _update_particles(self) -> None:
        if not self._enabled or self._is_paused:
            return

        w = self.width()
        h = self.height()
        if w <= 10 or h <= 10:
            return

        sm = self._speed_multiplier()
        for p in self._particles:
            p.sway_phase += p.sway_speed * sm
            dx = math_sin(p.sway_phase) * p.sway_amp * sm
            dy = p.speed_y * sm
            p.x += dx
            p.y += dy

            # Seamless boundary wrapping
            if p.y > h + 15:
                p.y = -10
                p.x = random.uniform(0, w)
            elif p.y < -20:
                p.y = h + 10

            if p.x < -20:
                p.x = w + 10
            elif p.x > w + 20:
                p.x = -10

        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._enabled or not self._particles:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        r = self._color.red()
        g = self._color.green()
        b = self._color.blue()

        for p in self._particles:
            alpha = int(p.base_alpha * 230)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(r, g, b, alpha))
            painter.drawEllipse(QPointF(p.x, p.y), p.radius, p.radius)

        painter.end()
