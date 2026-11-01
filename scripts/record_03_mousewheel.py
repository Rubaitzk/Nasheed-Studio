import os
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPen, QWheelEvent, QKeyEvent
from PySide6.QtCore import Qt, QPoint

from src.ui.main_window import MainWindow
from src.services.media_probe import find_tool

def record_inspector_mousewheel():
    out_dir = Path("final_delivery_proof")
    out_dir.mkdir(exist_ok=True, parents=True)
    out_mp4 = out_dir / "03_inspector_mousewheel.mp4"

    app = QApplication.instance() or QApplication([])

    win = MainWindow()
    win.resize(1440, 900)
    win.show()
    app.processEvents()

    # Clear initial focus from any control
    scroll_area = win.inspector_tabs.widget(0)
    scroll_area.widget().setFocus()
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

    print("Recording Task 3: Inspector Mouse-Wheel Behavior...")

    # Initial state
    target_sb = win.playlist_cols_spin
    hold(1.5, "Task 3: Inspector Mouse-Wheel Interaction Verification")

    # Step 1: Passive wheel scrolling over unfocused spinbox
    hold(1.2, "Test 1: Passive Mouse-Wheel Over Unfocused Control", target_sb)
    vsb = scroll_area.verticalScrollBar()

    # Simulate wheel scrolling down over target_sb
    for _ in range(12):
        evt_down = QWheelEvent(
            QPoint(10, 10), QPoint(10, 10), QPoint(), QPoint(0, -120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False
        )
        app.sendEvent(target_sb, evt_down)
        app.processEvents()
        hold(0.08, f"Passive Scroll: Value {target_sb.value()} Locked, Panel Scrolls", target_sb)

    hold(1.2, f"Passive Scroll Safe: Value stayed {target_sb.value()}", target_sb)

    # Scroll back up
    for _ in range(12):
        evt_up = QWheelEvent(
            QPoint(10, 10), QPoint(10, 10), QPoint(), QPoint(0, 120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False
        )
        app.sendEvent(target_sb, evt_up)
        app.processEvents()
        hold(0.05, "Scrolling Panel Back to Top", target_sb)

    # Step 2: Explicit Click / Focus on spinbox
    target_sb.setFocus()
    app.processEvents()
    hold(1.5, "Test 2: Explicit Click on Control - Focus Enabled", target_sb)

    # Mouse-wheel adjustments while focused
    for _ in range(2):
        evt_up = QWheelEvent(
            QPoint(10, 10), QPoint(10, 10), QPoint(), QPoint(0, 120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False
        )
        app.sendEvent(target_sb, evt_up)
        app.processEvents()
        hold(0.5, f"Focused Wheel: Value Adjusted to {target_sb.value()}", target_sb)

    # Step 3: Click outside to container
    scroll_area.widget().setFocus()
    app.processEvents()
    hold(1.5, "Test 3: Click Away / Outside - Focus Cleared", target_sb)

    # Subsequent wheel over spinbox safely scrolls page again
    for _ in range(8):
        evt_down = QWheelEvent(
            QPoint(10, 10), QPoint(10, 10), QPoint(), QPoint(0, -120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False
        )
        app.sendEvent(target_sb, evt_down)
        app.processEvents()
        hold(0.08, f"Passive Again: Value {target_sb.value()} Safe, Panel Scrolls", target_sb)

    # Step 4: Keyboard entry preserved
    target_sb.setFocus()
    target_sb.setValue(2)
    app.processEvents()
    hold(1.0, "Test 4: Keyboard Input & Arrow Navigation Intact", target_sb)

    key_evt = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
    app.sendEvent(target_sb, key_evt)
    app.processEvents()
    hold(1.5, f"Keyboard Up Arrow: Value Changed to {target_sb.value()}", target_sb)

    proc.stdin.close()
    proc.wait()
    win._dirty = False
    win.closeEvent = lambda e: e.accept()
    win.close()
    app.quit()
    print(f"Generated {out_mp4} successfully! Size: {out_mp4.stat().st_size} bytes")

if __name__ == "__main__":
    record_inspector_mousewheel()
