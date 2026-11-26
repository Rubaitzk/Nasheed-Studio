"""
Script to capture all required screenshots for theme before/after comparison.
Usage:
    python scripts/capture_theme_screenshots.py before
    python scripts/capture_theme_screenshots.py after
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set offscreen platform
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import (
    QApplication, QFrame, QMessageBox, QMenu, QComboBox, QSpinBox, QLineEdit, QPushButton, QDialog, QVBoxLayout, QLabel, QDialogButtonBox
)
from PySide6.QtCore import QSize, Qt, QPoint, QEvent
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtTest import QTest

from src.ui.main_window import MainWindow
from tests.conftest import dispose_window


def capture_theme(prefix: str = "before"):
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Register common fonts if on windows
    for font_file in ["segoeui.ttf", "segoeuib.ttf", "segoeuisb.ttf", "arial.ttf", "calibri.ttf"]:
        p = Path(f"C:/Windows/Fonts/{font_file}")
        if p.exists():
            QFontDatabase.addApplicationFont(str(p))
    app.setFont(QFont("Segoe UI", 9))

    out_dir = Path("tests/artifacts/theme")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Main window empty
    win = MainWindow()
    win.resize(1366, 768)
    win.show()
    app.processEvents()
    win.grab().save(str(out_dir / f"{prefix}_main_window_empty.png"))

    # 2. Main window with example tracks loaded
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

    win.grab().save(str(out_dir / f"{prefix}_main_window_loaded.png"))

    # 3. Each Inspector tab
    tab_names = ["canvas", "text", "indicator", "intro", "audio"]
    for i in range(win.inspector_tabs.count()):
        win.inspector_tabs.setCurrentIndex(i)
        app.processEvents()
        t_name = tab_names[i] if i < len(tab_names) else f"tab_{i}"
        win.inspector_panel.grab().save(str(out_dir / f"{prefix}_inspector_tab_{i}_{t_name}.png"))

    # Return to tab 0
    win.inspector_tabs.setCurrentIndex(0)
    app.processEvents()

    # 4. Export bar (idle and mid-export)
    export_bar = win.findChild(QFrame, "export_bar")
    if export_bar:
        export_bar.grab().save(str(out_dir / f"{prefix}_export_bar_idle.png"))

        # Mid-export state
        win._set_ui_running(True)
        win.progress.setValue(55)
        win.status_label.setText("Rendering frame 120/400 (55%)...")
        app.processEvents()
        export_bar.grab().save(str(out_dir / f"{prefix}_export_bar_running.png"))
        
        # Reset back to idle
        win._set_ui_running(False)
        win.progress.setValue(0)
        win.status_label.setText("Ready")
        app.processEvents()

    # 5. Buttons: Save, Render MP4, New, Open (normal, hover, pressed)
    buttons = [
        ("save", win.save_btn),
        ("render", win.render_btn),
        ("new", win.new_btn),
        ("open", win.open_btn),
    ]

    for name, btn in buttons:
        # Block signals so clicking does not trigger modal dialogs or start renders
        btn.blockSignals(True)
        
        # Normal
        app.processEvents()
        btn.grab().save(str(out_dir / f"{prefix}_button_{name}_normal.png"))

        # Hover
        center = btn.rect().center()
        QTest.mouseMove(btn, center)
        app.processEvents()
        btn.grab().save(str(out_dir / f"{prefix}_button_{name}_hover.png"))

        # Pressed state: use setDown to render pressed state without releasing click
        btn.setDown(True)
        app.processEvents()
        btn.grab().save(str(out_dir / f"{prefix}_button_{name}_pressed.png"))
        btn.setDown(False)
        app.processEvents()
        
        btn.blockSignals(False)

    # 6. Focused line edit, focused spin box, combo box
    win.collection_title.setFocus()
    app.processEvents()
    win.collection_title.grab().save(str(out_dir / f"{prefix}_input_lineedit_focused.png"))

    win.inspector_tabs.setCurrentIndex(0) # Canvas tab
    app.processEvents()
    if hasattr(win, "particles_speed_spin"):
        win.particles_speed_spin.setFocus()
        app.processEvents()
        win.particles_speed_spin.grab().save(str(out_dir / f"{prefix}_input_spinbox_focused.png"))

    # Combo box dropdown
    res_combo = win.resolution_combo
    res_combo.grab().save(str(out_dir / f"{prefix}_input_combobox.png"))
    # Also grab popup view if available
    popup = res_combo.view()
    if popup:
        popup.grab().save(str(out_dir / f"{prefix}_input_combobox_dropdown.png"))

    # 7. Selected row in playlist, and canvas preview with particles on
    if win.track_list.count() > 0:
        win.track_list.setCurrentRow(0)
        app.processEvents()
        win.playlist_panel.grab().save(str(out_dir / f"{prefix}_playlist_selected_row.png"))

    # Canvas preview with particles on
    win.particles_check.setChecked(True)
    win.particles_style_combo.setCurrentText("Drifting Flecks")
    win.particles_layer_combo.setCurrentText("Below Text")
    win._refresh_preview()
    if hasattr(win, "particle_overlay"):
        for _ in range(15):
            win.particle_overlay._update_particles()
    app.processEvents()
    win.preview_frame.grab().save(str(out_dir / f"{prefix}_canvas_particles_on.png"))

    # 8. Menu bar and context menus
    menu_bar = win.menuBar()
    menu_bar.grab().save(str(out_dir / f"{prefix}_menu_bar.png"))

    # Custom Dialog (testing theme colors on dialog, buttons, and text)
    dlg = QDialog(win)
    dlg.setWindowTitle("Dialog Theme Verification")
    dlg.resize(380, 160)
    dlg_layout = QVBoxLayout(dlg)
    dlg_label = QLabel("Confirmation Dialog sample with themed buttons.")
    dlg_layout.addWidget(dlg_label)
    btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    dlg_layout.addWidget(btn_box)
    dlg.show()
    app.processEvents()
    dlg.grab().save(str(out_dir / f"{prefix}_dialog.png"))
    dlg.close()
    app.processEvents()

    # Dispose window safely without triggering closeEvent dialog
    dispose_window(win)
    print(f"Captured all {prefix} screenshots into {out_dir}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "before"
    capture_theme(mode)
