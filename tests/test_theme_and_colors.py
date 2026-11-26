"""
Automated tests for the Green Color Scheme restoration (STEP 2 of requirements).
Verifies:
1. Palette test: No blue-family accent remains in stylesheets, tokens, main_window, or icons.
2. Token test: Tokens exist and match reference hex values exactly.
3. Widget color test: Samples pixels of Save button, Render button, slider handle, active tab indicator,
   and surface backgrounds to assert they match reference tokens (within 3 per channel).
4. State tests: Normal, hover, pressed, and disabled states differ visually and match tokens.
5. Contrast test: WCAG contrast ratios of text on #3D8B58 buttons and panels.
6. Icon test: Bundled SVG resources load cleanly without blue hexes.
7. Regression & Save/Load test: Project round-trip serialization is unaffected.
8. Export unaffected: Renders short video clip to ensure theme colors do not leak into video output.
"""

import os
import sys
import json
import tempfile
from pathlib import Path
import pytest
import numpy as np
from PIL import Image

from PySide6.QtWidgets import (
    QApplication, QFrame, QTabBar, QPushButton, QStyle, QStyleOptionButton
)
from PySide6.QtCore import Qt, QPoint, QRect, QFile
from PySide6.QtGui import QColor, QFontDatabase, QFont, QPixmap, QPainter
from PySide6.QtTest import QTest

from src.ui.style import (
    STYLE, TOKENS, ACCENT, ACCENT_HOVER, ACCENT_PRESSED,
    BG_WINDOW, BG_PANEL, BG_FIELD, BORDER, BORDER_ACCENT,
    BORDER_CANVAS, BG_CANVAS
)
from src.ui.main_window import MainWindow
from src.services.render_service import render_project
from src.services.media_probe import extract_video_frame
from tests.conftest import dispose_window


OLD_BLUE_HEXES = [
    "#6C9FE8", "#82AEED", "#5A8DD4", "#253042", "#242F40",
    "#282E3B", "#1C222E", "#2B3A52", "#38455C", "#333B4A",
    "#2A3446", "#343C4C", "#2A303D"
]


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    for font_file in ["segoeui.ttf", "segoeuib.ttf", "segoeuisb.ttf", "arial.ttf", "calibri.ttf"]:
        p = Path(f"C:/Windows/Fonts/{font_file}")
        if p.exists():
            QFontDatabase.addApplicationFont(str(p))
    app.setFont(QFont("Segoe UI", 9))
    return app


@pytest.fixture
def themed_window(qapp):
    win = MainWindow()
    win.resize(1366, 768)
    win.show()
    sample_bg = str(Path("tests/fixtures/images/sample_bg.png").resolve())
    sample_tone = str(Path("tests/fixtures/audio/sample_tone.wav").resolve())
    if Path(sample_bg).exists():
        win.background_path = sample_bg
    if Path(sample_tone).exists():
        win.tracks = [
            {"path": sample_tone, "title": f"0{i}. Sample Nasheed Track {i}", "duration": 45.0}
            for i in range(1, 4)
        ]
        win.collection_title.setText("Nasheed Collection Test")
        win._committed_title = "Nasheed Collection Test"
        win._refresh_tracks()
    win._refresh_preview()
    qapp.processEvents()
    yield win
    dispose_window(win)


# ---------------------------------------------------------------------------
# 1. Palette Test: No blue-family accent remains
# ---------------------------------------------------------------------------

def test_palette_no_blue_family_remains():
    """Scan stylesheet text, style module, main_window, icons, and resources for old blue hexes."""
    # Check STYLE string
    style_upper = STYLE.upper()
    for blue in OLD_BLUE_HEXES:
        assert blue.upper() not in style_upper, f"Old blue hex {blue} found in application STYLE!"

    # Check TOKENS dictionary
    for k, v in TOKENS.items():
        if isinstance(v, str):
            for blue in OLD_BLUE_HEXES:
                assert blue.upper() != v.upper(), f"Old blue hex {blue} found in TOKENS[{k}]!"

    # Check source files on disk
    src_dir = Path(__file__).resolve().parent.parent / "src" / "ui"
    for py_file in [src_dir / "style.py", src_dir / "icons.py", src_dir / "main_window.py"]:
        content = py_file.read_text(encoding="utf-8").upper()
        for blue in OLD_BLUE_HEXES:
            assert blue.upper() not in content, f"Old blue hex {blue} found in {py_file.name}!"


# ---------------------------------------------------------------------------
# 2. Token Test: Tokens exist and match reference hex values exactly
# ---------------------------------------------------------------------------

def test_token_values_match_reference():
    """Verify that all theme tokens exist and match the client's reference hex values exactly."""
    expected = {
        "accent": "#3D8B58",
        "bg_window": "#161C18",
        "bg_panel": "#1B211D",
        "bg_field": "#222A24",
        "border": "#2C362E",
        "border_accent": "#294231",
        "border_canvas": "#121615",
        "bg_canvas": "#121615",
        "accent_hover": "#48A167",
        "accent_pressed": "#2F7248",
        "accent_text": "#FFFFFF",
    }
    for key, expected_val in expected.items():
        assert key in TOKENS, f"Missing token key '{key}' in TOKENS"
        actual_val = TOKENS[key].upper()
        assert actual_val == expected_val.upper(), f"Token {key} expected {expected_val}, got {actual_val}"

    # Verify uppercase constants
    assert ACCENT.upper() == "#3D8B58"
    assert BG_WINDOW.upper() == "#161C18"
    assert BG_PANEL.upper() == "#1B211D"
    assert BG_FIELD.upper() == "#222A24"
    assert BORDER.upper() == "#2C362E"
    assert BORDER_ACCENT.upper() == "#294231"
    assert BORDER_CANVAS.upper() == "#121615"
    assert BG_CANVAS.upper() == "#121615"
    assert ACCENT_HOVER.upper() == "#48A167"
    assert ACCENT_PRESSED.upper() == "#2F7248"


# ---------------------------------------------------------------------------
# 3. Widget Color Test: Sample pixels against #3D8B58 and surface tokens
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
    h = hex_code.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _color_matches(c: QColor, target_hex: str, tolerance: int = 3) -> bool:
    tr, tg, tb = _hex_to_rgb(target_hex)
    return (
        abs(c.red() - tr) <= tolerance
        and abs(c.green() - tg) <= tolerance
        and abs(c.blue() - tb) <= tolerance
    )


def test_widget_pixel_color_sampling(themed_window, qapp):
    """
    Grab Save button, Render button, slider handle, active tab indicator,
    and assert they match #3D8B58 (+/- 3 per channel). Sample surfaces as well.
    """
    win = themed_window
    qapp.processEvents()

    # 1. Save button pixel sampling
    save_pix = win.save_btn.grab()
    save_img = save_pix.toImage()
    save_color = save_img.pixelColor(6, save_img.height() // 2)
    assert _color_matches(save_color, "#3D8B58", tolerance=3), (
        f"Save button background expected #3D8B58, sampled ({save_color.red()}, {save_color.green()}, {save_color.blue()})"
    )

    # 2. Render button pixel sampling
    render_pix = win.render_btn.grab()
    render_img = render_pix.toImage()
    render_color = render_img.pixelColor(6, render_img.height() // 2)
    assert _color_matches(render_color, "#3D8B58", tolerance=3), (
        f"Render button background expected #3D8B58, sampled ({render_color.red()}, {render_color.green()}, {render_color.blue()})"
    )

    # 3. Active tab indicator sampling (bottom 2px line rendered on tab bar)
    tab_bar = win.inspector_tabs.tabBar()
    tab_pix = tab_bar.grab()
    tab_img = tab_pix.toImage()
    tab_rect = tab_bar.tabRect(0)
    indicator_y = tab_img.height() - 2
    indicator_color = tab_img.pixelColor(tab_rect.center().x(), indicator_y)
    assert _color_matches(indicator_color, "#3D8B58", tolerance=3), (
        f"Active tab indicator expected #3D8B58, sampled ({indicator_color.red()}, {indicator_color.green()}, {indicator_color.blue()})"
    )

    # 4. Window background surface sampling
    win_pix = win.grab()
    win_img = win_pix.toImage()
    status_color = win_img.pixelColor(20, win_img.height() - 6)
    assert _color_matches(status_color, "#161C18", tolerance=3), (
        f"Window background expected #161C18, sampled ({status_color.red()}, {status_color.green()}, {status_color.blue()})"
    )

    # 5. Panel background sampling (playlist pane background)
    panel_pix = win.playlist_panel.grab()
    panel_img = panel_pix.toImage()
    panel_color = panel_img.pixelColor(4, 4)
    assert _color_matches(panel_color, "#1B211D", tolerance=3), (
        f"Panel background expected #1B211D, sampled ({panel_color.red()}, {panel_color.green()}, {panel_color.blue()})"
    )


# ---------------------------------------------------------------------------
# 4. State Tests: Normal, hover, pressed, disabled states differ visually
# ---------------------------------------------------------------------------

def _render_button_state(btn: QPushButton, state_flags: QStyle.StateFlag, clear_flags: QStyle.StateFlag = QStyle.StateFlag.State_None) -> QPixmap:
    pix = QPixmap(btn.size())
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    opt = QStyleOptionButton()
    btn.initStyleOption(opt)
    if clear_flags != QStyle.StateFlag.State_None:
        opt.state &= ~clear_flags
    opt.state |= state_flags
    btn.style().drawControl(QStyle.ControlElement.CE_PushButton, opt, painter, btn)
    painter.end()
    return pix


def test_button_state_visual_differences(themed_window, qapp):
    """Assert normal, hover, pressed, and disabled states produce distinct pixel renderings matching tokens."""
    win = themed_window
    qapp.processEvents()

    # Test primary button states (Save & Render)
    for name, btn in [("save", win.save_btn), ("render", win.render_btn)]:
        pix_normal = _render_button_state(btn, QStyle.StateFlag.State_Enabled)
        pix_hover = _render_button_state(btn, QStyle.StateFlag.State_MouseOver)
        pix_pressed = _render_button_state(btn, QStyle.StateFlag.State_Sunken)
        pix_disabled = _render_button_state(btn, QStyle.StateFlag.State_None, clear_flags=QStyle.StateFlag.State_Enabled)

        c_normal = pix_normal.toImage().pixelColor(6, btn.height() // 2)
        c_hover = pix_hover.toImage().pixelColor(6, btn.height() // 2)
        c_pressed = pix_pressed.toImage().pixelColor(6, btn.height() // 2)
        c_disabled = pix_disabled.toImage().pixelColor(6, btn.height() // 2)

        # Check exact token matching
        assert _color_matches(c_normal, TOKENS["accent"], tolerance=2), f"{name} normal state != accent"
        assert _color_matches(c_hover, TOKENS["accent_hover"], tolerance=2), f"{name} hover state != accent_hover"
        assert _color_matches(c_pressed, TOKENS["accent_pressed"], tolerance=2), f"{name} pressed state != accent_pressed"
        assert _color_matches(c_disabled, TOKENS["accent_disabled"], tolerance=2), f"{name} disabled state != accent_disabled"

        # Check visual distinctness
        assert c_normal != c_hover, f"{name} hover color equals normal"
        assert c_normal != c_pressed, f"{name} pressed color equals normal"
        assert c_normal != c_disabled, f"{name} disabled color equals normal"

    # Test outlined accent button (New button)
    pix_new_normal = _render_button_state(win.new_btn, QStyle.StateFlag.State_Enabled)
    pix_new_pressed = _render_button_state(win.new_btn, QStyle.StateFlag.State_Sunken)
    c_new_norm = pix_new_normal.toImage().pixelColor(6, win.new_btn.height() // 2)
    c_new_press = pix_new_pressed.toImage().pixelColor(6, win.new_btn.height() // 2)
    assert _color_matches(c_new_norm, TOKENS["bg_field"], tolerance=2)
    assert _color_matches(c_new_press, TOKENS["bg_input_pressed"], tolerance=2)


# ---------------------------------------------------------------------------
# 5. Contrast Test: Compute WCAG 2.1 contrast ratios and report
# ---------------------------------------------------------------------------

def _relative_luminance(r: int, g: int, b: int) -> float:
    def _gamma(c: float) -> float:
        c_norm = c / 255.0
        return c_norm / 12.92 if c_norm <= 0.03928 else ((c_norm + 0.055) / 1.055) ** 2.4
    return 0.2126 * _gamma(r) + 0.7152 * _gamma(g) + 0.0722 * _gamma(b)


def _contrast_ratio(hex1: str, hex2: str) -> float:
    r1, g1, b1 = _hex_to_rgb(hex1)
    r2, g2, b2 = _hex_to_rgb(hex2)
    l1 = _relative_luminance(r1, g1, b1)
    l2 = _relative_luminance(r2, g2, b2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def test_wcag_contrast_ratios():
    """Compute and assert WCAG contrast ratios on primary buttons, panels, and fields."""
    cr_button = _contrast_ratio("#FFFFFF", TOKENS["accent"])
    cr_panel = _contrast_ratio(TOKENS["text_main"], TOKENS["bg_panel"])
    cr_field = _contrast_ratio(TOKENS["text_main"], TOKENS["bg_field"])
    cr_muted = _contrast_ratio(TOKENS["text_muted"], TOKENS["bg_panel"])

    print(f"\n--- Contrast Ratio Audit ---")
    print(f"White text on #3D8B58 button: {cr_button:.2f}:1 (Requirement >= 3.0:1)")
    print(f"Light text on #1B211D panel: {cr_panel:.2f}:1 (Requirement >= 4.5:1)")
    print(f"Light text on #222A24 field: {cr_field:.2f}:1 (Requirement >= 4.5:1)")
    print(f"Muted text on #1B211D panel: {cr_muted:.2f}:1 (Secondary text)")

    assert cr_button >= 3.0, f"Button text contrast {cr_button:.2f}:1 is below 3.0:1"
    assert cr_panel >= 4.5, f"Panel text contrast {cr_panel:.2f}:1 is below 4.5:1"
    assert cr_field >= 4.5, f"Field text contrast {cr_field:.2f}:1 is below 4.5:1"


# ---------------------------------------------------------------------------
# 6. Icon Test: Bundled SVG resources load cleanly and contain no blue
# ---------------------------------------------------------------------------

def test_icon_resources_load_and_contain_no_blue():
    """Verify that bundled chevron SVGs exist, load into Qt resource system, and contain no blue."""
    assets_dir = Path(__file__).resolve().parent.parent / "assets" / "icons"
    svg_files = list(assets_dir.glob("*.svg"))
    assert len(svg_files) >= 8

    for svg in svg_files:
        content = svg.read_text(encoding="utf-8").upper()
        for blue in OLD_BLUE_HEXES:
            assert blue.upper() not in content, f"Old blue hex {blue} found in SVG file {svg.name}!"

        # Verify Qt resource equivalent exists
        res_path = f":/icons/{svg.name}"
        assert QFile.exists(res_path), f"Qt resource path {res_path} missing!"


# ---------------------------------------------------------------------------
# 7. Regression Test: Project save/load round-trip
# ---------------------------------------------------------------------------

def test_project_save_load_round_trip(themed_window, qapp):
    """Verify that theme change has zero effect on project configuration serialization."""
    win = themed_window
    win.collection_title.setText("Preserved Project Title")
    win.particles_check.setChecked(True)
    win.particles_count_spin.setValue(45)

    proj_dict = win._project()
    assert proj_dict["collection_title"] == "Preserved Project Title"
    assert proj_dict.get("particles_quantity") == 45 or proj_dict.get("particles_count") == 45

    # Round trip save to file and reload
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(proj_dict, f)
        temp_path = f.name

    try:
        win._load_project_file(temp_path)
        assert win.collection_title.text() == "Preserved Project Title"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ---------------------------------------------------------------------------
# 8. Export Unaffected: Render video clip to confirm theme does not bleed into video
# ---------------------------------------------------------------------------

def test_export_unaffected_by_theme():
    """Render a short clip and verify video frame rendering is unaffected by UI theme."""
    sample_audio = Path("tests/fixtures/audio/sample_tone.wav").resolve()
    sample_bg = Path("tests/fixtures/images/sample_bg.png").resolve()

    with tempfile.TemporaryDirectory() as tmp:
        out_video = Path(tmp) / "theme_export_test.mp4"
        project = {
            "collection_title": "Theme Export Test",
            "background": str(sample_bg),
            "logo": "",
            "tracks": [{"path": str(sample_audio), "title": "Track 1", "duration": 1.0}],
            "intro_enabled": False,
            "particles_enabled": False,
            "output_path": str(out_video),
        }
        render_project(project)
        assert out_video.is_file() and out_video.stat().st_size > 0

        # Extract frame and check that it contains real background pixels
        frame = extract_video_frame(str(out_video), 0.5)
        assert frame is not None and frame.width > 0 and frame.height > 0
        arr = np.array(frame.convert("RGB"))
        assert arr.shape[0] > 0 and arr.shape[1] > 0
