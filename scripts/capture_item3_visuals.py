import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QFrame, QComboBox, QSpinBox
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase, QFont

from src.ui.main_window import MainWindow


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    for font_file in ["segoeui.ttf", "segoeuib.ttf", "segoeuisb.ttf", "arial.ttf", "calibri.ttf"]:
        p = Path(f"C:/Windows/Fonts/{font_file}")
        if p.exists():
            QFontDatabase.addApplicationFont(str(p))
    app.setFont(QFont("Segoe UI", 9))

    out_dir = ROOT_DIR / "tests" / "artifacts" / "item3"
    out_dir.mkdir(parents=True, exist_ok=True)

    win = MainWindow()
    win.resize(1366, 768)
    win.show()
    app.processEvents()

    # 1. Capture every inspector tab
    for i in range(win.inspector_tabs.count()):
        win.inspector_tabs.setCurrentIndex(i)
        app.processEvents()
        tab_name = win.inspector_tabs.tabText(i).lower()
        win.inspector_panel.grab().save(str(out_dir / f"after_inspector_tab_{i}_{tab_name}.png"))
        print(f"Captured after_inspector_tab_{i}_{tab_name}.png", flush=True)

    # 2. Capture export bar (Resolution, Profile, Quality)
    export_bar = win.findChild(QFrame, "export_bar")
    if export_bar:
        export_bar.grab().save(str(out_dir / "after_export_bar.png"))
        print("Captured after_export_bar.png", flush=True)

    # 3. Capture hover and pressed states of spin box
    spin = win.particles_speed_spin
    if spin:
        up_pos = QPoint(spin.width() - 8, 6)
        QTest.mouseMove(spin, up_pos)
        app.processEvents()
        spin.grab().save(str(out_dir / "after_spin_up_hover.png"))

        QTest.mousePress(spin, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, up_pos)
        app.processEvents()
        spin.grab().save(str(out_dir / "after_spin_up_pressed.png"))
        QTest.mouseRelease(spin, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, up_pos)
        app.processEvents()

    # 4. Capture hover and pressed states of combo box
    if hasattr(win, "res_combo"):
        combo = win.res_combo
        combo_pos = QPoint(combo.width() - 10, combo.height() // 2)
        QTest.mouseMove(combo, combo_pos)
        app.processEvents()
        combo.grab().save(str(out_dir / "after_combo_hover.png"))

    win.closeEvent = lambda event: event.accept()
    win.close()
    print("Item 3 visuals captured successfully.", flush=True)


if __name__ == "__main__":
    main()
