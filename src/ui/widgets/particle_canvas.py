"""
Lightweight interface particle overlay widget for Nasheed Studio preview area.

Features:
- Completely mouse-transparent (WA_TransparentForMouseEvents) so clicks pass through to transport and canvas.
- Configurable color, speed (1-5), quantity (10-300), style ("Drifting Flecks" or "Floating Orbs"), and layer ("Below Text" or "Above Text").
- Zero CPU usage when disabled (QTimer is completely stopped).
- Auto-pause during video export and window minimization.
- True layer ordering: when set to "Below Text", typography is drawn on top of particles so text remains crisp and readable.
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple, Union
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget

from src.services.particle_service import (
    STYLE_DRIFTING_FLECKS,
    STYLE_FLOATING_ORBS,
    LAYER_BELOW_TEXT,
    LAYER_ABOVE_TEXT,
    _speed_multiplier,
)

math_sin = math.sin


class Particle:
    __slots__ = (
        "x", "y", "base_y", "speed_x", "speed_y", "sway_phase",
        "sway_speed", "sway_amp", "radius", "base_alpha", "depth"
    )

    def __init__(self, w: int, h: int, style: str = STYLE_DRIFTING_FLECKS, speed_factor: float = 1.0):
        self.depth = random.uniform(0.35, 1.0)
        self.x = random.uniform(0, max(10, w))
        self.y = random.uniform(0, max(10, h))
        self.base_y = self.y

        if style == STYLE_DRIFTING_FLECKS:
            # Drifting Flecks: horizontal drift with gentle natural vertical float
            self.radius = 1.0 + self.depth * 1.8
            self.speed_x = (1.5 + self.depth * 2.2) * speed_factor
            self.speed_y = 0.0
            self.sway_phase = random.uniform(0, 6.28318)
            self.sway_speed = random.uniform(0.015, 0.04) * speed_factor
            self.sway_amp = 2.0 + self.depth * 5.0
            self.base_alpha = 0.35 + self.depth * 0.55
        else:
            # Floating Orbs: vertical atmospheric float with sinusoidal sway
            self.radius = 1.5 + self.depth * 3.0
            self.speed_x = 0.0
            self.speed_y = (0.5 + self.depth * 1.0) * speed_factor
            self.sway_phase = random.uniform(0, 6.28318)
            self.sway_speed = random.uniform(0.015, 0.045) * speed_factor
            self.sway_amp = 0.4 + self.depth * 0.9
            self.base_alpha = 0.25 + self.depth * 0.55


class ParticleOverlayWidget(QWidget):
    """
    Visual particle canvas overlay that floats over the video preview.
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
        self._style: str = STYLE_DRIFTING_FLECKS
        self._layer: str = LAYER_BELOW_TEXT
        self._num_particles: int = 80
        self._text_pixmap: Optional[QPixmap] = None

        self._particles: List[Particle] = []

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

    def set_particle_style(self, style: str) -> None:
        """Set particle style: 'Drifting Flecks' or 'Floating Orbs'."""
        self._style = STYLE_DRIFTING_FLECKS if "fleck" in str(style).lower() else STYLE_FLOATING_ORBS
        self._particles.clear()
        self._ensure_particles()
        self.update()

    def get_particle_style(self) -> str:
        return self._style

    def set_particle_layer(self, layer: str) -> None:
        """Set particle layer placement: 'Below Text' or 'Above Text'."""
        self._layer = LAYER_ABOVE_TEXT if "above" in str(layer).lower() else LAYER_BELOW_TEXT
        self.update()

    def get_particle_layer(self) -> str:
        return self._layer

    def set_particle_count(self, count: int) -> None:
        """Set quantity of particles (10 to 300)."""
        self._num_particles = max(10, min(300, int(count)))
        self._particles.clear()
        self._ensure_particles()
        self.update()

    def get_particle_count(self) -> int:
        return self._num_particles

    def set_text_pixmap(self, pixmap: Optional[QPixmap]) -> None:
        """Set foreground text/typography pixmap to render on top when layer is 'Below Text'."""
        self._text_pixmap = pixmap
        self.update()

    def _speed_multiplier(self) -> float:
        return _speed_multiplier(self._speed_level)

    def _ensure_particles(self) -> None:
        w = max(100, self.width())
        h = max(100, self.height())
        sm = self._speed_multiplier()
        if len(self._particles) != self._num_particles:
            self._particles = [Particle(w, h, self._style, sm) for _ in range(self._num_particles)]

    def _reseed_velocities(self) -> None:
        sm = self._speed_multiplier()
        is_flecks = (self._style == STYLE_DRIFTING_FLECKS)
        for p in self._particles:
            if is_flecks:
                p.speed_x = (1.5 + p.depth * 2.2) * sm
                p.sway_speed = random.uniform(0.015, 0.04) * sm
            else:
                p.speed_y = (0.5 + p.depth * 1.0) * sm
                p.sway_speed = random.uniform(0.015, 0.045) * sm

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
        is_flecks = (self._style == STYLE_DRIFTING_FLECKS)

        for p in self._particles:
            if is_flecks:
                p.x += p.speed_x
                p.sway_phase += p.sway_speed
                p.y = p.base_y + math_sin(p.sway_phase) * p.sway_amp

                if p.x > w + 15:
                    p.x = -10
                    p.base_y = random.uniform(h * 0.05, h * 0.95)
                    p.y = p.base_y
            else:
                p.sway_phase += p.sway_speed
                dx = math_sin(p.sway_phase) * p.sway_amp * sm
                dy = p.speed_y
                p.x += dx
                p.y += dy

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
        if not self._enabled:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 1. Draw particles
        if self._particles:
            r = self._color.red()
            g = self._color.green()
            b = self._color.blue()

            for p in self._particles:
                alpha = int(p.base_alpha * 240)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(r, g, b, alpha))
                painter.drawEllipse(QPointF(p.x, p.y), p.radius, p.radius)

        # 2. If 'Below Text' layer is active and text pixmap is present, draw text on top of particles
        if self._layer == LAYER_BELOW_TEXT and self._text_pixmap and not self._text_pixmap.isNull():
            painter.drawPixmap(0, 0, self._text_pixmap)

        painter.end()
