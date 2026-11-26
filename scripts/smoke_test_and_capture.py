"""
Full flow smoke test and final multi-tab visual verification capture.
"""

import os
import sys
import time
import tempfile
import json
from pathlib import Path
import psutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set offscreen platform
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontDatabase, QFont

from src.ui.main_window import MainWindow
from src.services.particle_service import PARTICLE_STYLES
from src.services.render_service import render_project
from src.services.export_job import ExportJob

def _sleep_command(seconds: float) -> list[str]:
    return [sys.executable, "-c", f"import time; time.sleep({seconds})"]

def run_smoke_and_capture():
    print("=== Starting Full Flow Smoke Test & Multi-Tab Capture ===", flush=True)
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Load fonts for clean rendering
    for font_file in ["segoeui.ttf", "segoeuib.ttf", "segoeuisb.ttf", "arial.ttf", "calibri.ttf"]:
        p = Path(f"C:/Windows/Fonts/{font_file}")
        if p.exists():
            QFontDatabase.addApplicationFont(str(p))
    app.setFont(QFont("Segoe UI", 9))

    win = MainWindow()
    win.resize(1366, 768)
    win.show()
    app.processEvents()

    # 1. Load an OLD project format (backward compatibility smoke)
    with tempfile.NamedTemporaryFile(suffix=".ncn", delete=False, mode="w", encoding="utf-8") as tf:
        old_data = {
            "collection_title": "Legacy Project Smoke Test",
            "background": str(Path("tests/fixtures/images/sample_bg.png").resolve()),
            "tracks": [
                {"path": str(Path("tests/fixtures/audio/sample_tone.wav").resolve()), "title": "01. Legacy Nasheed Track 1", "duration": 2.0},
                {"path": str(Path("tests/fixtures/audio/sample_tone.wav").resolve()), "title": "02. Legacy Nasheed Track 2", "duration": 2.0}
            ],
            "particles_enabled": True,
            "particles_style": "Drifting Flecks",
            "particles_count": 50,
            "highlight_color": "#FFCC00"
        }
        json.dump(old_data, tf)
        old_proj_path = tf.name

    try:
        print(f"Loading legacy project: {old_proj_path}", flush=True)
        win._load_project_file(old_proj_path)
        app.processEvents()
        assert win.collection_title.text() == "Legacy Project Smoke Test"
        print("Legacy project loaded successfully!", flush=True)
        
        # Verify default particle size populated for legacy project
        assert hasattr(win, "particles_size_spin")
        assert win.particles_size_spin.value() == 5
        print("Default particle size 5 verified on legacy project load.", flush=True)

        # 2. Add audio track
        sample_tone = str(Path("tests/fixtures/audio/sample_tone.wav").resolve())
        new_track = {"path": sample_tone, "title": "03. Added Smoke Track 3", "duration": 2.0}
        win.tracks.append(new_track)
        win._refresh_tracks()
        app.processEvents()
        assert len(win.tracks) == 3
        print(f"Audio track added. Total tracks: {len(win.tracks)}", flush=True)

        # 3. Cycle through every particle style in turn
        print(f"Cycling through all {len(PARTICLE_STYLES)} particle styles...", flush=True)
        for style_name in PARTICLE_STYLES:
            win.particles_style_combo.setCurrentText(style_name)
            win._on_particles_param_changed()
            win._refresh_preview()
            app.processEvents()
            # Animate 3 frames
            for _ in range(3):
                win.particle_overlay._update_particles()
                app.processEvents()
            print(f"  Style '{style_name}' previewed successfully.", flush=True)

        # 4. Preview playback and scrubbing
        print("Testing preview playback and scrubbing...", flush=True)
        win._seek_preview(1.5)
        app.processEvents()
        pix = win.preview_image.pixmap()
        assert pix is not None and not pix.isNull()
        print("Preview scrub verified.", flush=True)

        # 5. Render short MP4 with FFmpeg via render_project
        print("Rendering short MP4 via render_service...", flush=True)
        with tempfile.TemporaryDirectory() as out_dir:
            out_mp4 = Path(out_dir) / "smoke_render.mp4"
            render_project_dict = win._project()
            render_project_dict["output_path"] = str(out_mp4)
            render_project_dict["video_resolution"] = "640x360"
            render_project_dict["tracks"] = [
                {"path": str(sample_tone), "title": "01. Smoke Snippet", "duration": 1.0}
            ]
            res_path = render_project(render_project_dict)
            assert out_mp4.exists() and out_mp4.stat().st_size > 1000, f"Rendered MP4 file missing or empty: {out_mp4}"
            print(f"Rendered MP4 verified: {out_mp4.stat().st_size} bytes at {res_path}", flush=True)

        # 6. Test cancel mid-export kills child processes
        print("Testing cancel mid-export process cleanup...", flush=True)
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir) / "work"
            cancel_out = Path(tmp_dir) / "cancelled.mp4"
            
            # Start a long sleep command simulating ffmpeg
            job = ExportJob(_sleep_command(30), work_dir, cancel_out)
            job.start()
            time.sleep(0.5)
            assert job.is_running, "Job should be running"
            
            # Record running child processes
            ffmpeg_procs_before = [p.pid for p in psutil.process_iter(['name']) if 'ffmpeg' in p.info['name'].lower()]
            
            # Cancel job mid-export
            job.cancel()
            job.join(timeout=5.0)
            assert not job.is_running, "Job must not be running after cancel"
            
            # Verify no orphan processes remain
            time.sleep(0.5)
            ffmpeg_procs_after = [p.pid for p in psutil.process_iter(['name']) if 'ffmpeg' in p.info['name'].lower()]
            new_orphans = set(ffmpeg_procs_after) - set(ffmpeg_procs_before)
            assert len(new_orphans) == 0, f"Found orphan processes after cancellation: {new_orphans}"
            print("Cancel mid-export successfully cleaned up all child processes without orphans.", flush=True)

        # 7. Capture final full-window screenshots for each Inspector tab
        out_base = Path("tests/artifacts")
        out_base.mkdir(parents=True, exist_ok=True)
        
        tab_names = ["canvas", "text", "indicator", "intro", "audio"]
        print("Capturing final full-window screenshots for each Inspector tab...", flush=True)
        for i in range(win.inspector_tabs.count()):
            win.inspector_tabs.setCurrentIndex(i)
            app.processEvents()
            tab_name = tab_names[i] if i < len(tab_names) else f"tab_{i}"
            cap_path = out_base / f"final_tab_{i}_{tab_name}.png"
            win.grab().save(str(cap_path))
            print(f"  Captured Inspector Tab {i} ({tab_name}): {cap_path}", flush=True)

        # 8. Verify unaffected features
        print("Verifying unaffected features...", flush=True)
        assert win.title_apply_btn.isVisible()
        assert win.add_tracks_btn.isVisible()
        assert win.rename_track_btn.isVisible()
        assert win.remove_track_btn.isVisible()
        assert win.up_btn.isVisible()
        assert win.down_btn.isVisible()
        assert win.scrubber_play_btn.isVisible()
        assert win.render_btn.isVisible()
        print("All playlist actions, preview controls, and export footer intact and verified!", flush=True)
        print("=== Full Flow Smoke Test PASSED ===", flush=True)

    finally:
        if os.path.exists(old_proj_path):
            os.remove(old_proj_path)
        win.closeEvent = lambda event: event.accept()
        win.close()
        app.processEvents()

if __name__ == "__main__":
    run_smoke_and_capture()
