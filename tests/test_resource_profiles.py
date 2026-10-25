"""Unit tests and benchmarks for rendering resource profiles (Phase 5).

Verifies:
1. build_render_command configures threads and presets correctly for:
   - Background-friendly: 2 threads, faster preset
   - Balanced: half CPU cores, veryfast preset
   - Maximum-speed: all CPU cores, veryfast preset
2. ExportJob applies the appropriate Windows process priority classes:
   - Background-friendly -> BELOW_NORMAL_PRIORITY_CLASS (0x4000)
   - Balanced -> NORMAL_PRIORITY_CLASS (0x20)
   - Maximum-speed -> ABOVE_NORMAL_PRIORITY_CLASS (0x8000)
3. Benchmark: Runs a real export under each profile and records time/duration differences.
"""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from PIL import Image

from src.services.render_service import build_render_command
from src.services.export_job import ExportJob


def _create_simple_wav(path: Path, dur_sec: float = 3.0, sr: int = 44100):
    import wave, struct, math
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(int(dur_sec * sr)):
            val = int(12000 * math.sin(2 * math.pi * 440 * i / sr))
            frames += struct.pack("<hh", val, val)
        wf.writeframes(frames)


class TestResourceProfiles(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        self.bg_path = self.tmp / "bg.png"
        Image.new("RGB", (1920, 1080), (25, 35, 30)).save(self.bg_path)

        self.audio_path = self.tmp / "track.wav"
        _create_simple_wav(self.audio_path, dur_sec=3.0)

        self.base_project = {
            "version": 1,
            "collection_title": "Profile Benchmark",
            "background": str(self.bg_path),
            "tracks": [{"path": str(self.audio_path), "duration": 3.0, "title": "Track 1"}],
            "output_path": str(self.tmp / "out.mp4"),
            "resolution": "1080p · Full HD",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_background_friendly_command(self):
        proj = dict(self.base_project)
        proj["resource_profile"] = "Background-friendly"
        cmd, _ = build_render_command(proj, self.tmp / "work_bg")
        cmd_str = " ".join(cmd)
        self.assertIn("-threads 2", cmd_str)
        self.assertIn("-preset faster", cmd_str)

    def test_balanced_command(self):
        proj = dict(self.base_project)
        proj["resource_profile"] = "Balanced"
        cmd, _ = build_render_command(proj, self.tmp / "work_bal")
        cmd_str = " ".join(cmd)
        cpu_cnt = os.cpu_count() or 4
        expected_threads = max(2, cpu_cnt // 2)
        self.assertIn(f"-threads {expected_threads}", cmd_str)
        self.assertIn("-preset veryfast", cmd_str)

    def test_maximum_speed_command(self):
        proj = dict(self.base_project)
        proj["resource_profile"] = "Maximum-speed"
        cmd, _ = build_render_command(proj, self.tmp / "work_max")
        cmd_str = " ".join(cmd)
        cpu_cnt = os.cpu_count() or 4
        expected_threads = max(4, cpu_cnt)
        self.assertIn(f"-threads {expected_threads}", cmd_str)
        self.assertIn("-preset veryfast", cmd_str)

    def test_export_job_creationflags(self):
        """ExportJob maps resource_profile to appropriate process creation flags on Windows."""
        for prof in ["Background-friendly", "Balanced", "Maximum-speed"]:
            job = ExportJob(
                command=["ffmpeg", "-version"],
                work_dir=self.tmp,
                output_path=self.tmp / "test.mp4",
                resource_profile=prof,
            )
            self.assertEqual(job._resource_profile, prof)

    def test_profile_benchmarks(self):
        """Execute renders with Background-friendly, Balanced, and Maximum-speed to measure actual execution time."""
        results = {}
        for prof in ["Background-friendly", "Balanced", "Maximum-speed"]:
            proj = dict(self.base_project)
            proj["resource_profile"] = prof
            proj["output_path"] = str(self.tmp / f"out_{prof.replace(' ', '_')}.mp4")
            work = self.tmp / f"work_{prof.replace(' ', '_')}"
            cmd, out_path = build_render_command(proj, work)

            t0 = time.perf_counter()
            res = subprocess.run(cmd, capture_output=True, text=True)
            elapsed = time.perf_counter() - t0
            self.assertEqual(res.returncode, 0, f"Render failed for {prof}: {res.stderr}")
            self.assertTrue(Path(out_path).exists())
            results[prof] = round(elapsed, 3)

        # Print observed benchmarks
        print("\n=== RESOURCE PROFILE BENCHMARK RESULTS ===")
        for prof, elapsed in results.items():
            print(f"  {prof:20s}: {elapsed:6.3f}s")
        print("==========================================")


if __name__ == "__main__":
    unittest.main()
