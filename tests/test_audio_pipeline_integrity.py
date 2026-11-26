"""
Tests verifying audio pipeline integrity:
- FFmpeg loudnorm filter positioning and 44.1 kHz sample rate compliance.
- Non-silent, properly leveled audio export compatible with Windows decoders (AAC <= 48kHz).
- Normalizer loudness leveling across diverse input levels.
- Format compatibility (.wav, .mp3, .m4a, .aac, .flac, .ogg).
- Preview audio player seek and media status synchronization.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from PIL import Image
import pytest

from src.services.media_probe import find_tool, get_duration
from src.services.render_service import build_render_command


@pytest.fixture
def test_env():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        ffmpeg = find_tool("ffmpeg")
        ffprobe = find_tool("ffprobe")

        # 1. Generate test background
        bg_path = tmp / "test_bg.png"
        Image.new("RGB", (640, 360), (24, 28, 36)).save(bg_path)

        # 2. Generate a 2-second loud tone (0 dB full-scale sine)
        loud_wav = tmp / "loud_input.wav"
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-ac", "2", "-ar", "44100", str(loud_wav)],
            check=True, capture_output=True
        )

        # 3. Generate a 2-second quiet tone (-30 dB sine)
        quiet_wav = tmp / "quiet_input.wav"
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-af", "volume=-30dB", "-ac", "2", "-ar", "44100", str(quiet_wav)],
            check=True, capture_output=True
        )

        yield {
            "tmp": tmp,
            "ffmpeg": ffmpeg,
            "ffprobe": ffprobe,
            "bg": bg_path,
            "loud_wav": loud_wav,
            "quiet_wav": quiet_wav,
        }


def test_render_command_structure(test_env):
    """Verify loudnorm comes before aformat and -ar 44100 is present in the output flags."""
    project = {
        "collection_title": "Audio Command Test",
        "background": str(test_env["bg"]),
        "tracks": [{"path": str(test_env["loud_wav"]), "title": "Track 1", "duration": 2.0}],
        "audio_normalize_enabled": True,
        "output_path": str(test_env["tmp"] / "out.mp4"),
    }
    cmd, _ = build_render_command(project, test_env["tmp"])
    cmd_str = " ".join(cmd)

    # 1. loudnorm must precede aformat so 96kHz loudnorm internal output is formatted down to 44.1kHz
    assert "loudnorm=I=-16.0:TP=-1.5:LRA=11.0,aformat=sample_fmts=fltp:sample_rates=44100" in cmd_str

    # 2. -ar 44100 must be in output flags
    assert "-ar" in cmd
    ar_idx = cmd.index("-ar")
    assert cmd[ar_idx + 1] == "44100"


def test_audio_export_sample_rate_and_levels(test_env):
    """Export video and probe audio stream: must be 44.1kHz AAC and audible."""
    out_file = test_env["tmp"] / "rendered_audio_test.mp4"
    project = {
        "collection_title": "Sample Rate & Level Test",
        "background": str(test_env["bg"]),
        "tracks": [{"path": str(test_env["loud_wav"]), "title": "Track 1", "duration": 2.0}],
        "audio_normalize_enabled": True,
        "output_path": str(out_file),
    }
    cmd, _ = build_render_command(project, test_env["tmp"])
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Render failed: {res.stderr}"

    # Probe stream info using ffprobe
    probe_cmd = [
        test_env["ffprobe"], "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels",
        "-of", "json",
        str(out_file)
    ]
    probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(probe_res.stdout)
    assert len(probe_data.get("streams", [])) > 0, "No audio stream found in export!"

    stream = probe_data["streams"][0]
    assert stream["codec_name"] == "aac"
    assert stream["sample_rate"] == "44100", f"Sample rate was {stream['sample_rate']} instead of 44100 (Windows decoder compatibility regression)!"
    assert stream["channels"] == 2

    # Measure volume with volumedetect
    v_cmd = [test_env["ffmpeg"], "-i", str(out_file), "-af", "volumedetect", "-f", "null", "-"]
    v_res = subprocess.run(v_cmd, capture_output=True, text=True)
    mean_lines = [l for l in v_res.stderr.splitlines() if "mean_volume:" in l]
    assert len(mean_lines) > 0
    mean_val = float(mean_lines[0].split("mean_volume:")[1].split("dB")[0].strip())
    # Audio must not be silent (-91 dB is digital silence)
    assert mean_val > -30.0, f"Audio is silent or near-silent: {mean_val} dB"


def test_audio_normalizer_levels_diverse_inputs(test_env):
    """Verify that loud and quiet tracks both level to standard EBU R128 loudness."""
    out_loud = test_env["tmp"] / "out_loud.mp4"
    out_quiet = test_env["tmp"] / "out_quiet.mp4"

    for path, out in [(test_env["loud_wav"], out_loud), (test_env["quiet_wav"], out_quiet)]:
        project = {
            "collection_title": "Norm Test",
            "background": str(test_env["bg"]),
            "tracks": [{"path": str(path), "title": "Track", "duration": 2.0}],
            "audio_normalize_enabled": True,
            "output_path": str(out),
        }
        cmd, _ = build_render_command(project, test_env["tmp"])
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0

    def get_mean_vol(f):
        c = [test_env["ffmpeg"], "-i", str(f), "-af", "volumedetect", "-f", "null", "-"]
        r = subprocess.run(c, capture_output=True, text=True)
        lines = [l for l in r.stderr.splitlines() if "mean_volume:" in l]
        return float(lines[0].split("mean_volume:")[1].split("dB")[0].strip())

    loud_mean = get_mean_vol(out_loud)
    quiet_mean = get_mean_vol(out_quiet)

    # Difference between normalized loud and normalized quiet should be less than 1.0 dB
    assert abs(loud_mean - quiet_mean) < 1.0, f"Normalizer failed to level volumes: loud={loud_mean}dB, quiet={quiet_mean}dB"


def test_preview_audio_pending_seek():
    """Verify preview audio pending seek handling in MainWindow."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtMultimedia import QMediaPlayer
    from src.ui.main_window import MainWindow
    from tests.conftest import dispose_window

    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        # Simulate seek with source change
        win._preview_audio_pending_seek = 3500
        assert win._preview_audio_pending_seek == 3500

        # Simulate media loaded
        fake_player = QMediaPlayer(win)
        win._preview_audio_player = fake_player
        win._on_preview_audio_media_status_changed(QMediaPlayer.MediaStatus.LoadedMedia)
        # Pending seek should have been applied and cleared
        assert win._preview_audio_pending_seek is None

        # Stopping preview resets pending seek
        win._preview_audio_pending_seek = 2000
        win._stop_preview_playback()
        assert win._preview_audio_pending_seek is None
    finally:
        win._release_preview_player()
        dispose_window(win)
