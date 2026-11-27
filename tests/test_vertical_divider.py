"""
Automated tests confirming the two green vertical divider lines around the Video Canvas
were removed while preserving exact spacing, draggability, and panel outlines.
"""

import sys
import pytest
from PySide6.QtWidgets import QApplication, QFrame
from PySide6.QtCore import Qt

from src.ui.main_window import MainWindow
from src.ui.style import TOKENS, STYLE
from tests.conftest import dispose_window


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def main_window(qapp):
    win = MainWindow()
    win.resize(1366, 768)
    win.show()
    qapp.processEvents()
    yield win
    dispose_window(win)


def test_divider_lines_removed(main_window):
    """Assert the visible divider line widgets and stylesheet rules are removed."""
    assert not hasattr(main_window, "playlist_canvas_divider")
    assert not hasattr(main_window, "canvas_inspector_divider")
    assert main_window.findChild(QFrame, "playlist_canvas_divider") is None
    assert main_window.findChild(QFrame, "canvas_inspector_divider") is None
    assert "QFrame#playlist_canvas_divider" not in STYLE
    assert "QFrame#canvas_inspector_divider" not in STYLE


def test_splitter_spacing_and_draggability_preserved(main_window, qapp):
    """Assert the 7px gap between panels is preserved, non-touching, and splitter remains draggable."""
    assert main_window.splitter.handleWidth() == 7
    h1 = main_window.splitter.handle(1)
    h2 = main_window.splitter.handle(2)
    assert h1.width() == 7
    assert h2.width() == 7

    # Panels must not touch each other (7px gap between edges)
    pl_right = main_window.playlist_panel.geometry().right()
    pv_left = main_window.preview_panel.geometry().left()
    pv_right = main_window.preview_panel.geometry().right()
    in_left = main_window.inspector_panel.geometry().left()
    assert pv_left - pl_right - 1 == 7
    assert in_left - pv_right - 1 == 7

    # Splitter handles remain enabled and resizable
    assert h1.isEnabled()
    assert h2.isEnabled()
    old_sizes = main_window.splitter.sizes()
    main_window.splitter.setSizes([old_sizes[0] + 20, old_sizes[1] - 20, old_sizes[2]])
    qapp.processEvents()
    new_sizes = main_window.splitter.sizes()
    assert new_sizes[0] != old_sizes[0]


def test_panel_outlines_and_section_borders_untouched(main_window):
    """Assert panel outlines and Inspector section header borders remain intact."""
    assert "QFrame#playlist_pane, QFrame#preview_pane, QFrame#inspector_pane" in STYLE
    assert "QPushButton#twirl_header" in STYLE
    assert "QFrame#hairline_h" in STYLE
    assert "QFrame#hairline_v" in STYLE
    assert TOKENS["border_hairline"].upper() in STYLE.upper()


def test_splitter_gaps_have_no_green_line_pixels(main_window, qapp):
    """Sample pixels inside both splitter handle gaps and verify only bg_window (#161C18) is painted."""
    qapp.processEvents()
    qapp.processEvents()
    bg_hex = TOKENS["bg_window"].lstrip("#")
    exp_r, exp_g, exp_b = int(bg_hex[0:2], 16), int(bg_hex[2:4], 16), int(bg_hex[4:6], 16)

    for handle in (main_window.splitter.handle(1), main_window.splitter.handle(2)):
        h_img = handle.grab().toImage()
        y_mid = h_img.height() // 2
        for dx in range(h_img.width()):
            c = h_img.pixelColor(dx, y_mid)
            assert abs(c.red() - exp_r) <= 3 and abs(c.green() - exp_g) <= 3 and abs(c.blue() - exp_b) <= 3, (
                f"Expected pure window bg ({exp_r},{exp_g},{exp_b}) inside handle gap, got ({c.red()},{c.green()},{c.blue()})"
            )


def test_window_resize_preserves_spacing_and_panels(main_window, qapp):
    """Assert resizing narrow (1024x700) and wide (1600x900) keeps gaps and panels intact."""
    for w, h in [(1024, 700), (1600, 900), (1366, 768)]:
        main_window.resize(w, h)
        qapp.processEvents()

        assert main_window.splitter.handleWidth() == 7
        assert main_window.playlist_panel.isVisible()
        assert main_window.preview_panel.isVisible()
        assert main_window.inspector_panel.isVisible()
        assert len(main_window.splitter.sizes()) == 3
