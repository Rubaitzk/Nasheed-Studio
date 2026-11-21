"""
Lightweight interface particle overlay widget for Nasheed Studio preview area.

Features:
- Completely mouse-transparent (WA_TransparentForMouseEvents) so clicks pass through to transport and canvas.
- Configurable color, speed (1-5), and ON/OFF state.
- Zero CPU usage when disabled (QTimer is completely stopped).
- Auto-pause during video export and window minimization.
"""

from __future__ import annotations

import random
from typing import List, Tuple, Union
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "radius", "base_alpha")

    def __init__(self, w: int, h: int, speed_factor: float = 1.0):
        self.x = random.uniform(0, max(10, w))
        self.y = random.uniform(0, max(10, h))
        angle = random.uniform(0, 6.28318)
        speed = random.uniform(0.3, 1.2) * speed_factor
        self.vx = math_cos(angle) * speed
        self.vy = math_sin(angle) * speed - 0.2  # subtle upward drift
        self.radius = random.uniform(2.0, 5.0)
        self.base_alpha = random.uniform(0.3, 0.8)


import math

math_cos = math.cos
math_sin = math.sin


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
        self._num_particles: int = 40

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
            angle = random.uniform(0, 6.28318)
            spd = random.uniform(0.3, 1.2) * sm
            p.vx = math_cos(angle) * spd
            p.vy = math_sin(angle) * spd - (0.2 * sm)

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

        for p in self._particles:
            p.x += p.vx
            p.y += p.vy

            # Boundary wrap
            if p.x < -10:
                p.x = w + 5
            elif p.x > w + 10:
                p.x = -5

            if p.y < -10:
                p.y = h + 5
            elif p.y > h + 10:
                p.y = -5

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
            alpha = int(p.base_alpha * 220)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(r, g, b, alpha))
            painter.drawEllipse(int(p.x), int(p.y), int(p.radius * 2), int(p.radius * 2))

        painter.end()
