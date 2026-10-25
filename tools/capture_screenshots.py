"""
Automated script to capture real rendered UI screenshots of Nasheed Studio.
Captures windows at exact resolutions (1120x720, 1440x900), DPI scales (100%, 125%),
inspector states (expanded, collapsed), long filename elision, track selection contrast,
and active render states.
"""

import os
import sys
import time
from pathlib import Path

# Ensure repo root is on path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

mode = sys.argv[1] if len(sys.argv) > 1 else "100pct"

# Configure High DPI scaling before importing Qt
if mode == "100pct":
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
elif mode == "125pct":
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ.pop("QT_SCALE_FACTOR", None)

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow

SCREENSHOT_DIR = REPO_ROOT / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


def dispose(win):
    if win is None:
        return
    if hasattr(win, "_title_timer") and win._title_timer.isActive():
        win._title_timer.stop()
    if hasattr(win, "_preview_timer") and win._preview_timer.isActive():
        win._preview_timer.stop()
    win.closeEvent = lambda e: e.accept()
    win.close()
    win.deleteLater()
    app = QApplication.instance()
    if app:
        app.processEvents()


def setup_sample_data(win: MainWindow):
    """Set up realistic sample data and assets for high-fidelity screenshots."""
    sample_bg = REPO_ROOT / "assets" / "reference_images" / "1000032692.jpg"
    if sample_bg.exists():
        win.background_path = str(sample_bg)
        win._set_asset_label(win.background_label, str(sample_bg))

    win.tracks = [
        {"title": "01 Kunta Rahimun (You Were Merciful)", "path": "D:/Audio/Kunta_Rahimun.mp3", "duration": 214.0},
        {"title": "02 Mawlay Salli Wa Sallim (Peace Upon Him)", "path": "D:/Audio/Mawlay_Salli.mp3", "duration": 285.0},
        {"title": "03 Qad Kafani Ilmu Rabbi (Sufficient Is My Lord)", "path": "D:/Audio/Qad_Kafani.mp3", "duration": 192.0},
        {"title": "04 Tala'al Badru 'Alayna (The Full Moon Rose)", "path": "D:/Audio/Talaal_Badru.mp3", "duration": 248.0},
    ]
    win._committed_title = "Sacred Melodies: Abu Ali Nasheeds Collection"
    win.collection_title.setText(win._committed_title)
    win.website_edit.setText("www.nasheedstudio.org")
    win._refresh_tracks()
    win._mark_dirty()


def capture():
    app = QApplication.instance() or QApplication(sys.argv)
    print(f"Running mode={mode}, app.devicePixelRatio()={app.devicePixelRatio()}", flush=True)

    if mode == "100pct":
        # 1. 1120x720 Expanded
        win = MainWindow()
        setup_sample_data(win)
        win.resize(1120, 720)
        win.show()
        app.processEvents()
        time.sleep(0.3)
        app.processEvents()
        pix = win.grab()
        pix.save(str(SCREENSHOT_DIR / "screenshot_1120x720_100scale_expanded.png"))
        print(f"Captured screenshot_1120x720_100scale_expanded.png ({pix.width()}x{pix.height()})", flush=True)

        # 2. 1120x720 Collapsed
        win.toggle_inspector()
        app.processEvents()
        time.sleep(0.2)
        app.processEvents()
        pix = win.grab()
        pix.save(str(SCREENSHOT_DIR / "screenshot_1120x720_100scale_collapsed.png"))
        print(f"Captured screenshot_1120x720_100scale_collapsed.png ({pix.width()}x{pix.height()})", flush=True)
        dispose(win)

        # 3. 1440x900 Expanded
        win2 = MainWindow()
        setup_sample_data(win2)
        win2.resize(1440, 900)
        win2.show()
        app.processEvents()
        time.sleep(0.3)
        app.processEvents()
        pix = win2.grab()
        pix.save(str(SCREENSHOT_DIR / "screenshot_1440x900_100scale_expanded.png"))
        print(f"Captured screenshot_1440x900_100scale_expanded.png ({pix.width()}x{pix.height()})", flush=True)

        # 4. 1440x900 Collapsed
        win2.toggle_inspector()
        app.processEvents()
        time.sleep(0.2)
        app.processEvents()
        pix = win2.grab()
        pix.save(str(SCREENSHOT_DIR / "screenshot_1440x900_100scale_collapsed.png"))
        print(f"Captured screenshot_1440x900_100scale_collapsed.png ({pix.width()}x{pix.height()})", flush=True)
        dispose(win2)

        # 5. Long Filenames
        win_lf = MainWindow()
        win_lf.resize(1280, 800)
        long_bg = "D:/Production/Projects/Nasheeds_2026/Assets/Background_Ultra_Wide_Cinematic_Desert_Mountains_Sunset_4K_Final_Render_Master.png"
        long_logo = "D:/Production/Branding/Official_Logos/Nasheed_Studio_Arabic_Calligraphy_Emblem_Gold_Vector_Master_High_DPI.png"
        win_lf.background_path = long_bg
        win_lf._set_asset_label(win_lf.background_label, long_bg)
        win_lf.logo_path = long_logo
        win_lf._set_asset_label(win_lf.logo_label, long_logo)
        win_lf.show()
        app.processEvents()
        time.sleep(0.3)
        pix = win_lf.grab()
        pix.save(str(SCREENSHOT_DIR / "screenshot_long_filenames.png"))
        print(f"Captured screenshot_long_filenames.png ({pix.width()}x{pix.height()})", flush=True)
        dispose(win_lf)

        # 6. Selected Track Contrast
        win_sel = MainWindow()
        setup_sample_data(win_sel)
        win_sel.resize(1280, 800)
        win_sel.show()
        win_sel.track_list.setCurrentRow(1)
        win_sel.track_list.setFocus()
        app.processEvents()
        time.sleep(0.3)
        pix = win_sel.grab()
        pix.save(str(SCREENSHOT_DIR / "screenshot_selected_track.png"))
        print(f"Captured screenshot_selected_track.png ({pix.width()}x{pix.height()})", flush=True)
        dispose(win_sel)

        # 7. Running Render
        win_rnd = MainWindow()
        setup_sample_data(win_rnd)
        win_rnd.resize(1280, 800)
        win_rnd.show()
        win_rnd._set_ui_running(True)
        win_rnd.progress.setRange(0, 100)
        win_rnd.progress.setValue(58)
        win_rnd.status_label.setText("Encoding video: frame 1850 / 3200 (42 fps) · ETA 00:32")
        app.processEvents()
        time.sleep(0.3)
        pix = win_rnd.grab()
        pix.save(str(SCREENSHOT_DIR / "screenshot_running_render.png"))
        print(f"Captured screenshot_running_render.png ({pix.width()}x{pix.height()})", flush=True)
        dispose(win_rnd)

    elif mode == "125pct":
        # 1120x720 at 125% Expanded & Collapsed
        win_125_sm = MainWindow()
        setup_sample_data(win_125_sm)
        win_125_sm.resize(1120, 720)
        win_125_sm.show()
        app.processEvents()
        time.sleep(0.3)
        pix = win_125_sm.grab()
        pix.save(str(SCREENSHOT_DIR / "screenshot_1120x720_125scale_expanded.png"))
        print(f"Captured screenshot_1120x720_125scale_expanded.png ({pix.width()}x{pix.height()})", flush=True)

        win_125_sm.toggle_inspector()
        app.processEvents()
        time.sleep(0.2)
        pix = win_125_sm.grab()
        pix.save(str(SCREENSHOT_DIR / "screenshot_1120x720_125scale_collapsed.png"))
        print(f"Captured screenshot_1120x720_125scale_collapsed.png ({pix.width()}x{pix.height()})", flush=True)
        dispose(win_125_sm)

        # 1440x900 at 125% Expanded & Collapsed
        win_125_lg = MainWindow()
        setup_sample_data(win_125_lg)
        win_125_lg.resize(1440, 900)
        win_125_lg.show()
        app.processEvents()
        time.sleep(0.3)
        pix = win_125_lg.grab()
        pix.save(str(SCREENSHOT_DIR / "screenshot_1440x900_125scale_expanded.png"))
        print(f"Captured screenshot_1440x900_125scale_expanded.png ({pix.width()}x{pix.height()})", flush=True)

        win_125_lg.toggle_inspector()
        app.processEvents()
        time.sleep(0.2)
        pix = win_125_lg.grab()
        pix.save(str(SCREENSHOT_DIR / "screenshot_1440x900_125scale_collapsed.png"))
        print(f"Captured screenshot_1440x900_125scale_collapsed.png ({pix.width()}x{pix.height()})", flush=True)
        dispose(win_125_lg)


if __name__ == "__main__":
    capture()
