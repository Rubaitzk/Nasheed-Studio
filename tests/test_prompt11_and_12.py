"""
Unit and integration tests for Prompt 11 and Prompt 12:
- Prompt 11: Intro Presentation Audio with Fade In / Out, sensible trimming/padding, and synchronization
- Prompt 12: Playlist ExtendedSelection and Bulk Removal with nearest-neighbor selection and Undo safety
"""

import os
import shutil
import tempfile
from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QAbstractItemView

from src.ui.main_window import MainWindow
from src.services.project_service import (
    extract_template,
    apply_template_to_project,
    check_missing_assets,
    relink_asset,
    bundle_managed_assets,
    TEMPLATE_DESIGN_KEYS,
)
from src.services.render_service import build_render_command
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
def dummy_audio_files(tmp_path):
    """Create tiny valid WAV files for testing."""
    import wave
    import struct

    def create_wav(filename: str, duration_sec: float = 2.0, sample_rate: int = 44100):
        p = tmp_path / filename
        with wave.open(str(p), "w") as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            num_frames = int(duration_sec * sample_rate)
            # 440 Hz tone
            data = bytearray()
            for i in range(num_frames):
                val = int(32767.0 * 0.2 * (1.0 if (i % 100 < 50) else -1.0))
                packed = struct.pack("<hh", val, val)
                data.extend(packed)
            wav_file.writeframes(data)
        return str(p)

    intro_wav = create_wav("intro_test.wav", duration_sec=2.5)
    track1_wav = create_wav("track1.wav", duration_sec=3.0)
    track2_wav = create_wav("track2.wav", duration_sec=3.0)
    track3_wav = create_wav("track3.wav", duration_sec=3.0)
    track4_wav = create_wav("track4.wav", duration_sec=3.0)

    return {
        "intro": intro_wav,
        "track1": track1_wav,
        "track2": track2_wav,
        "track3": track3_wav,
        "track4": track4_wav,
    }


# ==============================================================================
# PROMPT 11: Intro Presentation Audio & Fade In/Out Tests
# ==============================================================================

def test_intro_audio_project_keys():
    """Verify intro audio keys are recognized in project and template keys."""
    assert "intro_audio_path" in TEMPLATE_DESIGN_KEYS
    assert "intro_audio_fade_in" in TEMPLATE_DESIGN_KEYS
    assert "intro_audio_fade_out" in TEMPLATE_DESIGN_KEYS


def test_intro_audio_project_serialization(win, dummy_audio_files):
    """Verify intro audio settings are serialized in _project() and restored in _restore_project_state()."""
    win.intro_audio_path = dummy_audio_files["intro"]
    win.intro_fade_in_spin.setValue(1.2)
    win.intro_fade_out_spin.setValue(0.8)
    win.intro_check.setChecked(True)

    proj = win._project()
    assert proj["intro_audio_path"] == dummy_audio_files["intro"]
    assert proj["intro_audio_fade_in"] == 1.2
    assert proj["intro_audio_fade_out"] == 0.8
    assert proj["intro_enabled"] is True

    # Reset and restore
    win.clear_intro_audio()
    assert win.intro_audio_path == ""

    win._restore_project_state(proj)
    assert win.intro_audio_path == dummy_audio_files["intro"]
    assert win.intro_fade_in_spin.value() == 1.2
    assert win.intro_fade_out_spin.value() == 0.8
    assert win.intro_check.isChecked() is True


def test_intro_audio_template_extraction_and_apply(dummy_audio_files):
    """Verify templates preserve and apply intro audio and fade parameters."""
    project_data = {
        "version": 1,
        "collection_title": "My Collection",
        "tracks": [{"title": "Track A", "path": dummy_audio_files["track1"], "duration": 3.0}],
        "intro_enabled": True,
        "intro_duration": 4.0,
        "intro_audio_path": dummy_audio_files["intro"],
        "intro_audio_fade_in": 1.5,
        "intro_audio_fade_out": 1.0,
    }

    from unittest.mock import patch
    with patch("src.services.project_service.is_temp_or_obsolete_path", return_value=False):
        from unittest.mock import patch
    with patch("src.services.project_service.is_temp_or_obsolete_path", return_value=False):
        tmpl = extract_template(project_data, template_name="Intro Sound Template")
    assert tmpl["intro_audio_path"] == str(Path(dummy_audio_files["intro"]).resolve())
    assert tmpl["intro_audio_fade_in"] == 1.5
    assert tmpl["intro_audio_fade_out"] == 1.0

    target_project = {
        "collection_title": "Protected Title",
        "tracks": [{"title": "Preserved Track", "path": dummy_audio_files["track2"], "duration": 4.0}],
    }
    applied = apply_template_to_project(target_project, tmpl)
    assert applied["intro_audio_path"] == tmpl["intro_audio_path"]
    assert applied["intro_audio_fade_in"] == 1.5
    assert applied["intro_audio_fade_out"] == 1.0
    assert applied["collection_title"] == "Protected Title"
    assert applied["tracks"][0]["title"] == "Preserved Track"


def test_intro_audio_missing_assets_detection(tmp_path):
    """Verify check_missing_assets flags missing intro audio when intro is enabled."""
    non_existent = str(tmp_path / "ghost_intro.mp3")
    proj = {
        "intro_enabled": True,
        "intro_audio_path": non_existent,
    }
    missing = check_missing_assets(proj)
    assert "intro_audio" in missing
    assert missing["intro_audio"][0]["path"] == non_existent

    # If intro is disabled, missing intro audio should not be flagged
    proj["intro_enabled"] = False
    missing_disabled = check_missing_assets(proj)
    assert "intro_audio" not in missing_disabled


def test_intro_audio_relink_and_bundle(dummy_audio_files, tmp_path):
    """Verify relink_asset and bundle_managed_assets handle intro_audio_path."""
    proj = {
        "intro_enabled": True,
        "intro_audio_path": dummy_audio_files["intro"],
    }
    new_path = str(tmp_path / "relinked_intro.wav")
    relinked = relink_asset(proj, dummy_audio_files["intro"], new_path)
    assert relinked["intro_audio_path"] == new_path

    # Managed asset bundling
    bundle_dir = tmp_path / "bundle"
    managed = bundle_managed_assets(proj, bundle_dir)
    assert Path(managed["intro_audio_path"]).exists()
    assert "assets" in managed["intro_audio_path"]


def test_render_command_intro_audio_filter_graph(dummy_audio_files, tmp_path):
    """Verify build_render_command generates correct intro audio filter graph with apad, atrim, and afade."""
    project = {
        "collection_title": "Audio Render Test",
        "resolution": "720p · HD",
        "intro_enabled": True,
        "intro_duration": 4.0,
        "intro_audio_path": dummy_audio_files["intro"],
        "intro_audio_fade_in": 0.8,
        "intro_audio_fade_out": 0.6,
        "tracks": [
            {"title": "Track 1", "path": dummy_audio_files["track1"], "duration": 3.0},
        ],
        "output_path": str(tmp_path / "out.mp4"),
    }

    # Dummy background image
    bg_img = tmp_path / "bg.png"
    from PIL import Image
    Image.new("RGB", (1280, 720), (30, 30, 30)).save(bg_img)
    project["background"] = str(bg_img)

    work_dir = tmp_path / "work"
    work_dir.mkdir()

    cmd, _ = build_render_command(project, work_dir)
    cmd_str = " ".join(cmd)

    # 1. Check intro audio input file is added
    assert dummy_audio_files["intro"] in cmd

    # 2. Extract -filter_complex argument
    fc_idx = cmd.index("-filter_complex")
    filter_graph = cmd[fc_idx + 1]

    # 3. Verify intro audio filter chain
    assert "apad=whole_dur=4.000" in filter_graph
    assert "atrim=0:4.000" in filter_graph
    assert "afade=t=in:st=0:d=0.800" in filter_graph
    assert "afade=t=out:st=3.400:d=0.600" in filter_graph
    assert "[a_intro_prep]" in filter_graph
    assert "[a_intro_prep][a_norm_0]concat=n=2:v=0:a=1" in filter_graph


def test_render_command_short_and_long_audio_behavior(dummy_audio_files, tmp_path):
    """Verify sensible behavior for short audio (apad pads with silence) and long audio (atrim trims)."""
    bg_img = tmp_path / "bg.png"
    from PIL import Image
    Image.new("RGB", (1280, 720), (30, 30, 30)).save(bg_img)

    work_dir = tmp_path / "work"
    work_dir.mkdir(exist_ok=True)

    # Short audio (intro is 8.0s, dummy audio is 2.5s)
    project_short = {
        "collection_title": "Short Audio Test",
        "intro_enabled": True,
        "intro_duration": 8.0,
        "intro_audio_path": dummy_audio_files["intro"],
        "intro_audio_fade_in": 1.0,
        "intro_audio_fade_out": 2.0,
        "tracks": [{"title": "Track 1", "path": dummy_audio_files["track1"], "duration": 3.0}],
        "output_path": str(tmp_path / "out_short.mp4"),
        "background": str(bg_img),
    }
    cmd_short, _ = build_render_command(project_short, work_dir)
    fg_short = cmd_short[cmd_short.index("-filter_complex") + 1]
    assert "apad=whole_dur=8.000" in fg_short
    assert "atrim=0:8.000" in fg_short
    assert "afade=t=out:st=6.000:d=2.000" in fg_short

    # Long audio (intro is 1.5s, dummy audio is 2.5s)
    project_long = {
        "collection_title": "Long Audio Test",
        "intro_enabled": True,
        "intro_duration": 1.5,
        "intro_audio_path": dummy_audio_files["intro"],
        "intro_audio_fade_in": 0.5,
        "intro_audio_fade_out": 0.5,
        "tracks": [{"title": "Track 1", "path": dummy_audio_files["track1"], "duration": 3.0}],
        "output_path": str(tmp_path / "out_long.mp4"),
        "background": str(bg_img),
    }
    cmd_long, _ = build_render_command(project_long, work_dir)
    fg_long = cmd_long[cmd_long.index("-filter_complex") + 1]
    assert "apad=whole_dur=1.500" in fg_long
    assert "atrim=0:1.500" in fg_long
    assert "afade=t=out:st=1.000:d=0.500" in fg_long


def test_render_command_invalid_fades_and_missing_audio(dummy_audio_files, tmp_path):
    """Verify fallback to silence on missing audio and safe clamping of invalid fade durations."""
    bg_img = tmp_path / "bg.png"
    from PIL import Image
    Image.new("RGB", (1280, 720), (30, 30, 30)).save(bg_img)

    work_dir = tmp_path / "work"
    work_dir.mkdir(exist_ok=True)

    # 1. Missing audio fallback to [a_intro_silence]
    project_missing = {
        "collection_title": "Missing Audio Test",
        "intro_enabled": True,
        "intro_duration": 3.0,
        "intro_audio_path": str(tmp_path / "non_existent_file.mp3"),
        "tracks": [{"title": "Track 1", "path": dummy_audio_files["track1"], "duration": 3.0}],
        "output_path": str(tmp_path / "out_missing.mp4"),
        "background": str(bg_img),
    }
    cmd_missing, _ = build_render_command(project_missing, work_dir)
    fg_missing = cmd_missing[cmd_missing.index("-filter_complex") + 1]
    assert "[a_intro_silence]" in fg_missing
    assert "anullsrc=channel_layout=stereo:sample_rate=44100,atrim=duration=3.000" in fg_missing

    # 2. Extreme fades (sum > intro_duration) safely clamped
    project_extreme = {
        "collection_title": "Extreme Fades Test",
        "intro_enabled": True,
        "intro_duration": 2.0,
        "intro_audio_path": dummy_audio_files["intro"],
        "intro_audio_fade_in": 3.0,
        "intro_audio_fade_out": 3.0,
        "tracks": [{"title": "Track 1", "path": dummy_audio_files["track1"], "duration": 3.0}],
        "output_path": str(tmp_path / "out_extreme.mp4"),
        "background": str(bg_img),
    }
    cmd_extreme, _ = build_render_command(project_extreme, work_dir)
    fg_extreme = cmd_extreme[cmd_extreme.index("-filter_complex") + 1]
    # Sum of 3.0 + 3.0 = 6.0 > 2.0 -> scaled by 2/6 = 1/3, each fade becomes 1.0s
    assert "afade=t=in:st=0:d=1.000" in fg_extreme
    assert "afade=t=out:st=1.000:d=1.000" in fg_extreme


# ==============================================================================
# PROMPT 12: Multi-Select & Bulk Removal Tests
# ==============================================================================

def test_playlist_extended_selection_mode(win):
    """Verify PlaylistListWidget uses ExtendedSelection mode."""
    assert win.track_list.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection


def test_single_track_removal(win, dummy_audio_files):
    """Verify existing single-item selection and removal workflow is preserved."""
    win.tracks = [
        {"title": "Track 1", "path": dummy_audio_files["track1"], "duration": 3.0},
        {"title": "Track 2", "path": dummy_audio_files["track2"], "duration": 3.0},
        {"title": "Track 3", "path": dummy_audio_files["track3"], "duration": 3.0},
    ]
    win._refresh_tracks()
    assert win.track_list.count() == 3

    # Select track 1 (second row)
    win.track_list.setCurrentRow(1)
    win.remove_track()

    assert len(win.tracks) == 2
    assert win.tracks[0]["title"] == "Track 1"
    assert win.tracks[1]["title"] == "Track 3"
    # Nearest remaining track (index 1, "Track 3") is selected
    assert win.track_list.currentRow() == 1


def test_multi_select_bulk_removal_adjacent(win, dummy_audio_files):
    """Verify multi-selection and bulk removal of adjacent items in one operation."""
    win.tracks = [
        {"title": "Track 0", "path": dummy_audio_files["track1"], "duration": 3.0},
        {"title": "Track 1", "path": dummy_audio_files["track2"], "duration": 3.0},
        {"title": "Track 2", "path": dummy_audio_files["track3"], "duration": 3.0},
        {"title": "Track 3", "path": dummy_audio_files["track4"], "duration": 3.0},
    ]
    win._refresh_tracks()

    # Select adjacent rows 1 and 2
    win.track_list.item(1).setSelected(True)
    win.track_list.item(2).setSelected(True)
    selected_rows = [win.track_list.row(it) for it in win.track_list.selectedItems()]
    assert selected_rows == [1, 2]

    win.remove_track()

    assert len(win.tracks) == 2
    assert win.tracks[0]["title"] == "Track 0"
    assert win.tracks[1]["title"] == "Track 3"
    # Selected row should be nearest remaining item (row 1, "Track 3")
    assert win.track_list.currentRow() == 1


def test_multi_select_bulk_removal_nonadjacent(win, dummy_audio_files):
    """Verify multi-selection and bulk removal of nonadjacent items."""
    win.tracks = [
        {"title": "Track 0", "path": dummy_audio_files["track1"], "duration": 3.0},
        {"title": "Track 1", "path": dummy_audio_files["track2"], "duration": 3.0},
        {"title": "Track 2", "path": dummy_audio_files["track3"], "duration": 3.0},
        {"title": "Track 3", "path": dummy_audio_files["track4"], "duration": 3.0},
    ]
    win._refresh_tracks()

    # Select nonadjacent rows 0 and 2
    win.track_list.item(0).setSelected(True)
    win.track_list.item(2).setSelected(True)

    win.remove_track()

    assert len(win.tracks) == 2
    assert win.tracks[0]["title"] == "Track 1"
    assert win.tracks[1]["title"] == "Track 3"
    # Nearest remaining item at or after index 0 is row 0 ("Track 1")
    assert win.track_list.currentRow() == 0


def test_bulk_removal_at_start_and_end(win, dummy_audio_files):
    """Verify removing items near beginning and end of playlist updates selection safely."""
    win.tracks = [
        {"title": "Track 0", "path": dummy_audio_files["track1"], "duration": 3.0},
        {"title": "Track 1", "path": dummy_audio_files["track2"], "duration": 3.0},
        {"title": "Track 2", "path": dummy_audio_files["track3"], "duration": 3.0},
        {"title": "Track 3", "path": dummy_audio_files["track4"], "duration": 3.0},
    ]
    win._refresh_tracks()

    # 1. Remove beginning items (0 and 1)
    win.track_list.item(0).setSelected(True)
    win.track_list.item(1).setSelected(True)
    win.remove_track()

    assert len(win.tracks) == 2
    assert win.tracks[0]["title"] == "Track 2"
    assert win.tracks[1]["title"] == "Track 3"
    assert win.track_list.currentRow() == 0

    # 2. Remove last item
    win.track_list.clearSelection()
    win.track_list.item(1).setSelected(True)
    win.remove_track()

    assert len(win.tracks) == 1
    assert win.tracks[0]["title"] == "Track 2"
    assert win.track_list.currentRow() == 0


def test_bulk_removal_all_tracks(win, dummy_audio_files):
    """Verify removing all items leaves playlist empty and currentRow at -1."""
    win.tracks = [
        {"title": "Track 0", "path": dummy_audio_files["track1"], "duration": 3.0},
        {"title": "Track 1", "path": dummy_audio_files["track2"], "duration": 3.0},
    ]
    win._refresh_tracks()

    win.track_list.selectAll()
    assert len(win.track_list.selectedItems()) == 2

    win.remove_track()

    assert len(win.tracks) == 0
    assert win.track_list.count() == 0
    assert win.track_list.currentRow() == -1


def test_bulk_removal_undo_recovery(win, dummy_audio_files):
    """Verify bulk removal can be completely reverted with Undo (Ctrl+Z)."""
    win.tracks = [
        {"title": "Track 0", "path": dummy_audio_files["track1"], "duration": 3.0},
        {"title": "Track 1", "path": dummy_audio_files["track2"], "duration": 3.0},
        {"title": "Track 2", "path": dummy_audio_files["track3"], "duration": 3.0},
    ]
    win._refresh_tracks()
    win._commit_undo_snapshot()

    # Bulk remove tracks 1 and 2
    win.track_list.item(1).setSelected(True)
    win.track_list.item(2).setSelected(True)
    win.remove_track()
    assert len(win.tracks) == 1

    # Undo
    win.undo()
    assert len(win.tracks) == 3
    assert [t["title"] for t in win.tracks] == ["Track 0", "Track 1", "Track 2"]


def test_bulk_removal_preserves_disk_files(win, dummy_audio_files):
    """Verify removing entries from playlist NEVER deletes the source audio files from disk."""
    for key, path in dummy_audio_files.items():
        assert Path(path).exists()

    win.tracks = [
        {"title": "Track 0", "path": dummy_audio_files["track1"], "duration": 3.0},
        {"title": "Track 1", "path": dummy_audio_files["track2"], "duration": 3.0},
    ]
    win._refresh_tracks()
    win.track_list.selectAll()
    win.remove_track()

    assert len(win.tracks) == 0
    # Files must still exist on disk
    for key, path in dummy_audio_files.items():
        assert Path(path).exists()
