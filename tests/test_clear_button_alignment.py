"""
Automated tests for Item 6: Font family "X" clear button vertical center alignment.
"""

import sys
import pytest
from PySide6.QtWidgets import QApplication, QLineEdit, QToolButton

from src.ui.main_window import MainWindow
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


def test_font_family_clear_button_vertical_center_alignment(main_window, qapp):
    """
    Assert the clear button's geometry center equals the line edit's vertical center (±1 px)
    for every line edit with a clear button in the Inspector when visible.
    """
    win = main_window

    tested_fields = []
    # Switch across Inspector tabs to test each field when its tab is active
    for tab_idx in range(win.inspector_tabs.count()):
        win.inspector_tabs.setCurrentIndex(tab_idx)
        qapp.processEvents()

        current_tab_widget = win.inspector_tabs.widget(tab_idx)
        for le in current_tab_widget.findChildren(QLineEdit):
            if le.isClearButtonEnabled() and le.isVisible():
                le.setText("Segoe UI")
                qapp.processEvents()

                tb = le.findChild(QToolButton)
                assert tb is not None, f"Expected QToolButton inside QLineEdit for {le.placeholderText()!r}"
                assert tb.isVisible(), f"Expected clear button to be visible when text is set for {le.placeholderText()!r}"

                le_center_y = le.height() / 2.0
                tb_center_y = tb.y() + tb.height() / 2.0
                diff = abs(le_center_y - tb_center_y)

                top_padding = tb.y()
                bottom_padding = le.height() - (tb.y() + tb.height())

                # Assert vertical center alignment within ±1 px tolerance
                assert diff <= 1.0, (
                    f"Clear button vertical center misaligned for {le.placeholderText()!r}: "
                    f"diff={diff:.2f}px (le_center={le_center_y}, tb_center={tb_center_y})"
                )

                # Assert equal top and bottom padding within ±1 px tolerance
                pad_diff = abs(top_padding - bottom_padding)
                assert pad_diff <= 1.0, (
                    f"Clear button padding asymmetric for {le.placeholderText()!r}: "
                    f"top={top_padding}, bottom={bottom_padding}"
                )

                tested_fields.append(le.placeholderText())

    print(f"\nTested clear button alignment for fields: {tested_fields}")
    assert len(tested_fields) >= 3, f"Expected at least 3 font search clear buttons in Inspector, tested {tested_fields}"
