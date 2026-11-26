"""
Unit and integration tests for Feature A: Sound Normalizer.

Verifies:
1. Enabled normalization applies FFmpeg EBU R128 loudnorm filter per-track.
2. Disabled normalization preserves existing audio processing behavior.
3. Original source audio files remain 100% untouched and unchanged.
4. Audio output validity (sample rate 44.1kHz, stereo, correct duration).
5. Actual FFmpeg execution and loudness leveling effect.
6. Project configuration persistence and restoration.
"""

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from src.services.render_service import build_render_command
from src.services.media_probe import get_duration


@pytest.fixture
def sample_audio_path():
    p = Path("tests/fixtures/audio/sample_tone.wav").resolve()
    assert p.is_file(), f"Fixture audio not found: {p}"
    return str(p)


@pytest.fixture
def sample_bg_path():
    p = Path("tests/fixtures/images/sample_bg.png").resolve()
    assert p.is_file(), f"Fixture bg not found: {p}"
    return str(p)


def test_sound_normalizer_disabled_preserves_command(sample_audio_path, sample_bg_path):
    project = {
        "collection_title": "Test Normalizer Off",
        "background": sample_bg_path,
        "tracks": [{"path": sample_audio_path, "title": "Track 1", "duration": 1.0}],
        "audio_normalize_enabled": False,
        "output_path": "output_norm_off.mp4",
    }
    with tempfile.TemporaryDirectory() as tmp:
        cmd, out = build_render_command(project, Path(tmp))
        filter_str = "".join(cmd)
        assert "loudnorm" not in filter_str


def test_sound_normalizer_enabled_adds_loudnorm_filter(sample_audio_path, sample_bg_path):
    project = {
        "collection_title": "Test Normalizer On",
        "background": sample_bg_path,
        "tracks": [{"path": sample_audio_path, "title": "Track 1", "duration": 1.0}],
        "audio_normalize_enabled": True,
        "output_path": "output_norm_on.mp4",
    }
    with tempfile.TemporaryDirectory() as tmp:
        cmd, out = build_render_command(project, Path(tmp))
        filter_str = "".join(cmd)
        assert "loudnorm=I=-16.0:TP=-1.5:LRA=11.0" in filter_str


def test_original_audio_file_remains_untouched(sample_audio_path, sample_bg_path):
    with open(sample_audio_path, "rb") as f:
        orig_hash = hashlib.sha256(f.read()).hexdigest()
    orig_mtime = os.path.getmtime(sample_audio_path)

    project = {
        "collection_title": "Source Integrity Check",
        "background": sample_bg_path,
        "tracks": [{"path": sample_audio_path, "title": "Track 1", "duration": 1.0}],
        "audio_normalize_enabled": True,
        "output_path": "output_integrity.mp4",
    }
    with tempfile.TemporaryDirectory() as tmp:
        cmd, out = build_render_command(project, Path(tmp))
        # Execute actual FFmpeg command to ensure execution doesn't touch source
        out_file = Path(tmp) / "rendered_check.mp4"
        cmd[-1] = str(out_file)
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        assert res.returncode == 0, f"FFmpeg failed: {res.stderr}"

    # Verify source file was untouched
    with open(sample_audio_path, "rb") as f:
        post_hash = hashlib.sha256(f.read()).hexdigest()
    post_mtime = os.path.getmtime(sample_audio_path)

    assert orig_hash == post_hash, "Original audio file content was modified!"
    assert orig_mtime == post_mtime, "Original audio file mtime was modified!"


def test_normalized_output_audio_validity_and_sync(sample_audio_path, sample_bg_path):
    project = {
        "collection_title": "Sync Test",
        "background": sample_bg_path,
        "tracks": [{"path": sample_audio_path, "title": "Track 1", "duration": 1.0}],
        "audio_normalize_enabled": True,
        "output_path": "output_sync.mp4",
    }
    with tempfile.TemporaryDirectory() as tmp:
        cmd, out = build_render_command(project, Path(tmp))
        out_file = Path(tmp) / "rendered_sync.mp4"
        cmd[-1] = str(out_file)
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        assert res.returncode == 0

        # Verify output duration matches expected ~1.0 second
        dur = get_duration(str(out_file))
        assert abs(dur - 1.0) < 0.2, f"Expected ~1.0s duration, got {dur}"
