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

def record_intro_y_offsets():
    out_dir = Path("final_delivery_proof")
    out_dir.mkdir(exist_ok=True, parents=True)
    out_mp4 = out_dir / "04_intro_y_offsets.mp4"

    app = QApplication.instance() or QApplication([])

    temp_dir = tempfile.TemporaryDirectory()
    tmp_path = Path(temp_dir.name)

    bg_path = tmp_path / "bg.png"
    Image.new("RGB", (1280, 720), (22, 28, 26)).save(str(bg_path))

    logo_path = tmp_path / "logo.png"
    Image.new("RGBA", (140, 140), (82, 201, 122, 255)).save(str(logo_path))

    # Short dummy audio
    ffmpeg = find_tool("ffmpeg")
    audio_path = tmp_path / "t.mp3"
    subprocess.run([
        ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-c:a", "libmp3lame", str(audio_path)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    win = MainWindow()
    win.resize(1440, 900)
    win.show()
    app.processEvents()

    win.background_path = str(bg_path)
    win.logo_path = str(logo_path)
    win.collection_title.setText("Prophetic Pearls")
    win.website_edit.setText("www.nasheedstudio.com")
    win.tracks = [{
        "title": "Tala al-Badru Alayna",
        "path": str(audio_path),
        "duration": 5.0,
        "artist": "NCN Voices"
    }]
    win._refresh_tracks()

    # Enable intro
    win.intro_check.setChecked(True)
    win.intro_dur_spin.setValue(4.0)

    # Switch to Sound tab (tab 3)
    win.inspector_tabs.setCurrentIndex(3)
    app.processEvents()
    win._schedule_preview(50)
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

    def write_frame(label="", highlight_widget=None):
        qimg = win.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        canvas = QImage(canvas_w, canvas_h, QImage.Format.Format_RGBA8888)
        canvas.fill(QColor("#0d110e"))
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        ox = (canvas_w - qimg.width()) // 2
        oy = (canvas_h - qimg.height()) // 2
        painter.drawImage(ox, oy, qimg)

        if highlight_widget:
            tl = highlight_widget.mapTo(win, highlight_widget.rect().topLeft())
            br = highlight_widget.mapTo(win, highlight_widget.rect().bottomRight())
            hx = ox + tl.x() - 4
            hy = oy + tl.y() - 4
            hw = (br.x() - tl.x()) + 8
            hh = (br.y() - tl.y()) + 8
            painter.setPen(QPen(QColor("#52c97a"), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(hx, hy, hw, hh, 4, 4)

        if label:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 190))
            painter.drawRoundedRect(ox + 20, oy + 20, 600, 42, 6, 6)
            painter.setPen(QPen(QColor("#52c97a")))
            font = QFont("Segoe UI", 12, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(ox + 35, oy + 47, label)

        painter.end()
        raw_bytes = bytes(canvas.constBits())
        proc.stdin.write(raw_bytes)

    def hold(seconds, label="", highlight_widget=None):
        count = int(seconds * fps)
        for _ in range(count):
            app.processEvents()
            write_frame(label, highlight_widget)

    print("Recording Task 4: Intro Y-Offset Controls...")

    # Initial state
    hold(1.5, "Task 4: Intro Elements Y-Offset Controls")

    # Scroll down to show Intro Title, Logo, and Watermark Y-offsets
    scroll_area = win.inspector_tabs.widget(3)
    vsb = scroll_area.verticalScrollBar()
    for v in range(0, 320, 16):
        vsb.setValue(v)
        app.processEvents()
        hold(0.04, "Navigating to Intro Element Controls")

    hold(1.0, "Intro Logo Y-Offset, Title Y-Offset, Watermark Y-Offset Controls")

    # 1. Adjust Logo Y-offset: move up and down
    for y in range(0, -65, -5):
        win.intro_logo_y_offset_spin.setValue(y)
        win._on_intro_param_changed()
        app.processEvents()
        hold(0.08, f"Intro Logo Y-Offset: {y}px (Moving Logo Up)", win.intro_logo_y_offset_spin)

    hold(1.2, "Intro Logo Shifted Up - Preview Updated Live", win.intro_logo_y_offset_spin)

    # 2. Adjust Title Y-offset: move title down
    for y in range(0, 55, 5):
        win.intro_title_y_offset_spin.setValue(y)
        win._on_intro_param_changed()
        app.processEvents()
        hold(0.08, f"Intro Title Y-Offset: +{y}px (Moving Title Down)", win.intro_title_y_offset_spin)

    hold(1.2, "Intro Title Shifted Down - Live Preview Synced", win.intro_title_y_offset_spin)

    # 3. Adjust Watermark Y-offset: move watermark up
    for y in range(0, -45, -5):
        win.intro_website_y_offset_spin.setValue(y)
        win._on_intro_param_changed()
        app.processEvents()
        hold(0.08, f"Intro Watermark Y-Offset: {y}px (Moving Watermark Up)", win.intro_website_y_offset_spin)

    hold(1.5, "All 3 Intro Elements Independently Repositioned", win.intro_website_y_offset_spin)

    # Reset offsets back to 0
    win.intro_logo_y_offset_spin.setValue(0)
    win.intro_title_y_offset_spin.setValue(0)
    win.intro_website_y_offset_spin.setValue(0)
    win._on_intro_param_changed()
    app.processEvents()
    hold(1.2, "Intro Offsets Reset to Defaults (0 px)")

    proc.stdin.close()
    proc.wait()
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
    record_intro_y_offsets()
