import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication, QMessageBox

from src.services.media_probe import extract_video_frame, clear_video_frame_cache
from src.services.compositor import create_intro_card
from src.services.project_service import TEMPLATE_DESIGN_KEYS
from src.ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


def test_template_design_keys_include_intro_visual_keys():
    """Verify all independent intro visual keys are registered as durable template design keys."""
    expected_keys = [
        "intro_title_text",
        "intro_title_font_family",
        "intro_title_font_style",
        "intro_title_font_size",
        "intro_title_color",
        "intro_logo_show",
        "intro_logo_scale",
        "intro_website_show",
        "intro_website_text",
        "intro_website_font_size",
        "intro_website_opacity",
        "intro_website_color",
        "intro_blur_radius",
        "intro_card_opacity",
    ]
    for key in expected_keys:
        assert key in TEMPLATE_DESIGN_KEYS, f"Key {key} must be in TEMPLATE_DESIGN_KEYS"


def test_video_frame_cache_hit_and_eviction(tmp_path):
    """Test that extract_video_frame leverages the in-memory frame cache to prevent repeated subprocess calls."""
    clear_video_frame_cache()
    fake_video = tmp_path / "mock_video.mp4"
    fake_video.write_bytes(b"mock video data 12345")

    # Mock run_tracked_subprocess to simulate FFmpeg frame extraction
    mock_img = Image.new("RGB", (640, 360), color=(100, 150, 200))
    mock_res = MagicMock()
    mock_res.stdout = b"fake_bytes"
    with patch("src.services.media_probe.run_tracked_subprocess", return_value=mock_res) as mock_subproc, \
         patch("PIL.Image.open", return_value=mock_img):

        # First call: cache miss -> invokes subprocess
        frame1 = extract_video_frame(str(fake_video), timestamp=1.5)
        assert frame1 is not None
        assert mock_subproc.call_count == 1

        # Second call with same timestamp and file: cache hit -> NO subprocess invocation!
        frame2 = extract_video_frame(str(fake_video), timestamp=1.5)
        assert frame2 is not None
        assert mock_subproc.call_count == 1  # subprocess was NOT called again


def test_intro_card_independent_visual_generation(tmp_path):
    """Test create_intro_card renders blurred plate with custom independent fonts, logo scale and watermark."""
    bg_img = Image.new("RGB", (1280, 720), color=(30, 45, 60))
    bg_path = tmp_path / "bg.png"
    bg_img.save(bg_path)

    logo_img = Image.new("RGBA", (100, 100), color=(255, 255, 0, 255))
    logo_path = tmp_path / "logo.png"
    logo_img.save(logo_path)

    out_card = create_intro_card(
        width=1280,
        height=720,
        background_path=str(bg_path),
        logo_path=str(logo_path),
        collection_title="Independent Intro Title",
        template="Cinematic",
        out_dir=str(tmp_path),
        title_font_family="Segoe UI",
        title_font_style="Bold",
        title_font_size=72,
        title_color="#FFDD44",
        logo_show=True,
        logo_scale=1.5,
        website_text="@IndependentWatermark",
        website_show=True,
        website_opacity=0.85,
        website_font_size=26,
        website_color="#AABBCC",
        blur_radius=20,
        card_opacity=0.75,
    )

    assert Path(out_card).is_file()
    img = Image.open(out_card)
    assert img.size == (1280, 720)


def test_main_window_intro_visual_serialization_and_restore(tmp_path, monkeypatch):
    """Test MainWindow correctly serializes independent intro visual options and restores them."""
    win = MainWindow()

    # Configure custom independent intro controls
    win.intro_title_edit.setText("My Unique Intro Title")
    win.intro_title_size_spin.setValue(80)
    win.intro_title_color = (255, 200, 50)
    win.intro_logo_show_check.setChecked(False)
    win.intro_logo_scale_spin.setValue(140)
    win.intro_website_show_check.setChecked(True)
    win.intro_website_edit.setText("nasheed-custom.org")
    win.intro_website_size_spin.setValue(28)
    win.intro_website_opacity_slider.setValue(65)
    win.intro_website_color = (180, 220, 250)
    win.intro_blur_spin.setValue(35)
    win.intro_card_opacity_slider.setValue(85)

    project_data = win._project()

    assert project_data["intro_title_text"] == "My Unique Intro Title"
    assert project_data["intro_title_font_size"] == 80
    assert project_data["intro_title_color"] == (255, 200, 50)
    assert project_data["intro_logo_show"] is False
    assert project_data["intro_logo_scale"] == 1.40
    assert project_data["intro_website_text"] == "nasheed-custom.org"
    assert project_data["intro_website_font_size"] == 28
    assert project_data["intro_website_opacity"] == 0.65
    assert project_data["intro_blur_radius"] == 35
    assert project_data["intro_card_opacity"] == 0.85

    # Mock dialog confirmation for new_project
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Yes)
    win.new_project()
    assert win.intro_title_edit.text() == ""
    assert win.intro_title_size_spin.value() == 56

    win._restore_project_state(project_data)
    assert win.intro_title_edit.text() == "My Unique Intro Title"
    assert win.intro_title_size_spin.value() == 80
    assert win.intro_title_color == (255, 200, 50)
    assert win.intro_logo_show_check.isChecked() is False
    assert win.intro_logo_scale_spin.value() == 140
    assert win.intro_website_edit.text() == "nasheed-custom.org"
    assert win.intro_website_size_spin.value() == 28
    assert win.intro_website_opacity_slider.value() == 65
    assert win.intro_blur_spin.value() == 35
    assert win.intro_card_opacity_slider.value() == 85


def test_video_frame_rate_throttle_in_preview():
    """Verify that _on_video_frame_received throttles rapid incoming video frames to avoid UI freezing."""
    win = MainWindow()
    win._is_preview_playing = True

    # Create a mock valid QVideoFrame
    mock_frame = MagicMock()
    mock_frame.isValid.return_value = True
    qimg = QImage(640, 360, QImage.Format.Format_ARGB32)
    qimg.fill(QColor(0, 0, 0))
    mock_frame.toImage.return_value = qimg

    win._last_video_frame_time = time.monotonic()

    # Immediate call (elapsed ~ 0.0s < 0.033s) should be dropped by throttle
    win.preview_image.setPixmap = MagicMock()
    win._on_video_frame_received(mock_frame)
    win.preview_image.setPixmap.assert_not_called()

    # Call with simulated elapsed time >= 0.033s should process and render
    win._last_video_frame_time = time.monotonic() - 0.040
    win._on_video_frame_received(mock_frame)
    win.preview_image.setPixmap.assert_called_once()
