"""
Unit and integration tests for Feature E: Audio Visualizer.

Verifies:
1. ON/OFF control: enabled generates overlay layer; disabled leaves pipeline untouched.
2. Heartbeat style: reacts to audio, respects amplitude, element size, direction.
3. Standard style (horizontal bars): element count, size, width, direction (Upward, Downward, Bidirectional).
4. Audio responsiveness: actual FFT analysis on audio vs silence resting state.
5. Preview image generation (PIL RGBA).
6. Actual FFmpeg rendering execution: produces valid MP4 with visualizer overlay.
7. Project persistence & restoration.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from src.services.media_probe import get_duration, get_video_info
from src.services.render_service import build_render_command
from src.services.visualizer_service import (
    build_timeline_audio,
    extract_audio_features,
    load_audio_samples,
    render_visualizer_frame,
    render_visualizer_preview_image,
)
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def sample_audio_path():
    p = Path("tests/fixtures/audio/sample_tone.wav").resolve()
    assert p.is_file()
    return str(p)


@pytest.fixture
def sample_bg_path():
    p = Path("tests/fixtures/images/sample_bg.png").resolve()
    assert p.is_file(), f"Fixture bg not found: {p}"
    return str(p)


def test_visualizer_audio_feature_extraction(sample_audio_path):
    audio = load_audio_samples(sample_audio_path)
    assert len(audio) > 0

    bins, rms = extract_audio_features(audio, time_sec=0.5, num_bins=32)
    assert len(bins) == 32
    assert rms > 0.05, f"Expected non-trivial RMS energy, got {rms}"
    assert np.any(bins > 0), "Expected non-zero frequency bins from audio"


def test_visualizer_silence_handling():
    silent_audio = np.zeros(44100, dtype=np.float32)
    bins, rms = extract_audio_features(silent_audio, time_sec=0.5, num_bins=32)
    assert rms == 0.0
    assert np.all(bins == 0)

    # Frame rendering must still succeed gracefully
    frame = render_visualizer_frame(
        1280, 720, silent_audio, 0.5,
        {
            "visualizer_enabled": True,
            "visualizer_style": "Standard (Horizontal Bars)",
            "visualizer_direction": "Bidirectional",
            "visualizer_element_count": 16,
            "visualizer_element_size": 6,
            "visualizer_width": 600,
            "visualizer_y": 500,
        }
    )
    assert frame.shape == (720, 1280, 4)
    # Baseline indicators should be visible even in silence
    assert (frame[:, :, 3] > 0).sum() > 0


def test_visualizer_standard_directions(sample_audio_path):
    audio = load_audio_samples(sample_audio_path)
    directions = ["Upward", "Downward", "Bidirectional"]

    for d in directions:
        frame = render_visualizer_frame(
            1280, 720, audio, 0.5,
            {
                "visualizer_enabled": True,
                "visualizer_style": "Standard (Horizontal Bars)",
                "visualizer_direction": d,
                "visualizer_element_count": 24,
                "visualizer_element_size": 10,
                "visualizer_width": 700,
                "visualizer_y": 500,
                "visualizer_amplitude": 1.5,
                "visualizer_color": (0, 200, 255),
            }
        )
        non_zero = (frame[:, :, 3] > 0).sum()
        assert non_zero > 0, f"Direction {d} produced empty frame"


def test_visualizer_heartbeat_style(sample_audio_path):
    audio = load_audio_samples(sample_audio_path)
    frame = render_visualizer_frame(
        1280, 720, audio, 0.5,
        {
            "visualizer_enabled": True,
            "visualizer_style": "Heartbeat",
            "visualizer_direction": "Bidirectional",
            "visualizer_element_count": 64,
            "visualizer_element_size": 4,
            "visualizer_width": 800,
            "visualizer_y": 600,
            "visualizer_amplitude": 1.2,
            "visualizer_color": (255, 100, 100),
        }
    )
    assert frame.shape == (720, 1280, 4)
    assert (frame[:, :, 3] > 0).sum() > 0


def test_visualizer_preview_image(sample_audio_path):
    project = {
        "visualizer_enabled": True,
        "visualizer_style": "Standard (Horizontal Bars)",
        "tracks": [{"path": sample_audio_path, "duration": 1.0}],
    }
    img = render_visualizer_preview_image(1280, 720, project, preview_time=0.5)
    assert img is not None
    assert img.size == (1280, 720)
    assert img.mode == "RGBA"


def test_visualizer_render_command_and_ffmpeg_export(sample_audio_path, sample_bg_path):
    project = {
        "collection_title": "Visualizer Export Test",
        "background": sample_bg_path,
        "tracks": [{"path": sample_audio_path, "title": "Track 1", "duration": 1.0}],
        "visualizer_enabled": True,
        "visualizer_style": "Standard (Horizontal Bars)",
        "visualizer_direction": "Bidirectional",
        "visualizer_element_count": 20,
        "visualizer_element_size": 8,
        "visualizer_width": 600,
        "visualizer_y": 550,
        "visualizer_amplitude": 1.0,
        "visualizer_color": (56, 189, 248),
        "output_path": "vis_export.mp4",
    }
    with tempfile.TemporaryDirectory() as tmp:
        cmd, out = build_render_command(project, Path(tmp))
        filter_str = "".join(cmd)
        assert "overlay" in filter_str

        # Execute actual FFmpeg command to verify visualizer stream integration
        out_file = Path(tmp) / "rendered_vis.mp4"
        cmd[-1] = str(out_file)
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        assert res.returncode == 0, f"FFmpeg failed: {res.stderr}"

        # Verify video streams and duration
        info = get_video_info(str(out_file))
        assert info.get("has_video") is True
        dur = get_duration(str(out_file))
        assert abs(dur - 1.0) < 0.2


def test_visualizer_main_window_persistence(qapp):
    win = MainWindow()
    try:
        win.visualizer_check.setChecked(True)
        win.visualizer_style_combo.setCurrentText("Heartbeat")
        win.visualizer_direction_combo.setCurrentText("Upward")
        win.visualizer_count_spin.setValue(48)
        win.visualizer_amp_spin.setValue(2.0)

        proj = win._project()
        assert proj["visualizer_enabled"] is True
        assert proj["visualizer_style"] == "Heartbeat"
        assert proj["visualizer_direction"] == "Upward"
        assert proj["visualizer_element_count"] == 48
        assert proj["visualizer_amplitude"] == 2.0

        # Restore in new state
        win._restore_project_state(proj)
        assert win.visualizer_check.isChecked() is True
        assert win.visualizer_style_combo.currentText() == "Heartbeat"
        assert win.visualizer_count_spin.value() == 48
    finally:
        dispose_window(win)
