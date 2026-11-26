import sys
import os
import shutil
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtCore import Qt

from src.ui.main_window import MainWindow
from src.services.particle_service import PARTICLE_STYLES, generate_particle_loop_video


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    out_dir = ROOT_DIR / "tests" / "artifacts" / "item2"
    out_dir.mkdir(parents=True, exist_ok=True)

    win = MainWindow()
    win.resize(1280, 720)
    win.show()
    app.processEvents()

    win.particles_check.setChecked(True)
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"

    sizes_to_test = [1, 3, 10, 20]

    # Capture for each style at sizes 1, 3, 10, 20
    for style in PARTICLE_STYLES:
        sanitized = style.lower().replace(" ", "_").replace("&", "and").replace("-", "_")
        win.particles_style_combo.setCurrentText(style)
        app.processEvents()

        for s in sizes_to_test:
            win.particles_size_spin.setValue(s)
            app.processEvents()

            # Grab preview
            preview_img = win.particle_overlay.grab()
            preview_path = out_dir / f"preview_{sanitized}_size{s}.png"
            preview_img.save(str(preview_path))

    # Also capture render frames for representative styles (Wind Streaks, Drifting Flecks) at sizes 1, 3, 10, 20
    for style in ["Wind Streaks", "Drifting Flecks"]:
        sanitized = style.lower().replace(" ", "_")
        for s in sizes_to_test:
            mov_path = out_dir / f"render_{sanitized}_size{s}.mov"
            frame_path = out_dir / f"render_{sanitized}_size{s}.png"
            generate_particle_loop_video(
                output_path=mov_path,
                duration=1.0,
                fps=30,
                width=1280,
                height=720,
                style=style,
                quantity=30,
                speed=1,
                size=s,
                ffmpeg_bin=ffmpeg_bin
            )
            cmd = [ffmpeg_bin, "-y", "-ss", "00:00:00.000", "-i", str(mov_path), "-vframes", "1", str(frame_path)]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if mov_path.exists():
                mov_path.unlink()  # clean up temp mov

    win.closeEvent = lambda event: event.accept()
    win.close()
    print("Item 2 visual artifacts captured successfully.", flush=True)


if __name__ == "__main__":
    main()
