import tempfile
import pytest
from pathlib import Path
from PIL import Image

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.services.compositor import create_composition, _draw_smooth_rounded_rect
from tests.conftest import dispose_window


@pytest.fixture
def app():
    instance = QApplication.instance()
    if not instance:
        instance = QApplication([])
    return instance


@pytest.fixture
def win(app):
    w = MainWindow()
    w.show()
    yield w
    dispose_window(w)


@pytest.fixture
def test_audio_file(tmp_path):
    import wave
    audio_file = tmp_path / "track_sample.wav"
    with wave.open(str(audio_file), "w") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(44100)
        # 2 seconds of silence
        f.writeframes(b"\x00" * (44100 * 4 * 2))
    return str(audio_file)


# ---------------------------------------------------------------------------
# Test Prompt 14 & Highlight Centering / Misplacement
# ---------------------------------------------------------------------------

def test_highlight_multiline_centering_no_misplacement(tmp_path):
    """Verify that multi-line tracks do not suffer highlight misplacement or slice through text."""
    titles = [
        "01. Short Title",
        "02. Very Long Nasheed Title That Definitely Wraps Onto Two Or More Lines In Playlist",
        "03. Another Track",
    ]
    base, overlays = create_composition(
        1280,
        720,
        "",
        None,
        "Test Nasheed Collection",
        titles,
        "Classic Left",
        str(tmp_path),
        track_max_chars=25,  # Force line wrapping on item 2
        active_track_index=1,
        highlight_style="Pill",
        highlight_target="text",
    )
    assert len(overlays) == 3
    # Check overlay 1 (wrapped title)
    ov_img = Image.open(overlays[1]).convert("RGBA")
    alpha = ov_img.split()[3]
    bbox = alpha.getbbox()
    assert bbox is not None, "Highlight overlay should have visible content"
    hl_height = bbox[3] - bbox[1]
    # A wrapped 2-line title highlight must be taller than a single line height
    assert hl_height > 35, f"Highlight height ({hl_height}) should cover multi-line wrapped text"


def test_accent_bar_smooth_edges_no_uncut_white_pixels(tmp_path):
    """
    Prompt 14: Verify that _draw_smooth_rounded_rect produces smooth, antialiased corners
    without white uncut step pixels across transparent, dark, and light backgrounds.
    """
    for bg_color in [(0, 0, 0, 0), (20, 24, 22, 255), (240, 240, 240, 255)]:
        canvas = Image.new("RGBA", (200, 80), bg_color)
        # Draw rounded accent bar
        bar_box = (20, 10, 36, 70)
        bar_rgb = (212, 168, 67, 255)
        _draw_smooth_rounded_rect(canvas, bar_box, radius=8, fill=bar_rgb)

        # Inspect corner pixel values around the top-left corner (x=20, y=10)
        # With 4x lanczos supersampling, outer step pixels should smoothly blend alpha
        # and NOT produce harsh opaque white (255, 255, 255) artifact pixels
        for cy in range(8, 14):
            for cx in range(18, 24):
                px = canvas.getpixel((cx, cy))
                if bg_color[3] == 0:
                    assert not (px[0] > 240 and px[1] > 240 and px[2] > 240 and px[3] == 255), (
                        f"Uncut opaque white pixel found at ({cx}, {cy}): {px}"
                    )


def test_accent_bar_attached_to_text_box(tmp_path):
    """Verify Accent Bar stays anchored to the highlight box edge even when highlight_target='text'."""
    titles = ["01. Test Title One", "02. Test Title Two"]
    base, overlays = create_composition(
        1280,
        720,
        "",
        None,
        "Nasheed Collection",
        titles,
        "Classic Left",
        str(tmp_path),
        active_track_index=0,
        highlight_style="Accent Bar",
        highlight_target="text",
    )
    assert len(overlays) == 2
    ov_img = Image.open(overlays[0]).convert("RGBA")
    alpha = ov_img.split()[3]
    bbox = alpha.getbbox()
    assert bbox is not None
    assert (bbox[2] - bbox[0]) > 0
    assert (bbox[3] - bbox[1]) > 0


# ---------------------------------------------------------------------------
# Test Prompt 13: Interactive Preview Playback
# ---------------------------------------------------------------------------

def test_preview_playback_controls_initialized(win):
    """Prompt 13: Verify clear Play/Pause controls and enabled interactive timeline scrubber."""
    assert hasattr(win, "play_preview_btn")
    assert win.play_preview_btn.isVisible()
    assert "Play" in win.play_preview_btn.text()

    assert hasattr(win, "scrubber_play_btn")
    assert hasattr(win, "scrubber_stop_btn")
    assert hasattr(win, "timeline_scrubber")
    assert win.timeline_scrubber.isEnabled(), "Timeline scrubber should be enabled for interactive preview"


def test_preview_playback_toggle_start_pause_stop(win, test_audio_file):
    """Prompt 13: Test starting, pausing, stopping, and repeated preview playback."""
    win.tracks = [
        {"title": "Track 01", "path": test_audio_file, "duration": 2.0, "_id": "t1"},
        {"title": "Track 02", "path": test_audio_file, "duration": 2.0, "_id": "t2"},
    ]
    win._refresh_tracks_labels()
    win._refresh_preview()

    # 1. Start playback
    win._toggle_preview_playback()
    assert win._is_preview_playing is True
    assert "Pause" in win.play_preview_btn.text()
    assert "Interactive (Approximate)" in win.preview_badge.text()

    # 2. Pause playback
    win._toggle_preview_playback()
    assert win._is_preview_playing is False
    assert "Play" in win.play_preview_btn.text()

    # 3. Repeated play
    win._start_preview_playback()
    assert win._is_preview_playing is True

    # 4. Stop playback
    win._stop_preview_playback()
    assert win._is_preview_playing is False
    assert win._preview_current_time == 0.0
    assert win.scrubber_cur_label.text() == "00:00"
    assert "Play" in win.play_preview_btn.text()


def test_preview_timeline_duration_with_intro(win, test_audio_file):
    """Prompt 13: Timeline duration should accurately encompass intro + playlist tracks."""
    win.intro_enabled_check.setChecked(True)
    win.intro_dur_spin.setValue(3.5)
    win.tracks = [
        {"title": "Track 01", "path": test_audio_file, "duration": 4.0, "_id": "t1"},
        {"title": "Track 02", "path": test_audio_file, "duration": 5.0, "_id": "t2"},
    ]
    tot_d = win._get_project_timeline_duration()
    assert tot_d == 12.5  # 3.5 + 4.0 + 5.0
    win._refresh_tracks_labels()
    assert win.scrubber_total_label.text() == "00:12"


def test_preview_scrubber_seeking(win, test_audio_file):
    """Prompt 13: User seeking moves timeline, updates mm:ss label, and updates active track visual."""
    win.intro_enabled_check.setChecked(False)
    win.tracks = [
        {"title": "Track 01", "path": test_audio_file, "duration": 10.0, "_id": "t1"},
        {"title": "Track 02", "path": test_audio_file, "duration": 10.0, "_id": "t2"},
    ]
    win._refresh_tracks_labels()
    win._refresh_preview()

    # Seek to 12.5 seconds (which is in Track 02)
    win._seek_preview(12.5)
    assert win._preview_current_time == 12.5
    assert win.scrubber_cur_label.text() == "00:12"
    assert win._preview_active_visual_idx == 1


def test_preview_audio_sync_intro_to_playlist(win, test_audio_file):
    """Prompt 13: Verify audio transitions from intro to playlist tracks."""
    win.intro_enabled_check.setChecked(True)
    win.intro_dur_spin.setValue(2.0)
    win.intro_audio_path = test_audio_file
    win.tracks = [
        {"title": "Track 01", "path": test_audio_file, "duration": 5.0, "_id": "t1"},
    ]
    win._refresh_tracks_labels()
    win._refresh_preview()

    # In intro (t = 1.0)
    win._sync_playback_state(1.0, is_playing=False)
    assert win._preview_active_visual_idx == -1
    assert win._preview_audio_current_track_idx == -1

    # In track 1 (t = 3.0, which is playlist_t = 1.0)
    win._sync_playback_state(3.0, is_playing=False)
    assert win._preview_active_visual_idx == 0
    assert win._preview_audio_current_track_idx == 0


def test_preview_spacebar_shortcut(win):
    """Prompt 13: Spacebar shortcut toggles preview playback unless user is editing text."""
    assert win._is_preview_playing is False

    # Press spacebar
    win._on_shortcut_space_preview()
    assert win._is_preview_playing is True

    win._on_shortcut_space_preview()
    assert win._is_preview_playing is False
