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
from typing import Any, List, Optional, Tuple, Union
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPixmap, QPolygonF
from PySide6.QtWidgets import QWidget

from src.services.particle_service import (
    STYLE_DRIFTING_FLECKS,
    STYLE_FLOATING_ORBS,
    STYLE_LIGHT_GLINTS,
    LAYER_BELOW_TEXT,
    LAYER_ABOVE_TEXT,
    _speed_multiplier,
    lens_polygon,
    glint_state,
)

math_sin = math.sin


class Particle:
    __slots__ = (
        "x", "y", "base_y", "speed_x", "speed_y", "sway_phase",
        "sway_speed", "sway_amp", "radius", "base_alpha", "depth",
        "positions", "n", "phase", "vx", "vy", "width", "height",
        "length", "glint_width", "angle_deg", "peak_alpha"
    )

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __init__(
        self,
        w: int,
        h: int,
        style: str = STYLE_DRIFTING_FLECKS,
        speed_factor: float = 1.0,
        rng: Optional[random.Random] = None,
    ):
        r_gen = rng if rng is not None else random
        self.depth = r_gen.uniform(0.35, 1.0)
        self.x = r_gen.uniform(0, max(10, w))
        self.y = r_gen.uniform(0, max(10, h))
        self.base_y = self.y

        # Initialize slots with safe defaults
        self.positions = []
        self.n = 2
        self.phase = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.width = max(10, w)
        self.height = max(10, h)
        self.length = 0.0
        self.glint_width = 0.0
        self.angle_deg = 0.0
        self.peak_alpha = 255

        s = str(style).lower()
        if "fleck" in s:
            # Drifting Flecks: horizontal drift with gentle natural vertical float
            self.radius = 1.0 + self.depth * 1.8
            self.speed_x = (1.5 + self.depth * 2.2) * speed_factor
            self.speed_y = 0.0
            self.sway_phase = r_gen.uniform(0, 6.28318)
            self.sway_speed = r_gen.uniform(0.015, 0.04) * speed_factor
            self.sway_amp = 2.0 + self.depth * 5.0
            self.base_alpha = 0.35 + self.depth * 0.55
        elif "glint" in s:
            # Light Glints: thin tapered white sliver / flick drifting slowly with flashing glint
            res_scale = max(0.5, h / 1080.0)
            self.length = r_gen.uniform(14.0, 48.0) * res_scale
            w_ratio = r_gen.uniform(7.0, 11.0)
            self.glint_width = self.length / w_ratio
            self.radius = self.glint_width
            self.angle_deg = -60.0 + r_gen.uniform(-14.0, 14.0)
            self.n = r_gen.choice([2, 3, 4])
            self.phase = r_gen.uniform(0.0, 1.0)
            self.peak_alpha = int(round(r_gen.uniform(150, 255) * (0.5 + 0.5 * self.depth)))
            self.positions = [
                (r_gen.uniform(0, self.width), r_gen.uniform(0, self.height))
                for _ in range(self.n)
            ]
            kx_choices = [1] if speed_factor <= 1.0 else ([1, 2] if speed_factor <= 3.0 else [2, 3])
            ky_choices = [-1] if speed_factor <= 1.0 else ([-2, -1] if speed_factor <= 3.0 else [-3, -2])
            duration = 6.0
            self.vx = r_gen.choice(kx_choices) * self.width / duration
            self.vy = r_gen.choice(ky_choices) * self.height / duration
            self.speed_x = self.vx
            self.speed_y = self.vy
            self.sway_phase = 0.0
            self.sway_speed = 0.0
            self.sway_amp = 0.0
            self.base_alpha = 0.0
            self.x = self.positions[0][0]
            self.y = self.positions[0][1]
        else:
            # Floating Orbs: vertical atmospheric float with sinusoidal sway
            self.radius = 1.5 + self.depth * 3.0
            self.speed_x = 0.0
            self.speed_y = (0.5 + self.depth * 1.0) * speed_factor
            self.sway_phase = r_gen.uniform(0, 6.28318)
            self.sway_speed = r_gen.uniform(0.015, 0.045) * speed_factor
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
        self._duration: float = 6.0
        self._time_counter: float = 0.0

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
            self._text_pixmap = None
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
        """Set particle style: 'Drifting Flecks', 'Floating Orbs', or 'Light Glints'."""
        s = str(style).lower()
        if "fleck" in s:
            self._style = STYLE_DRIFTING_FLECKS
        elif "glint" in s:
            self._style = STYLE_LIGHT_GLINTS
        else:
            self._style = STYLE_FLOATING_ORBS
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
            rng = random.Random(42 + self._num_particles + self._speed_level)
            self._particles = [
                Particle(w, h, self._style, sm, rng=rng)
                for _ in range(self._num_particles)
            ]
            if "glint" in self._style.lower():
                for p in self._particles:
                    p.width = w
                    p.height = h
                    x, y, alpha_factor = glint_state(p, self._time_counter, self._duration)
                    p.x = x
                    p.y = y
                    p.base_alpha = alpha_factor

    def _reseed_velocities(self) -> None:
        sm = self._speed_multiplier()
        s = self._style.lower()
        if "fleck" in s:
            for p in self._particles:
                p.speed_x = (1.5 + p.depth * 2.2) * sm
                p.sway_speed = random.uniform(0.015, 0.04) * sm
        elif "glint" in s:
            kx_choices = [1] if sm <= 1.0 else ([1, 2] if sm <= 3.0 else [2, 3])
            ky_choices = [-1] if sm <= 1.0 else ([-2, -1] if sm <= 3.0 else [-3, -2])
            duration = getattr(self, "_duration", 6.0)
            for p in self._particles:
                kx = random.choice(kx_choices)
                ky = random.choice(ky_choices)
                p.vx = kx * p.width / duration
                p.vy = ky * p.height / duration
        else:
            for p in self._particles:
                p.speed_y = (0.5 + p.depth * 1.0) * sm
                p.sway_speed = random.uniform(0.015, 0.045) * sm

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w = max(100, self.width())
        h = max(100, self.height())
        for p in self._particles:
            p.width = w
            p.height = h
        self._ensure_particles()

    def _update_particles(self) -> None:
        if not self._enabled or self._is_paused:
            return

        w = self.width()
        h = self.height()
        if w <= 10 or h <= 10:
            return

        sm = self._speed_multiplier()
        s = self._style.lower()

        if "glint" in s:
            dt = 1.0 / 30.0
            self._time_counter = (self._time_counter + dt) % self._duration
            for p in self._particles:
                p.width = w
                p.height = h
                x, y, alpha_factor = glint_state(p, self._time_counter, self._duration)
                p.x = x
                p.y = y
                p.base_alpha = alpha_factor
            self.update()
            return

        is_flecks = ("fleck" in s)

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

            if "glint" in self._style.lower():
                r_out = int(round(r * 0.4 + 255 * 0.6))
                g_out = int(round(g * 0.4 + 255 * 0.6))
                b_out = int(round(b * 0.4 + 255 * 0.6))
                for p in self._particles:
                    eff_alpha = int(p.peak_alpha * p.base_alpha)
                    if eff_alpha <= 5:
                        continue
                    # Outer lens sliver
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(r_out, g_out, b_out, eff_alpha))
                    pts = lens_polygon(p.x, p.y, p.length, p.glint_width, p.angle_deg)
                    painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in pts]))

                    # Core bright center (glow)
                    core_alpha = min(255, int(eff_alpha * 1.15))
                    painter.setBrush(QColor(255, 255, 255, core_alpha))
                    core_pts = lens_polygon(p.x, p.y, p.length * 0.65, p.glint_width * 0.45, p.angle_deg)
                    painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in core_pts]))
            else:
                for p in self._particles:
                    alpha = int(p.base_alpha * 240)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(r, g, b, alpha))
                    painter.drawEllipse(QPointF(p.x, p.y), p.radius, p.radius)

        # 2. If 'Below Text' layer is active and text pixmap is present, draw text on top of particles
        # Centered exactly to align with QLabel preview_image (AlignCenter)
        if self._layer == LAYER_BELOW_TEXT and self._text_pixmap and not self._text_pixmap.isNull():
            ox = max(0, (self.width() - self._text_pixmap.width()) // 2)
            oy = max(0, (self.height() - self._text_pixmap.height()) // 2)
            painter.drawPixmap(ox, oy, self._text_pixmap)

        painter.end()
