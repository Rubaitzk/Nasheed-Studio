import sys
import os
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFontDatabase, QImage, QColor

from src.ui.main_window import MainWindow
from src.ui.widgets.particle_canvas import ParticleOverlayWidget
from src.services.particle_service import generate_particle_loop_video
import shutil
import subprocess

def main():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication(sys.argv)
    
    font_path = "C:/Windows/Fonts/segoeui.ttf"
    if os.path.exists(font_path):
        QFontDatabase.addApplicationFont(font_path)

    out_dir = ROOT_DIR / "tests" / "artifacts" / "item1"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Capturing Item 1 preview frames...")
    win = MainWindow()
    win.show()
    win.resize(1280, 800)
    app.processEvents()

    sample_bg = str((ROOT_DIR / "tests/fixtures/images/sample_bg.png").resolve())
    sample_tone = str((ROOT_DIR / "tests/fixtures/audio/sample_tone.wav").resolve())
    if os.path.exists(sample_bg):
        win.background_path = sample_bg
    if os.path.exists(sample_tone):
        win.tracks = [
            {"path": sample_tone, "title": "01. Beautiful Nasheed Track - Artist Name", "duration": 180.0},
            {"path": sample_tone, "title": "02. Second Nasheed Track - Vocals Only", "duration": 200.0}
        ]
        win.collection_title.setText("BISMILLAH - NASHEED TITLE")
        win._committed_title = "BISMILLAH - NASHEED TITLE"
        win._refresh_tracks()
    win.particles_check.setChecked(True)
    win.particles_style_combo.setCurrentText("Wind Streaks")
    win.particles_speed_spin.setValue(1.0)
    win.particles_count_spin.setValue(50)
    win.particles_angle_spin.setValue(225.0)
    win._refresh_preview()
    app.processEvents()

    canvas = win.preview_frame
    overlay = win.particle_overlay
    overlay.show()
    app.processEvents()

    # Capture preview at t=0
    # Pre-warm already done on overlay resize / init
    p0 = canvas.grab()
    p0.save(str(out_dir / "preview_t0.png"))
    print("Saved preview_t0.png")

    # Advance 1.0s (30 frames)
    for _ in range(30):
        overlay._update_particles()
    p1 = canvas.grab()
    p1.save(str(out_dir / "preview_t1.png"))
    print("Saved preview_t1.png")

    # Advance another 2.0s (60 frames to reach t=3.0s)
    for _ in range(60):
        overlay._update_particles()
    p3 = canvas.grab()
    p3.save(str(out_dir / "preview_t3.png"))
    print("Saved preview_t3.png")

    # Now render 5s clip with FFmpeg using particle_service (.mov required for qtrle codec)
    video_path = out_dir / "wind_streaks_5s.mov"
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    print(f"FFmpeg binary: {ffmpeg_bin}")

    print("Generating particle loop video...")
    generate_particle_loop_video(
        output_path=str(video_path),
        duration=5.0,
        fps=30,
        width=1280,
        height=720,
        style="Wind Streaks",
        quantity=50,
        speed=2,
        color="#FFFFFF",
        angle=225.0,
        ffmpeg_bin=ffmpeg_bin
    )
    print(f"Rendered {video_path}")

    # Extract frames at t=0, t=1.0, t=3.0 from MP4
    # Note: t=0 frame
    cmd0 = [ffmpeg_bin, "-y", "-ss", "00:00:00.000", "-i", str(video_path), "-vframes", "1", str(out_dir / "render_t0.png")]
    cmd1 = [ffmpeg_bin, "-y", "-ss", "00:00:01.000", "-i", str(video_path), "-vframes", "1", str(out_dir / "render_t1.png")]
    cmd3 = [ffmpeg_bin, "-y", "-ss", "00:00:03.000", "-i", str(video_path), "-vframes", "1", str(out_dir / "render_t3.png")]
    for cmd in (cmd0, cmd1, cmd3):
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("Extracted render_t0.png, render_t1.png, render_t3.png")

    win.closeEvent = lambda event: event.accept()
    win.close()
    print("Item 1 visuals captured successfully.", flush=True)

if __name__ == "__main__":
    main()
