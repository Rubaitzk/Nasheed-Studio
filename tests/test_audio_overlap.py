"""Regression test for sequential audio playback and boundary synchronization.

Verifies:
1. Three tracks with different durations play strictly sequentially without premature track start.
2. Track 3 does NOT start playing when Track 2 begins.
3. Output audio duration matches the sum of track durations (+ intro duration if enabled).
4. Intro silence prepends cleanly before Track 1.
5. Transition SFX mix cleanly at exact track boundary timestamps.
"""

import math
import struct
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from PIL import Image

from src.services.render_service import build_render_command, validate_project
from src.services.timeline import build_timeline
from src.services.media_probe import get_duration, find_tool


def _generate_tone_wav(path: Path, freq: float, duration_sec: float, sample_rate: int = 44100, amp: int = 16000) -> None:
    """Generate a clean dual-channel 16-bit PCM WAV tone at freq Hz."""
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        total_frames = int(duration_sec * sample_rate)
        frames = bytearray()
        for i in range(total_frames):
            val = int(amp * math.sin(2.0 * math.pi * freq * i / sample_rate))
            frames += struct.pack("<hh", val, val)
        wf.writeframes(frames)


def _measure_frequency_energies(raw_pcm: bytes, start_sec: float, duration_sec: float, freqs: list[float], sr: int = 44100) -> dict[float, float]:
    """Measure spectral energy at specific target frequencies using DFT correlation."""
    start_frame = int(start_sec * sr)
    num_frames = int(duration_sec * sr)
    samples = struct.unpack(f"<{len(raw_pcm) // 2}h", raw_pcm)

    chunk = samples[start_frame: start_frame + num_frames]
    if not chunk:
        return {f: 0.0 for f in freqs}

    energies = {}
    for f in freqs:
        re = sum(s * math.cos(2.0 * math.pi * f * i / sr) for i, s in enumerate(chunk))
        im = sum(s * math.sin(2.0 * math.pi * f * i / sr) for i, s in enumerate(chunk))
        energies[f] = math.sqrt(re**2 + im**2) / len(chunk)
    return energies


class TestSequentialAudioPlayback(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Background image
        self.bg_path = self.tmp / "bg.png"
        Image.new("RGB", (1920, 1080), color=(18, 24, 20)).save(self.bg_path)

        # Distinct frequencies for 3 tracks
        self.t1_freq = 440.0   # A4
        self.t2_freq = 880.0   # A5
        self.t3_freq = 1320.0  # E6

        self.t1_dur = 3.0
        self.t2_dur = 4.0
        self.t3_dur = 3.0

        self.t1_wav = self.tmp / "track1_440hz.wav"
        self.t2_wav = self.tmp / "track2_880hz.wav"
        self.t3_wav = self.tmp / "track3_1320hz.wav"

        _generate_tone_wav(self.t1_wav, self.t1_freq, self.t1_dur)
        _generate_tone_wav(self.t2_wav, self.t2_freq, self.t2_dur)
        _generate_tone_wav(self.t3_wav, self.t3_freq, self.t3_dur)

        self.tracks = [
            {"path": str(self.t1_wav), "duration": self.t1_dur, "title": "Nasheed One (440Hz)"},
            {"path": str(self.t2_wav), "duration": self.t2_dur, "title": "Nasheed Two (880Hz)"},
            {"path": str(self.t3_wav), "duration": self.t3_dur, "title": "Nasheed Three (1320Hz)"},
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_three_track_timeline_offsets(self):
        """Timeline must calculate strictly contiguous, cumulative intervals."""
        timeline = build_timeline(self.tracks)
        self.assertEqual(len(timeline), 3)

        # Track 1
        self.assertAlmostEqual(timeline[0].start, 0.0)
        self.assertAlmostEqual(timeline[0].end, 3.0)

        # Track 2
        self.assertAlmostEqual(timeline[1].start, 3.0)
        self.assertAlmostEqual(timeline[1].end, 7.0)

        # Track 3 (cumulative: 3.0 + 4.0 = 7.0, NOT 4.0!)
        self.assertAlmostEqual(timeline[2].start, 7.0)
        self.assertAlmostEqual(timeline[2].end, 10.0)

    def test_rendered_mp4_sequential_audio_no_overlap(self):
        """
        Render real MP4 with 3 distinct audio frequencies.
        Extract rendered PCM audio and verify spectral energy across all track regions:
        - When Track 2 plays, Track 3 MUST NOT be playing (energy at 1320Hz must be zero).
        - Track 3 only begins when Track 2 ends (at 7.0s).
        """
        out_mp4 = self.tmp / "seq_test_out.mp4"
        project = {
            "version": 1,
            "collection_title": "Audio Reliability Test",
            "background": str(self.bg_path),
            "tracks": self.tracks,
            "output_path": str(out_mp4),
            "resolution": "1080p · Full HD",
        }

        work_dir = self.tmp / "render_work"
        cmd, final_out = build_render_command(project, work_dir)
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"FFmpeg render failed: {res.stderr}")
        self.assertTrue(out_mp4.exists())

        # Probe final duration
        final_dur = get_duration(str(out_mp4))
        self.assertAlmostEqual(final_dur, 10.0, delta=0.2)

        # Extract 44.1kHz 16-bit mono PCM from the rendered MP4
        pcm_dump = self.tmp / "extracted_audio.raw"
        ffmpeg_bin = find_tool("ffmpeg")
        dump_cmd = [
            ffmpeg_bin, "-y", "-i", str(out_mp4),
            "-f", "s16le", "-ac", "1", "-ar", "44100",
            str(pcm_dump),
        ]
        res_dump = subprocess.run(dump_cmd, capture_output=True, text=True)
        self.assertEqual(res_dump.returncode, 0, f"PCM dump failed: {res_dump.stderr}")

        raw_pcm = pcm_dump.read_bytes()
        freqs = [self.t1_freq, self.t2_freq, self.t3_freq]

        # Region 1: Track 1 (t = 1.0s to 2.0s) -> Only 440Hz
        e1 = _measure_frequency_energies(raw_pcm, start_sec=1.0, duration_sec=1.0, freqs=freqs)
        self.assertGreater(e1[self.t1_freq], 3000)
        self.assertLess(e1[self.t2_freq], 100)
        self.assertLess(e1[self.t3_freq], 100)

        # Region 2: Track 2 (t = 4.0s to 5.5s) -> Only 880Hz
        # CRITICAL REGRESSION CHECK: Track 3 (1320Hz) must NOT be playing here!
        e2 = _measure_frequency_energies(raw_pcm, start_sec=4.0, duration_sec=1.5, freqs=freqs)
        self.assertLess(e2[self.t1_freq], 100)
        self.assertGreater(e2[self.t2_freq], 3000)
        self.assertLess(e2[self.t3_freq], 100, "Track 3 started prematurely while Track 2 was playing!")

        # Region 3: Track 3 (t = 8.0s to 9.5s) -> Only 1320Hz
        e3 = _measure_frequency_energies(raw_pcm, start_sec=8.0, duration_sec=1.5, freqs=freqs)
        self.assertLess(e3[self.t1_freq], 100)
        self.assertLess(e3[self.t2_freq], 100)
        self.assertGreater(e3[self.t3_freq], 3000)

    def test_audio_with_intro_silence(self):
        """With intro enabled, Track 1 audio begins only after intro_duration."""
        intro_sec = 2.0
        out_mp4 = self.tmp / "intro_audio_out.mp4"
        project = {
            "version": 1,
            "collection_title": "Intro Audio Test",
            "background": str(self.bg_path),
            "tracks": self.tracks,
            "intro_enabled": True,
            "intro_duration": intro_sec,
            "intro_animation": "Fade in / out",
            "output_path": str(out_mp4),
            "resolution": "1080p · Full HD",
        }

        work_dir = self.tmp / "intro_render_work"
        cmd, final_out = build_render_command(project, work_dir)
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"FFmpeg intro render failed: {res.stderr}")

        # Probe final duration: 2.0s intro + 10.0s tracks = 12.0s
        final_dur = get_duration(str(out_mp4))
        self.assertAlmostEqual(final_dur, 12.0, delta=0.2)

        pcm_dump = self.tmp / "intro_audio.raw"
        dump_cmd = [
            find_tool("ffmpeg"), "-y", "-i", str(out_mp4),
            "-f", "s16le", "-ac", "1", "-ar", "44100",
            str(pcm_dump),
        ]
        subprocess.run(dump_cmd, check=True, capture_output=True)
        raw_pcm = pcm_dump.read_bytes()
        freqs = [self.t1_freq, self.t2_freq, self.t3_freq]

        # Intro period (0.5s to 1.5s): silence, zero energy
        e_intro = _measure_frequency_energies(raw_pcm, start_sec=0.5, duration_sec=1.0, freqs=freqs)
        self.assertLess(e_intro[self.t1_freq], 10)
        self.assertLess(e_intro[self.t2_freq], 10)
        self.assertLess(e_intro[self.t3_freq], 10)

        # Track 1 period (2.5s to 3.5s): 440Hz
        e_t1 = _measure_frequency_energies(raw_pcm, start_sec=2.5, duration_sec=1.0, freqs=freqs)
        self.assertGreater(e_t1[self.t1_freq], 3000)
        self.assertLess(e_t1[self.t2_freq], 100)
        self.assertLess(e_t1[self.t3_freq], 100)

    def test_rendered_mp4_with_transition_sfx_no_track_overlap(self):
        """
        With transition SFX enabled, SFX mixes at track boundaries without causing
        Track 3 to bleed into Track 2 or tracks to play simultaneously.
        """
        sfx_freq = 2000.0
        sfx_wav = self.tmp / "sfx_transition.wav"
        _generate_tone_wav(sfx_wav, sfx_freq, duration_sec=1.0, amp=8000)

        out_mp4 = self.tmp / "sfx_audio_out.mp4"
        project = {
            "version": 1,
            "collection_title": "SFX Audio Overlap Test",
            "background": str(self.bg_path),
            "tracks": self.tracks,
            "transition_sfx_enabled": True,
            "transition_sfx_path": str(sfx_wav),
            "transition_sfx_volume": 0.5,
            "output_path": str(out_mp4),
            "resolution": "1080p · Full HD",
        }

        work_dir = self.tmp / "sfx_render_work"
        cmd, final_out = build_render_command(project, work_dir)
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"FFmpeg render with SFX failed: {res.stderr}")

        pcm_dump = self.tmp / "sfx_audio_dump.raw"
        dump_cmd = [
            find_tool("ffmpeg"), "-y", "-i", str(out_mp4),
            "-f", "s16le", "-ac", "1", "-ar", "44100",
            str(pcm_dump),
        ]
        subprocess.run(dump_cmd, check=True, capture_output=True)
        raw_pcm = pcm_dump.read_bytes()
        freqs = [self.t1_freq, self.t2_freq, self.t3_freq, sfx_freq]

        # Middle of Track 2 (t = 4.5s to 5.5s):
        # Only 880Hz must be present; Track 3 (1320Hz) and SFX (2000Hz) MUST NOT be playing here!
        e_t2 = _measure_frequency_energies(raw_pcm, start_sec=4.5, duration_sec=1.0, freqs=freqs)
        self.assertGreater(e_t2[self.t2_freq], 3000)
        self.assertLess(e_t2[self.t3_freq], 100, "Track 3 played over Track 2 when SFX was enabled!")
        self.assertLess(e_t2[sfx_freq], 100, "Transition SFX bled into Track 2 body!")

        # Middle of Track 3 (t = 8.0s to 9.0s):
        # Only 1320Hz must be present; Track 2 (880Hz) MUST NOT be playing here!
        e_t3 = _measure_frequency_energies(raw_pcm, start_sec=8.0, duration_sec=1.0, freqs=freqs)
        self.assertGreater(e_t3[self.t3_freq], 3000)
        self.assertLess(e_t3[self.t2_freq], 100, "Track 2 continued playing into Track 3!")
        self.assertLess(e_t3[sfx_freq], 100, "Transition SFX bled into Track 3 body!")


if __name__ == "__main__":
    unittest.main()
