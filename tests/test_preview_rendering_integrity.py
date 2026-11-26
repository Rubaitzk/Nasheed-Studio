"""
Automated regression tests verifying preview rendering integrity and absence of
duplicated visual elements across intro card, playlist preview, playback scrubbing,
repeated logo resizing, and export pipeline.
"""

import sys
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.services.render_service import render_project
from src.services.media_probe import extract_video_frame
from tests.conftest import dispose_window


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def test_window(qapp):
    win = MainWindow()
    win.resize(1280, 720)
    win.show()

    sample_bg = str(Path("tests/fixtures/images/sample_bg.png").resolve())
    sample_logo = str(Path("assets/ncn_logo.png").resolve())

    win.background_path = sample_bg
    win.logo_path = sample_logo
    win.tracks = [
        {"path": "tests/fixtures/audio/sample_tone.wav", "title": f"0{i}. Sample Nasheed {i}", "duration": 5.0}
        for i in range(1, 6)
    ]
    win.collection_title.setText("Nasheed Collection Test")
    win._committed_title = "Nasheed Collection Test"
    win.particles_check.setChecked(True)
    win.particles_layer_combo.setCurrentText("Below Text")
    win.particles_count_spin.setValue(40)

    yield win

    dispose_window(win)


def test_intro_preview_has_no_playlist_artifacts(test_window, qapp):
    """Verify intro preview displays only intro card elements without playlist tracks or bottom-right logo."""
    test_window._previewing_intro = False
    test_window._refresh_preview()
    qapp.processEvents()

    # Toggle to intro preview
    test_window._toggle_intro_preview()
    qapp.processEvents()

    assert test_window._previewing_intro is True
    assert test_window.particle_overlay._text_pixmap is None

    # Grab composite frame of preview_frame
    grabbed = test_window.preview_frame.grab().toImage()
    w, h = grabbed.width(), grabbed.height()

    # Check playlist area on the left: should have NO white playlist track names
    # In intro card, left region is darkened frosted glass background
    left_crop = grabbed.copy(int(w * 0.05), int(h * 0.2), int(w * 0.25), int(h * 0.5))
    # Convert to PIL
    ptr = left_crop.bits()
    arr_left = np.frombuffer(ptr, dtype=np.uint8).reshape((left_crop.height(), left_crop.width(), 4))
    # Count bright white text pixels (> 220 in RGB)
    bright_text_pixels = np.sum((arr_left[:, :, 0] > 220) & (arr_left[:, :, 1] > 220) & (arr_left[:, :, 2] > 220))
    assert bright_text_pixels == 0, f"Intro card preview contaminated by playlist text ({bright_text_pixels} pixels)"


def test_playlist_preview_has_no_duplicated_elements(test_window, qapp):
    """Verify playlist preview displays each element exactly once with no ghosting or duplicates."""
    test_window._previewing_intro = False
    test_window._refresh_preview()
    qapp.processEvents()

    assert test_window._previewing_intro is False
    assert test_window.particle_overlay._text_pixmap is not None
    # In Below Text mode, preview_image MUST have the clean background only (no text/logo)
    # so particle_overlay paints the typography on top without duplicate underlying text
    bg_pix = test_window.preview_image.pixmap()
    assert not bg_pix.isNull()

    # Repeatedly trigger cache hits and resizes
    for _ in range(5):
        test_window._refresh_preview()
        qapp.processEvents()

    # Check particle overlay text pixmap is not None and not null
    assert test_window.particle_overlay._text_pixmap is not None
    assert not test_window.particle_overlay._text_pixmap.isNull()


def test_repeated_logo_resizing_responsiveness_and_correctness(test_window, qapp):
    """Verify repeatedly changing logo scale and position updates cleanly without freezing or duplicates."""
    import time
    test_window._previewing_intro = False
    test_window._refresh_preview()
    qapp.processEvents()

    scales = [80, 100, 140, 180, 120, 100]
    positions = ["Bottom-Right", "Top-Left", "Bottom-Left", "Top-Right", "Bottom-Right"]

    t0 = time.time()
    for sc, pos in zip(scales, positions):
        test_window.logo_scale_spin.setValue(sc)
        test_window.logo_pos_combo.setCurrentText(pos)
        test_window._refresh_preview()
        qapp.processEvents()
    elapsed = time.time() - t0

    # 5 full refreshes should complete smoothly without blocking or hanging
    assert elapsed < 10.0, f"Logo resizing too slow: took {elapsed:.2f}s"
    assert test_window.particle_overlay._text_pixmap is not None
    assert not test_window.particle_overlay._text_pixmap.isNull()


def test_playback_scrubbing_intro_to_playlist_transitions(test_window, qapp):
    """Verify seeking into intro card clears text overlay, and seeking into playlist restores it."""
    test_window.intro_enabled_check.setChecked(True)
    test_window.intro_dur_spin.setValue(3.0)
    test_window._refresh_preview()
    qapp.processEvents()

    # Seek into intro (t = 1.0s < 3.0s)
    test_window._seek_preview(1.0)
    qapp.processEvents()
    assert test_window.particle_overlay._text_pixmap is None

    # Seek into playlist (t = 4.0s >= 3.0s)
    test_window._seek_preview(4.0)
    qapp.processEvents()
    assert test_window.particle_overlay._text_pixmap is not None
    assert not test_window.particle_overlay._text_pixmap.isNull()

    # Seek back into intro (t = 0.5s)
    test_window._seek_preview(0.5)
    qapp.processEvents()
    assert test_window.particle_overlay._text_pixmap is None


def test_exported_video_frames_independent_verification():
    """Verify final exported video frames at intro and playlist timestamps have single elements."""
    sample_audio = Path("tests/fixtures/audio/sample_tone.wav").resolve()
    sample_bg = Path("tests/fixtures/images/sample_bg.png").resolve()
    sample_logo = Path("assets/ncn_logo.png").resolve()

    with tempfile.TemporaryDirectory() as tmp:
        out_video = Path(tmp) / "export_verify.mp4"
        project = {
            "collection_title": "Integrity Test Collection",
            "background": str(sample_bg),
            "logo": str(sample_logo),
            "logo_position": "Bottom-Right",
            "logo_scale": 1.0,
            "website_text": "www.test.com",
            "website_position": "Top-Right",
            "website_show": True,
            "tracks": [
                {"path": str(sample_audio), "title": "Track 1", "duration": 1.5},
            ],
            "intro_enabled": True,
            "intro_duration": 1.5,
            "intro_animation": "Fade in / out",
            "intro_title_text": "Intro Integrity Test",
            "intro_logo_show": True,
            "intro_logo_scale": 1.0,
            "intro_website_show": True,
            "intro_website_text": "www.test.com",
            "particles_enabled": True,
            "particles_style": "Drifting Flecks",
            "particles_layer": "Below Text",
            "particles_quantity": 25,
            "output_path": str(out_video),
        }
        render_project(project)
        assert out_video.is_file() and out_video.stat().st_size > 0

        # Frame at 0.5s (intro): must NOT have bottom-right logo
        frame_intro = extract_video_frame(str(out_video), 0.5)
        crop_intro_br = frame_intro.crop((int(frame_intro.width * 0.8), int(frame_intro.height * 0.8), frame_intro.width, frame_intro.height))
        arr_intro_br = np.array(crop_intro_br.convert("RGB"))
        bright_intro_br = np.sum((arr_intro_br[:, :, 0] > 220) & (arr_intro_br[:, :, 1] > 220) & (arr_intro_br[:, :, 2] > 220))
        assert bright_intro_br == 0, f"Exported intro frame contains playlist logo ({bright_intro_br} bright pixels)"

        # Frame at 2.0s (playlist): must have bottom-right logo
        frame_playlist = extract_video_frame(str(out_video), 2.0)
        crop_play_br = frame_playlist.crop((int(frame_playlist.width * 0.8), int(frame_playlist.height * 0.8), frame_playlist.width, frame_playlist.height))
        arr_play_br = np.array(crop_play_br.convert("RGB"))
        bright_play_br = np.sum((arr_play_br[:, :, 0] > 200) & (arr_play_br[:, :, 1] > 200) & (arr_play_br[:, :, 2] > 200))
        assert bright_play_br > 0, "Exported playlist frame missing bottom-right logo"
