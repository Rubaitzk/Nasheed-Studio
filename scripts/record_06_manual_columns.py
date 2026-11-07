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

def record_manual_column_distribution():
    out_dir = Path("final_delivery_proof")
    out_dir.mkdir(exist_ok=True, parents=True)
    out_mp4 = out_dir / "06_manual_column_distribution.mp4"

    app = QApplication.instance() or QApplication([])

    temp_dir = tempfile.TemporaryDirectory()
    tmp_path = Path(temp_dir.name)

    bg_path = tmp_path / "bg.png"
    Image.new("RGB", (1280, 720), (22, 28, 25)).save(str(bg_path))

    ffmpeg = find_tool("ffmpeg")
    audio_path = tmp_path / "dummy.mp3"
    subprocess.run([
        ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:a", "libmp3lame", str(audio_path)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    win = MainWindow()
    win.resize(1440, 900)
    win.show()
    app.processEvents()

    win.background_path = str(bg_path)
    win.collection_title.setText("Nasheed Collection")

    # Populate 16 tracks (>12 tracks)
    track_titles = [
        "01. Tala'al Badru 'Alayna",
        "02. Mawlaya Salli Wa Sallim",
        "03. Qamarun Sidnan Nabi",
        "04. Ya Taiba Ya Taiba",
        "05. Assalamu Alayka",
        "06. Hasbi Rabbi Jallallah",
        "07. Kun Anta",
        "08. Rahman Ya Rahman",
        "09. Labbaik Allahumma Labbaik",
        "10. Fastabiqul Khairat",
        "11. Subhanallah Walhamdulillah",
        "12. Antassalam Wa Minkassalam",
        "13. Noorul Huda",
        "14. Ashraqat Nafsi Bi Hubb",
        "15. Ya Nabi Salam Alayka",
        "16. Salawatullah Ala Ahmad"
    ]
    win.tracks = [
        {"title": t, "path": str(audio_path), "duration": 180.0, "artist": "NCN Artists"}
        for t in track_titles
    ]
    win._refresh_tracks()

    # Layout tab
    win.inspector_tabs.setCurrentIndex(0)
    win.template_combo.setCurrentText("Two-column")
    win.playlist_cols_spin.setValue(2)
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
            painter.drawRoundedRect(ox + 20, oy + 20, 640, 42, 6, 6)
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

    print("Recording Task 6: Manual Column Distribution...")

    # 1. Automatic mode
    hold(1.5, "Task 6: Manual Column Distribution Verification (>12 Tracks)")
    hold(1.5, "Distribution Mode: Automatic (Default Auto-Balanced 8 / 8)", win.playlist_col_mode_combo)

    # 2. Switch to Manual mode
    win.playlist_col_mode_combo.setCurrentText("Manual")
    app.processEvents()
    hold(1.5, "Distribution Mode: Manual Activated -> 'Items Per Col' Visible", win.playlist_col_dist_edit)

    # 3. Enter '11, 5'
    win.playlist_col_dist_edit.setText("11, 5")
    win._on_layout_param_changed()
    app.processEvents()
    hold(2.0, "Manual Distribution: '11, 5' -> Col 1 has 11, Col 2 has 5", win.playlist_col_dist_edit)

    # 4. Enter '14, 2'
    win.playlist_col_dist_edit.setText("14, 2")
    win._on_layout_param_changed()
    app.processEvents()
    hold(2.0, "Manual Distribution: '14, 2' -> Col 1 has 14, Col 2 has 2", win.playlist_col_dist_edit)

    # 5. Enter '7, 9'
    win.playlist_col_dist_edit.setText("7, 9")
    win._on_layout_param_changed()
    app.processEvents()
    hold(2.0, "Manual Distribution: '7, 9' -> Col 1 has 7, Col 2 has 9", win.playlist_col_dist_edit)

    # 6. Switch back to Automatic
    win.playlist_col_mode_combo.setCurrentText("Automatic")
    app.processEvents()
    hold(1.8, "Switching Back to Automatic: Auto-Balance Restored (8 / 8)", win.playlist_col_mode_combo)

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
    record_manual_column_distribution()
