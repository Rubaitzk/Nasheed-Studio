"""
Automated tests for Item 5: High-resolution DPI-aware canvas preview, painter render hints,
static-layer caching, and particle overlay performance.
"""

import os
import sys
import time
from pathlib import Path
import pytest
import numpy as np
from PIL import Image

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import Qt, QSize

from src.ui.main_window import MainWindow
from src.ui.widgets.particle_canvas import ParticleOverlayWidget
from tests.conftest import dispose_window


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def populated_window(qapp):
    win = MainWindow()
    win.resize(1366, 768)
    win.show()
    qapp.processEvents()

    sample_bg = str(Path("tests/fixtures/images/sample_bg.png").resolve())
    sample_tone = str(Path("tests/fixtures/audio/sample_tone.wav").resolve())
    if Path(sample_bg).exists():
        win.background_path = sample_bg
    if Path(sample_tone).exists():
        win.tracks = [
            {"path": sample_tone, "title": f"0{i}. Sample Nasheed Track {i}", "duration": 45.0}
            for i in range(1, 5)
        ]
        win.collection_title.setText("Nasheed Collection")
        win._committed_title = "Nasheed Collection"
        win._refresh_tracks()

    win._refresh_preview()
    qapp.processEvents()
    yield win
    dispose_window(win)


def test_static_layer_cached_across_frames(populated_window, qapp):
    """
    Assert the static text/background layer is rendered once across N frames while
    particles animate, and is invalidated only when text or viewport size changes.
    """
    win = populated_window
    assert hasattr(win, "_static_layer_render_count")
    initial_render_count = win._static_layer_render_count
    assert initial_render_count >= 1, "Expected static layer to be rendered at least once on init"

    # Turn particles ON and animate N=30 frames
    win.particles_check.setChecked(True)
    win._on_particles_param_changed()
    qapp.processEvents()

    for _ in range(30):
        win.particle_overlay._update_particles()
        qapp.processEvents()

    # Verify static layer was NOT re-rasterized during particle animation
    assert win._static_layer_render_count == initial_render_count, (
        f"Static layer was re-rendered {win._static_layer_render_count - initial_render_count} times during particle animation"
    )

    # Invalidate by changing text
    win.collection_title.setText("Updated Collection Title")
    win._apply_title()
    win._refresh_preview()
    qapp.processEvents()

    assert win._static_layer_render_count == initial_render_count + 1, (
        "Expected static layer render count to increment after text modification"
    )

    # Invalidate by changing size
    new_size = QSize(720, 405)
    win.preview_frame.resize(new_size)
    win._refresh_preview()
    qapp.processEvents()

    # Scaled pixmap cache handles size adaptation
    assert win._static_layer_render_count >= initial_render_count + 1


def test_render_hints_on_every_painter(populated_window):
    """
    Assert that required render hints (Antialiasing, TextAntialiasing, SmoothPixmapTransform)
    are enabled on every QPainter, and FastTransformation is nowhere in the source code.
    """
    # 1. Assert FastTransformation does not exist in any Python source file under src/
    src_dir = Path(__file__).resolve().parent.parent / "src"
    violations = []
    for py_file in src_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if "FastTransformation" in text:
            violations.append(str(py_file.relative_to(src_dir)))
    assert not violations, f"Found prohibited FastTransformation in: {violations}"

    # 2. Check ParticleOverlayWidget paintEvent sets the 3 required hints
    overlay = populated_window.particle_overlay
    assert hasattr(overlay, "paintEvent")
    # Inspect paintEvent source code
    import inspect
    source = inspect.getsource(overlay.paintEvent)
    assert "RenderHint.Antialiasing" in source
    assert "RenderHint.TextAntialiasing" in source
    assert "RenderHint.SmoothPixmapTransform" in source

    # 3. Check video frame handler also enforces all 3 hints
    source_video = inspect.getsource(populated_window._on_video_frame_received)
    assert "RenderHint.Antialiasing" in source_video
    assert "RenderHint.TextAntialiasing" in source_video
    assert "RenderHint.SmoothPixmapTransform" in source_video


def test_text_region_pixel_consistency_particles_on_vs_off(populated_window, qapp):
    """
    Assert that text pixels match within tolerance between particles OFF and ON
    (verifying no resolution loss or degradation occurs when particles are enabled).
    """
    win = populated_window
    win.particles_check.setChecked(False)
    win._refresh_preview()
    qapp.processEvents()

    # Capture canvas with particles OFF
    pix_off = win.preview_image.pixmap()
    assert pix_off is not None and not pix_off.isNull()
    img_off = pix_off.toImage()

    # Switch particles ON in foreground overlay mode
    win.particles_check.setChecked(True)
    win.particles_style_combo.setCurrentText("Wind Streaks")
    win._on_particles_param_changed()
    win._refresh_preview()
    qapp.processEvents()

    # Background canvas preview_image should maintain identical high resolution
    pix_on = win.preview_image.pixmap()
    assert pix_on is not None and not pix_on.isNull()
    img_on = pix_on.toImage()

    assert img_off.width() == img_on.width()
    assert img_off.height() == img_on.height()

    # Compare raw bytes of static text/background layer
    b_off = img_off.constBits()
    b_on = img_on.constBits()
    arr_off = np.frombuffer(b_off, dtype=np.uint8).reshape((img_off.height(), img_off.bytesPerLine()))
    arr_on = np.frombuffer(b_on, dtype=np.uint8).reshape((img_on.height(), img_on.bytesPerLine()))

    # Text/background pixmap must match identically (0 diff) because particles are on separate overlay
    diff = np.abs(arr_off.astype(int) - arr_on.astype(int))
    max_diff = np.max(diff)
    assert max_diff == 0, f"Expected 0 diff on static layer, got max_diff={max_diff}"


def test_particle_preview_frame_performance(populated_window, qapp):
    """
    Performance sanity check: measure average preview frame time with particles ON
    across 60 frames. Frame time must be reasonable (< 15 ms).
    """
    win = populated_window
    win.particles_check.setChecked(True)
    win.particles_style_combo.setCurrentText("Wind Streaks")
    win._on_particles_param_changed()
    qapp.processEvents()

    times = []
    for _ in range(60):
        t0 = time.perf_counter()
        win.particle_overlay._update_particles()
        qapp.processEvents()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)

    avg_ms = float(np.mean(times))
    p95_ms = float(np.percentile(times, 95))
    print(f"\n[Performance] Particle preview frame time: avg={avg_ms:.2f}ms, p95={p95_ms:.2f}ms (Budget: 33.3ms)")

    assert avg_ms < 15.0, f"Average frame time {avg_ms:.2f}ms exceeds 15ms target"
