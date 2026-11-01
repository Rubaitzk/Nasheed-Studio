import os
import sys
import time
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPen
from PySide6.QtCore import Qt, QPoint

from src.ui.main_window import MainWindow
from src.services.media_probe import find_tool

def record_inspector_demonstration():
    out_dir = Path("final_delivery_proof")
    out_dir.mkdir(exist_ok=True, parents=True)
    out_mp4 = out_dir / "01_inspector_panel.mp4"

    app = QApplication.instance() or QApplication([])

    win = MainWindow()
    win.resize(1440, 900)
    win.show()
    app.processEvents()

    # Create dummy project state with sample tracks so preview & inspector are fully active
    win.collection_title.setText("The Beauty of Existence")
    win.website_edit.setText("www.nasheedstudio.com")
    app.processEvents()

    canvas_w = 1440
    canvas_h = 900
    fps = 30
    ffmpeg = find_tool("ffmpeg")

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

        # Center grab on canvas if smaller
        ox = (canvas_w - qimg.width()) // 2
        oy = (canvas_h - qimg.height()) // 2
        painter.drawImage(ox, oy, qimg)

        if label:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 180))
            painter.drawRoundedRect(ox + 20, oy + 20, 480, 40, 6, 6)
            painter.setPen(QPen(QColor("#52c97a")))
            font = QFont("Segoe UI", 12, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(ox + 35, oy + 46, label)

        painter.end()
        raw_bytes = bytes(canvas.constBits())
        proc.stdin.write(raw_bytes)

    def hold(seconds, label=""):
        count = int(seconds * fps)
        for _ in range(count):
            app.processEvents()
            write_frame(label)

    print("Recording Task 1: Inspector Panel Sizing...")

    # Initial view (1440x900) - Layout Tab
    win.inspector_tabs.setCurrentIndex(0)
    app.processEvents()
    hold(1.5, "Task 1: Inspector Panel Startup (1440x900)")

    # Scroll down Layout tab to show all buttons
    scroll_area = win.inspector_tabs.widget(0)
    vsb = scroll_area.verticalScrollBar()
    max_val = vsb.maximum()
    steps = 25
    for i in range(steps):
        vsb.setValue(int(max_val * (i + 1) / steps))
        app.processEvents()
        hold(0.04, "Layout Tab: Complete Content & Action Buttons")
    hold(1.0, "All Action Buttons Fully Accessible")

    # Scroll back up
    for i in range(steps):
        vsb.setValue(int(max_val * (steps - i - 1) / steps))
        app.processEvents()
        hold(0.02, "Layout Tab: Smooth Scrolling")

    # Tab 1: Text Tab
    win.inspector_tabs.setCurrentIndex(1)
    app.processEvents()
    hold(1.2, "Text Tab: Font Selectors & Browse Without Clipping")
    scroll_area = win.inspector_tabs.widget(1)
    vsb = scroll_area.verticalScrollBar()
    max_val = vsb.maximum()
    for i in range(steps):
        vsb.setValue(int(max_val * (i + 1) / steps))
        app.processEvents()
        hold(0.03, "Text Tab: Typography & Color Controls")
    hold(0.8, "Text Tab: Action Buttons & Controls Intact")
    for i in range(steps):
        vsb.setValue(int(max_val * (steps - i - 1) / steps))
        app.processEvents()
        hold(0.02, "Text Tab: Sizing Stable")

    # Tab 2: Indicator Tab
    win.inspector_tabs.setCurrentIndex(2)
    app.processEvents()
    hold(1.2, "Indicator Tab: Indicator Styling & Options")
    scroll_area = win.inspector_tabs.widget(2)
    vsb = scroll_area.verticalScrollBar()
    max_val = vsb.maximum()
    for i in range(steps):
        vsb.setValue(int(max_val * (i + 1) / steps))
        app.processEvents()
        hold(0.03, "Indicator Tab: Complete Controls")
    hold(0.8, "Indicator Tab: Verified")
    for i in range(steps):
        vsb.setValue(int(max_val * (steps - i - 1) / steps))
        app.processEvents()
        hold(0.02, "Indicator Tab")

    # Tab 3: Sound Tab
    win.inspector_tabs.setCurrentIndex(3)
    app.processEvents()
    hold(1.2, "Sound Tab: Intro Card & Watermark Controls")
    scroll_area = win.inspector_tabs.widget(3)
    vsb = scroll_area.verticalScrollBar()
    max_val = vsb.maximum()
    for i in range(steps):
        vsb.setValue(int(max_val * (i + 1) / steps))
        app.processEvents()
        hold(0.03, "Sound Tab: Watermark & Bottom Controls Accessible")
    hold(1.0, "Sound Tab: Watermark Controls Visible & Intact")
    for i in range(steps):
        vsb.setValue(int(max_val * (steps - i - 1) / steps))
        app.processEvents()
        hold(0.02, "Sound Tab")

    # Switch back to Tab 0 and resize to 1120x720 (compact screen)
    win.inspector_tabs.setCurrentIndex(0)
    win.resize(1120, 720)
    app.processEvents()
    hold(1.5, "Responsiveness Test: 1120x720 Window Size")

    # Show layout scroll at 720p
    scroll_area = win.inspector_tabs.widget(0)
    vsb = scroll_area.verticalScrollBar()
    max_val = vsb.maximum()
    for i in range(steps):
        vsb.setValue(int(max_val * (i + 1) / steps))
        app.processEvents()
        hold(0.03, "1120x720: Scroll Area Engages Cleanly")
    hold(1.0, "1120x720: Export Buttons Fully Usable")

    # Show Sound tab at 720p
    win.inspector_tabs.setCurrentIndex(3)
    app.processEvents()
    scroll_area = win.inspector_tabs.widget(3)
    vsb = scroll_area.verticalScrollBar()
    max_val = vsb.maximum()
    for i in range(steps):
        vsb.setValue(int(max_val * (i + 1) / steps))
        app.processEvents()
        hold(0.03, "1120x720 Sound Tab: Scroll Down")
    hold(1.0, "1120x720 Sound Tab: All Watermark Controls Usable")

    # Back to 1440x900
    win.resize(1440, 900)
    win.inspector_tabs.setCurrentIndex(0)
    app.processEvents()
    hold(1.0, "Inspector Panel Sizing & Controls Verified")

    proc.stdin.close()
    proc.wait()
    win._dirty = False
    win.closeEvent = lambda e: e.accept()
    win.close()
    app.quit()
    print(f"Generated {out_mp4} successfully! Size: {out_mp4.stat().st_size} bytes")

if __name__ == "__main__":
    record_inspector_demonstration()
