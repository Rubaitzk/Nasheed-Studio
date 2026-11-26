import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set offscreen platform
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSize, Qt

from src.ui.main_window import MainWindow

def capture_baseline():
    app = QApplication.instance() or QApplication(sys.argv)
    from PySide6.QtGui import QFontDatabase, QFont
    for font_file in ["segoeui.ttf", "segoeuib.ttf", "segoeuisb.ttf", "arial.ttf", "calibri.ttf"]:
        p = Path(f"C:/Windows/Fonts/{font_file}")
        if p.exists():
            QFontDatabase.addApplicationFont(str(p))
    app.setFont(QFont("Segoe UI", 9))
    win = MainWindow()
    win.resize(1366, 768)
    win.show()
    app.processEvents()

    # Setup sample tracks and preview
    sample_bg = str(Path("tests/fixtures/images/sample_bg.png").resolve())
    sample_tone = str(Path("tests/fixtures/audio/sample_tone.wav").resolve())
    if Path(sample_bg).exists():
        win.background_path = sample_bg
    if Path(sample_tone).exists():
        win.tracks = [
            {"path": sample_tone, "title": f"0{i}. Sample Nasheed Track {i}", "duration": 45.0}
            for i in range(1, 5)
        ]
        win.collection_title.setText("Nasheed Collection")
        win._committed_title = "Nasheed Collection"
        win._refresh_tracks()
    win._refresh_preview()
    app.processEvents()

    out_base = Path("tests/artifacts")

    # 1. Capture main window at normal size
    win.grab().save(str(out_base / "baseline/before_main_window_normal.png"))

    # 2. Capture main window narrow and wide (Item 4 problem area)
    win.resize(1024, 700)
    app.processEvents()
    win.grab().save(str(out_base / "item4/before_main_window_narrow.png"))

    win.resize(1600, 900)
    app.processEvents()
    win.grab().save(str(out_base / "item4/before_main_window_wide.png"))

    # Reset size
    win.resize(1366, 768)
    app.processEvents()

    # 3. Capture Inspector tabs (Item 3 problem area)
    for i in range(win.inspector_tabs.count()):
        win.inspector_tabs.setCurrentIndex(i)
        app.processEvents()
        tab_name = win.inspector_tabs.tabText(i).lower()
        win.inspector_panel.grab().save(str(out_base / f"item3/before_inspector_tab_{i}_{tab_name}.png"))
        win.inspector_panel.grab().save(str(out_base / f"baseline/before_inspector_tab_{i}_{tab_name}.png"))

    # 4. Capture Export bar (Item 3 problem area)
    from PySide6.QtWidgets import QFrame
    export_bar = win.findChild(QFrame, "export_bar")
    if export_bar:
        export_bar.grab().save(str(out_base / "item3/before_export_bar.png"))
        export_bar.grab().save(str(out_base / "baseline/before_export_bar.png"))

    # 5. Capture Font field clear button (Item 6 problem area)
    win.inspector_tabs.setCurrentIndex(1) # Text tab
    app.processEvents()
    if hasattr(win, "title_font_combo"):
        # Put text in line edit so clear button might appear
        le = win.title_font_combo.lineEdit()
        if le:
            le.setText("Segoe UI")
            app.processEvents()
            win.title_font_combo.grab().save(str(out_base / "item6/before_font_field.png"))
            win.title_font_combo.grab().save(str(out_base / "baseline/before_font_field.png"))

    # 6. Capture canvas with particles OFF and ON (Item 5 problem area)
    win.particles_check.setChecked(False)
    win._refresh_preview()
    app.processEvents()
    win.preview_frame.grab().save(str(out_base / "item5/before_canvas_particles_off.png"))
    win.preview_frame.grab().save(str(out_base / "baseline/before_canvas_particles_off.png"))

    win.particles_check.setChecked(True)
    win.particles_style_combo.setCurrentText("Drifting Flecks")
    win.particles_layer_combo.setCurrentText("Below Text")
    win._refresh_preview()
    # Advance particle timer / tick a few times
    if hasattr(win, "particle_overlay"):
        for _ in range(10):
            win.particle_overlay._update_particles()
    app.processEvents()
    win.preview_frame.grab().save(str(out_base / "item5/before_canvas_particles_on.png"))
    win.preview_frame.grab().save(str(out_base / "baseline/before_canvas_particles_on.png"))

    print("Baseline screenshots captured successfully.")

if __name__ == "__main__":
    capture_baseline()
