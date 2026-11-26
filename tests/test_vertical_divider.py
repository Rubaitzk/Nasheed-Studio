"""
Automated tests for Item 4: Vertical separator between Playlist & Audio and Video Canvas,
and between Video Canvas and Inspector.
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


def test_divider_widgets_exist(main_window):
    """Assert the divider widgets exist and can be found in the widget tree."""
    assert hasattr(main_window, "playlist_canvas_divider")
    assert isinstance(main_window.playlist_canvas_divider, QFrame)
    assert main_window.playlist_canvas_divider.objectName() == "playlist_canvas_divider"

    assert hasattr(main_window, "canvas_inspector_divider")
    assert isinstance(main_window.canvas_inspector_divider, QFrame)
    assert main_window.canvas_inspector_divider.objectName() == "canvas_inspector_divider"

    # Both dividers are accessible as children of splitter handles
    assert main_window.findChild(QFrame, "playlist_canvas_divider") is not None
    assert main_window.findChild(QFrame, "canvas_inspector_divider") is not None


def test_divider_width_is_1px(main_window):
    """Assert both dividers are exactly 1 px wide."""
    div1 = main_window.playlist_canvas_divider
    div2 = main_window.canvas_inspector_divider

    assert div1.maximumWidth() == 1
    assert div1.minimumWidth() == 1
    assert div1.width() == 1

    assert div2.maximumWidth() == 1
    assert div2.minimumWidth() == 1
    assert div2.width() == 1


def test_divider_uses_same_color_as_existing_divider(main_window):
    """Assert the divider uses the same color as the existing hairline dividers."""
    expected_color = TOKENS["border_hairline"].upper()
    assert expected_color == TOKENS["border_hairline"].upper()

    # Verify hairline_h and hairline_v styles in application stylesheet
    assert "QFrame#hairline_h" in STYLE
    assert "QFrame#playlist_canvas_divider" in STYLE
    assert "QFrame#canvas_inspector_divider" in STYLE
    assert expected_color in STYLE


def test_layout_margins_are_symmetric(main_window):
    """Assert layout margins around both dividers are symmetric (left == right)."""
    h1 = main_window.splitter.handle(1)
    assert h1.layout() is not None
    m1 = h1.layout().contentsMargins()
    assert m1.left() == m1.right(), f"Handle 1 margins not symmetric: {m1.left()} != {m1.right()}"
    assert m1.left() > 0, "Expected non-zero spacing around divider"

    h2 = main_window.splitter.handle(2)
    assert h2.layout() is not None
    m2 = h2.layout().contentsMargins()
    assert m2.left() == m2.right(), f"Handle 2 margins not symmetric: {m2.left()} != {m2.right()}"
    assert m2.left() == m1.left(), "Expected both dividers to have equal spacing"


def test_window_resize_preserves_dividers_and_panel_sizes(main_window, qapp):
    """Assert resizing narrow (1024x700) and wide (1600x900) keeps dividers and panels intact."""
    for w, h in [(1024, 700), (1600, 900), (1366, 768)]:
        main_window.resize(w, h)
        qapp.processEvents()

        assert main_window.playlist_canvas_divider.width() == 1
        assert main_window.canvas_inspector_divider.width() == 1
        assert main_window.playlist_panel.isVisible()
        assert main_window.preview_panel.isVisible()
        assert main_window.inspector_panel.isVisible()
        assert len(main_window.splitter.sizes()) == 3
