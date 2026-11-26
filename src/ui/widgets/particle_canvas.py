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
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPixmap, QPolygonF, QPen, QBrush
from PySide6.QtWidgets import QWidget

from src.services.particle_service import (
    STYLE_WIND_STREAKS,
    STYLE_DRIFTING_FLECKS,
    STYLE_FLOATING_ORBS,
    STYLE_LIGHT_GLINTS,
    STYLE_TWINKLE_STARS,
    STYLE_BOKEH_RINGS,
    STYLE_CRESCENTS_AND_STARS,
    STYLE_EIGHT_POINT_STARS,
    LAYER_BELOW_TEXT,
    LAYER_ABOVE_TEXT,
    _speed_multiplier,
    lens_polygon,
    capsule_polygon,
    star_4point_polygon,
    crescent_polygon,
    star_5point_polygon,
    star_8point_polygon,
    glint_state,
    wind_streak_state,
    create_wind_streak_particles,
)

math_sin = math.sin


class Particle:
    __slots__ = (
        "x", "y", "base_y", "speed_x", "speed_y", "sway_phase",
        "sway_speed", "sway_amp", "radius", "base_alpha", "depth",
        "positions", "n", "phase", "vx", "vy", "width", "height",
        "length", "glint_width", "angle_deg", "peak_alpha", "sub_type",
        "base_radius", "base_length", "base_glint_width", "base_sway_amp",
        "base_speed_x", "base_speed_y", "style_name", "w_ratio",
        "thickness", "base_thickness", "color_rgb", "t_life",
        "spawn_x", "spawn_y", "rot", "speed_var"
    )

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @property
    def rotation(self) -> float:
        return math.atan2(self.vy, self.vx)

    def __init__(
        self,
        w: int,
        h: int,
        style: str = STYLE_WIND_STREAKS,
        speed_factor: float = 1.0,
        size_factor: float = 1.0,
        rng: Optional[random.Random] = None,
        angle: float = 225.0,
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
        self.sub_type = "default"
        self.base_radius = 0.0
        self.base_length = 0.0
        self.base_glint_width = 0.0
        self.base_sway_amp = 0.0
        self.base_speed_x = 0.0
        self.base_speed_y = 0.0
        self.w_ratio = 8.0
        self.thickness = 0.0
        self.base_thickness = 0.0
        self.color_rgb = (255, 255, 255)
        self.t_life = 1.0
        self.spawn_x = 0.0
        self.spawn_y = 0.0
        self.rot = 0.0
        self.speed_var = 1.0

        self.style_name = str(style).lower()
        s = self.style_name

        res_scale = max(10, h) / 1080.0
        geom_scale = res_scale * size_factor

        if "wind" in s:
            # Wind Streaks: solid white capsules drifting diagonally with constant velocity
            self.angle_deg = float(angle)
            base_len = r_gen.uniform(6.0, 14.0)
            base_thick = r_gen.uniform(1.5, 2.0)
            self.base_length = base_len
            self.base_thickness = base_thick
            self.length = base_len * geom_scale
            self.thickness = base_thick * geom_scale
            self.radius = self.thickness
            self.base_alpha = r_gen.uniform(0.6, 0.9)
            self.color_rgb = r_gen.choice([(255, 255, 255), (224, 224, 224)])

            rad = math.radians(self.angle_deg)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            speed_mag_ref = 254.558441227 * speed_factor
            self.base_speed_x = speed_mag_ref * cos_a
            self.base_speed_y = -speed_mag_ref * sin_a

            self.speed_var = r_gen.uniform(0.85, 1.15)
            self.vx = self.base_speed_x * self.speed_var * res_scale
            self.vy = self.base_speed_y * self.speed_var * res_scale
            self.speed_x = self.vx
            self.speed_y = self.vy
            self.rot = math.atan2(self.vy, self.vx)
            self.angle_deg = math.degrees(self.rot)

            margin = 50.0 * res_scale
            w_box = max(10, w) + 2.0 * margin
            h_box = max(10, h) + 2.0 * margin
            if self.vx <= 0 and self.vy >= 0:
                l_spawn = w_box + h_box
                u = r_gen.uniform(0.0, l_spawn)
                if u < w_box:
                    self.spawn_x = -margin + u
                    self.spawn_y = -margin
                else:
                    self.spawn_x = max(10, w) + margin
                    self.spawn_y = -margin + (u - w_box)
                tx = (-margin - self.spawn_x) / self.vx if self.vx < 0 else 1e9
                ty = (max(10, h) + margin - self.spawn_y) / self.vy if self.vy > 0 else 1e9
                self.t_life = max(0.2, min(tx, ty))
            else:
                sx_edge = (max(10, w) + margin) if self.vx < 0 else -margin
                sy_edge = -margin if self.vy > 0 else (max(10, h) + margin)
                cx_edge = -margin if self.vx < 0 else (max(10, w) + margin)
                cy_edge = (max(10, h) + margin) if self.vy > 0 else -margin

                l_spawn = w_box + h_box
                u = r_gen.uniform(0.0, l_spawn)
                if u < w_box:
                    self.spawn_x = -margin + u
                    self.spawn_y = sy_edge
                else:
                    self.spawn_x = sx_edge
                    self.spawn_y = -margin + (u - w_box)
                tx = (cx_edge - self.spawn_x) / self.vx if abs(self.vx) > 1e-4 else 1e9
                ty = (cy_edge - self.spawn_y) / self.vy if abs(self.vy) > 1e-4 else 1e9
                self.t_life = max(0.2, min(tx, ty))

            self.phase = r_gen.uniform(0.0, self.t_life)
            self.x = self.spawn_x + self.vx * self.phase
            self.y = self.spawn_y + self.vy * self.phase
        elif "fleck" in s:
            # Drifting Flecks: horizontal drift with gentle natural vertical float
            self.base_radius = 1.2 + self.depth * 1.8
            self.radius = self.base_radius * geom_scale
            self.base_speed_x = (4.5 + self.depth * 6.6) * speed_factor
            self.speed_x = self.base_speed_x * res_scale
            self.speed_y = 0.0
            self.sway_phase = r_gen.uniform(0, 6.28318)
            self.sway_speed = r_gen.uniform(0.015, 0.04) * speed_factor
            self.base_sway_amp = 2.5 + self.depth * 5.0
            self.sway_amp = self.base_sway_amp * res_scale
            self.base_alpha = 0.35 + self.depth * 0.55
        elif "glint" in s:
            # Light Glints: thin tapered white sliver / flick drifting slowly with flashing glint
            self.base_length = r_gen.uniform(14.0, 48.0)
            self.w_ratio = r_gen.uniform(7.0, 11.0)
            self.base_glint_width = self.base_length / self.w_ratio
            self.length = self.base_length * geom_scale
            self.glint_width = self.base_glint_width * geom_scale
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
        elif "twinkle" in s:
            # Twinkle Stars: 4-point diamond star with long thin arms flashing in and out
            self.base_radius = r_gen.uniform(8.0, 24.0)
            self.radius = self.base_radius * geom_scale
            self.length = self.radius * 2.0
            self.glint_width = self.radius * 0.36
            self.angle_deg = r_gen.uniform(0.0, 45.0)
            self.n = r_gen.choice([2, 3, 4])
            self.phase = r_gen.uniform(0.0, 1.0)
            self.peak_alpha = int(round(r_gen.uniform(150, 255) * (0.5 + 0.5 * self.depth)))
            self.positions = [
                (r_gen.uniform(0, self.width), r_gen.uniform(0, self.height))
                for _ in range(self.n)
            ]
            kx_choices = [1] if speed_factor <= 1.0 else ([1, 2] if speed_factor <= 3.0 else [2, 3])
            ky_choices = [-1, 0, 1]
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
        elif "bokeh" in s:
            # Bokeh Rings: soft translucent circle with a brighter edge ring, larger and slower
            self.base_radius = r_gen.uniform(6.0, 22.0)
            self.radius = self.base_radius * geom_scale
            self.base_speed_x = 0.0
            self.speed_x = 0.0
            self.base_speed_y = (0.75 + self.depth * 1.8) * speed_factor
            self.speed_y = self.base_speed_y * res_scale
            self.sway_phase = r_gen.uniform(0, 6.28318)
            self.sway_speed = r_gen.uniform(0.01, 0.03) * speed_factor
            self.base_sway_amp = 1.5 + self.depth * 3.0
            self.sway_amp = self.base_sway_amp * res_scale
            self.base_alpha = 0.25 + self.depth * 0.45
        elif "crescent" in s:
            # Crescents & Stars: small crescent moons and 5-point stars, sparse and slow
            self.sub_type = "crescent" if (r_gen.random() < 0.5) else "star"
            self.base_radius = (r_gen.uniform(7.0, 15.0) if self.sub_type == "crescent" else r_gen.uniform(4.0, 9.0))
            self.radius = self.base_radius * geom_scale
            self.angle_deg = r_gen.uniform(-15.0, 35.0) if self.sub_type == "crescent" else r_gen.uniform(0.0, 72.0)
            self.base_speed_x = 0.0
            self.speed_x = 0.0
            self.base_speed_y = (0.9 + self.depth * 1.8) * speed_factor
            self.speed_y = self.base_speed_y * res_scale
            self.sway_phase = r_gen.uniform(0, 6.28318)
            self.sway_speed = r_gen.uniform(0.015, 0.035) * speed_factor
            self.base_sway_amp = 3.0 + self.depth * 6.0
            self.sway_amp = self.base_sway_amp * res_scale
            self.base_alpha = 0.35 + self.depth * 0.5
        elif "eight" in s:
            # Eight-Point Stars: small Islamic-style stars (Rub el Hizb)
            self.base_radius = r_gen.uniform(5.0, 13.0)
            self.radius = self.base_radius * geom_scale
            self.angle_deg = r_gen.uniform(0.0, 45.0)
            self.base_speed_x = 0.0
            self.speed_x = 0.0
            self.base_speed_y = (0.75 + self.depth * 1.5) * speed_factor
            self.speed_y = self.base_speed_y * res_scale
            self.sway_phase = r_gen.uniform(0, 6.28318)
            self.sway_speed = r_gen.uniform(0.015, 0.035) * speed_factor
            self.base_sway_amp = 2.4 + self.depth * 4.5
            self.sway_amp = self.base_sway_amp * res_scale
            self.base_alpha = 0.35 + self.depth * 0.5
        else:
            # Floating Orbs: vertical atmospheric float with sinusoidal sway
            self.base_radius = 1.8 + self.depth * 3.2
            self.radius = self.base_radius * geom_scale
            self.base_speed_x = 0.0
            self.speed_x = 0.0
            self.base_speed_y = (1.5 + self.depth * 3.0) * speed_factor
            self.speed_y = self.base_speed_y * res_scale
            self.sway_phase = r_gen.uniform(0, 6.28318)
            self.sway_speed = r_gen.uniform(0.015, 0.045) * speed_factor
            self.base_sway_amp = 1.2 + self.depth * 2.7
            self.sway_amp = self.base_sway_amp * res_scale
            self.base_alpha = 0.25 + self.depth * 0.55

    def update_scale(self, res_scale: float, geom_scale: float) -> None:
        """Rescale particle dimensions and velocities when window is resized or size is changed."""
        s = self.style_name
        if "wind" in s:
            self.length = self.base_length * geom_scale
            self.thickness = self.base_thickness * geom_scale
            self.radius = self.thickness
            var = getattr(self, "speed_var", 1.0)
            self.vx = self.base_speed_x * var * res_scale
            self.vy = self.base_speed_y * var * res_scale
            self.speed_x = self.vx
            self.speed_y = self.vy
            self.rot = math.atan2(self.vy, self.vx)
            self.angle_deg = math.degrees(self.rot)
        elif "fleck" in s:
            self.radius = self.base_radius * geom_scale
            self.sway_amp = self.base_sway_amp * res_scale
            self.speed_x = self.base_speed_x * res_scale
        elif "glint" in s:
            self.length = self.base_length * geom_scale
            self.glint_width = self.base_glint_width * geom_scale
            self.radius = self.glint_width
        elif "twinkle" in s:
            self.radius = self.base_radius * geom_scale
            self.length = self.radius * 2.0
            self.glint_width = self.radius * 0.36
        elif "bokeh" in s:
            self.radius = self.base_radius * geom_scale
            self.sway_amp = self.base_sway_amp * res_scale
            self.speed_y = self.base_speed_y * res_scale
        elif "crescent" in s:
            self.radius = self.base_radius * geom_scale
            self.sway_amp = self.base_sway_amp * res_scale
            self.speed_y = self.base_speed_y * res_scale
        elif "eight" in s:
            self.radius = self.base_radius * geom_scale
            self.sway_amp = self.base_sway_amp * res_scale
            self.speed_y = self.base_speed_y * res_scale
        else:
            self.radius = self.base_radius * geom_scale
            self.sway_amp = self.base_sway_amp * res_scale
            self.speed_y = self.base_speed_y * res_scale


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
        self._size_val: int = 5  # 1 to 20 (sensible default 5)
        self._color: QColor = QColor(56, 189, 248)  # Default cyan accent
        self._style: str = STYLE_WIND_STREAKS
        self._angle: float = 225.0
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

    def set_particle_size(self, size: int) -> None:
        """Set particle size (range 1 to 20, or legacy percentage)."""
        self._size_val = int(size)
        self._rescale_particles()
        self.update()

    def get_particle_size(self) -> int:
        return self._size_val

    @property
    def _size_percent(self) -> int:
        return self._size_val

    def _size_factor(self) -> float:
        val = self._size_val
        return (val / 5.0) if val <= 20 else (val / 100.0)

    def _rescale_particles(self) -> None:
        h = max(10, self.height())
        res_scale = h / 1080.0
        geom_scale = res_scale * self._size_factor()
        for p in self._particles:
            p.update_scale(res_scale, geom_scale)

    def set_particle_angle(self, angle: float) -> None:
        """Set particle travel angle in degrees."""
        self._angle = float(angle)
        self._particles.clear()
        self._ensure_particles()
        self.update()

    def get_particle_angle(self) -> float:
        return self._angle

    def set_particle_style(self, style: str) -> None:
        """Set particle style: 'Wind Streaks', 'Drifting Flecks', 'Floating Orbs', 'Light Glints', etc."""
        s = str(style).lower()
        if "wind" in s:
            self._style = STYLE_WIND_STREAKS
        elif "fleck" in s:
            self._style = STYLE_DRIFTING_FLECKS
        elif "glint" in s:
            self._style = STYLE_LIGHT_GLINTS
        elif "twinkle" in s:
            self._style = STYLE_TWINKLE_STARS
        elif "bokeh" in s:
            self._style = STYLE_BOKEH_RINGS
        elif "crescent" in s:
            self._style = STYLE_CRESCENTS_AND_STARS
        elif "eight" in s:
            self._style = STYLE_EIGHT_POINT_STARS
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
        size_factor = self._size_factor()
        if len(self._particles) != self._num_particles:
            rng = random.Random(42 + self._num_particles + self._speed_level)
            self._particles = [
                Particle(w, h, self._style, sm, size_factor=size_factor, rng=rng, angle=getattr(self, "_angle", 225.0))
                for _ in range(self._num_particles)
            ]
            if "glint" in self._style.lower() or "twinkle" in self._style.lower():
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
        res_scale = max(10, self.height()) / 1080.0
        if "wind" in s:
            rad = math.radians(getattr(self, "_angle", 225.0))
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            speed_mag_ref = 254.558441227 * sm
            for p in self._particles:
                p.base_speed_x = speed_mag_ref * cos_a
                p.base_speed_y = -speed_mag_ref * sin_a
                var = getattr(p, "speed_var", 1.0)
                p.vx = p.base_speed_x * var * res_scale
                p.vy = p.base_speed_y * var * res_scale
                p.speed_x = p.vx
                p.speed_y = p.vy
                p.rot = math.atan2(p.vy, p.vx)
                p.angle_deg = math.degrees(p.rot)
        elif "fleck" in s:
            for p in self._particles:
                p.base_speed_x = (4.5 + p.depth * 6.6) * sm
                p.speed_x = p.base_speed_x * res_scale
                p.sway_speed = random.uniform(0.015, 0.04) * sm
        elif "glint" in s or "twinkle" in s:
            kx_choices = [1] if sm <= 1.0 else ([1, 2] if sm <= 3.0 else [2, 3])
            ky_choices = [-1] if sm <= 1.0 else ([-2, -1] if sm <= 3.0 else [-3, -2])
            duration = getattr(self, "_duration", 6.0)
            for p in self._particles:
                kx = random.choice(kx_choices)
                ky = random.choice(ky_choices)
                p.vx = kx * p.width / duration
                p.vy = ky * p.height / duration
        elif "bokeh" in s:
            for p in self._particles:
                p.base_speed_y = (0.75 + p.depth * 1.8) * sm
                p.speed_y = p.base_speed_y * res_scale
                p.sway_speed = random.uniform(0.01, 0.03) * sm
        elif "crescent" in s:
            for p in self._particles:
                p.base_speed_y = (0.9 + p.depth * 1.8) * sm
                p.speed_y = p.base_speed_y * res_scale
                p.sway_speed = random.uniform(0.015, 0.035) * sm
        elif "eight" in s:
            for p in self._particles:
                p.base_speed_y = (0.75 + p.depth * 1.5) * sm
                p.speed_y = p.base_speed_y * res_scale
                p.sway_speed = random.uniform(0.015, 0.035) * sm
        else:
            for p in self._particles:
                p.base_speed_y = (1.5 + p.depth * 3.0) * sm
                p.speed_y = p.base_speed_y * res_scale
                p.sway_speed = random.uniform(0.015, 0.045) * sm

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w = max(100, self.width())
        h = max(100, self.height())
        for p in self._particles:
            p.width = w
            p.height = h
        self._rescale_particles()
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

        if "wind" in s:
            dt = 1.0 / 30.0
            self._time_counter += dt
            for p in self._particles:
                p.width = w
                p.height = h
                tau = (p.phase + self._time_counter) % p.t_life
                p.x = p.spawn_x + p.vx * tau
                p.y = p.spawn_y + p.vy * tau
            self.update()
            return

        if "glint" in s or "twinkle" in s:
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
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # 1. Draw particles
        if self._particles:
            r = self._color.red()
            g = self._color.green()
            b = self._color.blue()

            if "wind" in self._style.lower():
                for p in self._particles:
                    cr, cg, cb = p.color_rgb
                    a = int(round(p.base_alpha * 255))
                    pen = QPen(QColor(cr, cg, cb, a), max(0.1, p.thickness), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                    painter.setPen(pen)
                    rot = p.rot
                    half_d = max(0.1, (p.length - p.thickness) / 2.0)
                    cos_r = math.cos(rot)
                    sin_r = math.sin(rot)
                    x1 = p.x - half_d * cos_r
                    y1 = p.y - half_d * sin_r
                    x2 = p.x + half_d * cos_r
                    y2 = p.y + half_d * sin_r
                    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            elif "glint" in self._style.lower():
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
            elif "twinkle" in self._style.lower():
                r_out = int(round(r * 0.4 + 255 * 0.6))
                g_out = int(round(g * 0.4 + 255 * 0.6))
                b_out = int(round(b * 0.4 + 255 * 0.6))
                for p in self._particles:
                    eff_alpha = int(p.peak_alpha * p.base_alpha)
                    if eff_alpha <= 5:
                        continue
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(r_out, g_out, b_out, eff_alpha))
                    pts = star_4point_polygon(p.x, p.y, p.radius, p.radius * 0.18, p.angle_deg)
                    painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in pts]))

                    core_alpha = min(255, int(eff_alpha * 1.15))
                    painter.setBrush(QColor(255, 255, 255, core_alpha))
                    core_pts = star_4point_polygon(p.x, p.y, p.radius * 0.45, p.radius * 0.10, p.angle_deg)
                    painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in core_pts]))
            elif "bokeh" in self._style.lower():
                r_edge = int(round(r * 0.3 + 255 * 0.7))
                g_edge = int(round(g * 0.3 + 255 * 0.7))
                b_edge = int(round(b * 0.3 + 255 * 0.7))
                pen_w = max(0.5, 1.8 * (max(10, self.height()) / 1080.0) * self._size_factor())
                pen = QPen(QColor(r_edge, g_edge, b_edge, 210), pen_w)
                brush = QBrush(QColor(r, g, b, 50))
                for p in self._particles:
                    painter.setPen(pen)
                    painter.setBrush(brush)
                    painter.drawEllipse(QPointF(p.x, p.y), p.radius, p.radius)
            elif "crescent" in self._style.lower():
                r_out = int(round(r * 0.35 + 255 * 0.65))
                g_out = int(round(g * 0.35 + 255 * 0.65))
                b_out = int(round(b * 0.35 + 255 * 0.65))
                painter.setPen(Qt.PenStyle.NoPen)
                for p in self._particles:
                    painter.setBrush(QColor(r_out, g_out, b_out, int(p.base_alpha * 240)))
                    if p.sub_type == "crescent":
                        pts = crescent_polygon(p.x, p.y, p.radius, p.angle_deg)
                    else:
                        pts = star_5point_polygon(p.x, p.y, p.radius, angle_deg=p.angle_deg)
                    painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in pts]))
            elif "eight" in self._style.lower():
                r_out = int(round(r * 0.35 + 255 * 0.65))
                g_out = int(round(g * 0.35 + 255 * 0.65))
                b_out = int(round(b * 0.35 + 255 * 0.65))
                painter.setPen(Qt.PenStyle.NoPen)
                for p in self._particles:
                    painter.setBrush(QColor(r_out, g_out, b_out, int(p.base_alpha * 240)))
                    pts = star_8point_polygon(p.x, p.y, p.radius, angle_deg=p.angle_deg)
                    painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in pts]))
            else:
                for p in self._particles:
                    alpha = int(p.base_alpha * 240)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(r, g, b, alpha))
                    painter.drawEllipse(QPointF(p.x, p.y), p.radius, p.radius)

        # 2. If 'Below Text' layer is active and text pixmap is present, draw text on top of particles
        # Wind Streaks is strictly foreground overlay above text, so skip drawing text over particles
        if self._layer == LAYER_BELOW_TEXT and self._text_pixmap and not self._text_pixmap.isNull():
            dpr = self._text_pixmap.devicePixelRatio() or 1.0
            log_w = int(round(self._text_pixmap.width() / dpr))
            log_h = int(round(self._text_pixmap.height() / dpr))
            ox = max(0, (self.width() - log_w) // 2)
            oy = max(0, (self.height() - log_h) // 2)
            painter.drawPixmap(ox, oy, self._text_pixmap)

        painter.end()
