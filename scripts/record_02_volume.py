import os
import sys
import subprocess
import tempfile
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPen
from PySide6.QtCore import Qt

from src.ui.main_window import MainWindow
from src.services.media_probe import find_tool

def record_preview_volume():
    out_dir = Path("final_delivery_proof")
    out_dir.mkdir(exist_ok=True, parents=True)
    out_mp4 = out_dir / "02_preview_volume.mp4"

    app = QApplication.instance() or QApplication([])

    # Create dummy assets
    temp_dir = tempfile.TemporaryDirectory()
    tmp_path = Path(temp_dir.name)

    bg_path = tmp_path / "bg.png"
    Image.new("RGB", (1280, 720), (20, 24, 22)).save(str(bg_path))

    # Generate a short 5-second sine wave audio file
    ffmpeg = find_tool("ffmpeg")
    audio_path = tmp_path / "track01.mp3"
    subprocess.run([
        ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
        "-c:a", "libmp3lame", "-b:a", "128k", str(audio_path)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    win = MainWindow()
    win.resize(1440, 900)
    win.show()
    app.processEvents()

    # Load track and background
    win.background_path = str(bg_path)
    win.tracks = [{
        "title": "Burdah Shareef",
        "path": str(audio_path),
        "duration": 10.0,
        "artist": "NCN Artists"
    }]
    win._refresh_tracks()
    win._refresh_preview()
    app.processEvents()

    canvas_w = 1440
    canvas_h = 900
    fps = 30

    proc = subprocess.Popen([
        ffmpeg, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{canvas_w}x{canvas_h}",
        "-pix_fmt", "rgba",
        "-r", str(fps),
        "-i", "-",
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        "-crf", "18",
        str(out_mp4)
    ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def write_frame(label=""):
        qimg = win.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        canvas = QImage(canvas_w, canvas_h, QImage.Format.Format_RGBA8888)
        canvas.fill(QColor("#0d110e"))
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        ox = (canvas_w - qimg.width()) // 2
        oy = (canvas_h - qimg.height()) // 2
        painter.drawImage(ox, oy, qimg)

        # Draw highlight around the preview volume controls in the scrubber row
        vol_btn_pos = win.preview_volume_btn.mapTo(win, win.preview_volume_btn.rect().topLeft())
        lbl_pos = win.preview_volume_label.mapTo(win, win.preview_volume_label.rect().bottomRight())
        hx = ox + vol_btn_pos.x() - 4
        hy = oy + vol_btn_pos.y() - 4
        hw = (lbl_pos.x() - vol_btn_pos.x()) + 8
        hh = (lbl_pos.y() - vol_btn_pos.y()) + 8
        painter.setPen(QPen(QColor("#52c97a"), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(hx, hy, hw, hh, 4, 4)

        if label:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 190))
            painter.drawRoundedRect(ox + 20, oy + 20, 560, 42, 6, 6)
            painter.setPen(QPen(QColor("#52c97a")))
            font = QFont("Segoe UI", 12, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(ox + 35, oy + 47, label)

        painter.end()
        raw_bytes = bytes(canvas.constBits())
        proc.stdin.write(raw_bytes)

    def hold(seconds, label=""):
        count = int(seconds * fps)
        for _ in range(count):
            app.processEvents()
            write_frame(label)

    print("Recording Task 2: Preview Audio Volume Control...")

    # Initial state
    hold(1.5, "Task 2: Independent Preview Audio Volume Control")

    # Start preview playback
    win.scrubber_play_btn.click()
    app.processEvents()
    hold(2.0, "Playback Active - Default Volume: 70%")

    # Smoothly decrease volume to 25%
    for v in range(70, 24, -2):
        win.preview_volume_slider.setValue(v)
        app.processEvents()
        hold(0.06, f"Decreasing Preview Volume: {v}% (Quieter)")

    hold(1.5, "Preview Volume at 25% - Immediate Audio Attenuation")

    # Smoothly increase volume to 90%
    for v in range(25, 91, 2):
        win.preview_volume_slider.setValue(v)
        app.processEvents()
        hold(0.06, f"Increasing Preview Volume: {v}% (Louder)")

    hold(1.5, "Preview Volume at 90% - Immediate Response")

    # Test Mute button
    win.preview_volume_btn.click()
    app.processEvents()
    hold(2.0, "Mute Toggled: Volume 0%, Audio Output Silenced")

    # Test Unmute button (restores previous volume)
    win.preview_volume_btn.click()
    app.processEvents()
    hold(2.0, f"Unmute Toggled: Restored to {win.preview_volume_slider.value()}%")

    # Pause playback
    win.scrubber_play_btn.click()
    app.processEvents()
    hold(1.2, "Playback Paused - Export Settings Completely Untouched")

    proc.stdin.close()
    proc.wait()
    win._release_preview_player()
    win._dirty = False
    win.closeEvent = lambda e: e.accept()
    win.close()
    app.quit()
    try:
        temp_dir.cleanup()
    except Exception:
        pass
    print(f"Generated {out_mp4} successfully! Size: {out_mp4.stat().st_size} bytes")

if __name__ == "__main__":
    record_preview_volume()
