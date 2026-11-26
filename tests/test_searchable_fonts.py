"""
Unit and integration tests for Feature B: Searchable Fonts.

Verifies:
1. SearchableFontComboBox instant filtering and autocomplete.
2. Selecting fonts via text typing and dropdown.
3. Empty search string safety (reverts to last valid).
4. Missing / unrecognized font name handling (reverts gracefully, never corrupts).
5. Integration with MainWindow and project persistence.
"""

import sys
import pytest
from PySide6.QtWidgets import QApplication

from src.ui.widgets import SearchableFontComboBox
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_searchable_font_combo_filtering(qapp):
    combo = SearchableFontComboBox()
    families = ["Segoe UI", "Arial", "Calibri", "Montserrat", "Cinzel Decorative", "Times New Roman"]
    combo.set_font_families(families, current="Segoe UI")

    assert combo.count() == len(families)
    assert combo.currentText() == "Segoe UI"

    # Test selecting valid font
    combo.setEditText("Montserrat")
    combo._on_editing_finished()
    assert combo.currentText() == "Montserrat"
    assert combo._last_valid_text == "Montserrat"


def test_searchable_font_combo_substring_match(qapp):
    combo = SearchableFontComboBox()
    families = ["Segoe UI", "Arial", "Montserrat Light", "Cinzel Decorative"]
    combo.set_font_families(families, current="Arial")

    # Partial typing "cinz" should match "Cinzel Decorative"
    combo.setEditText("cinz")
    combo._on_editing_finished()
    assert combo.currentText() == "Cinzel Decorative"


def test_searchable_font_combo_missing_font_reversion(qapp):
    combo = SearchableFontComboBox()
    families = ["Segoe UI", "Arial", "Calibri"]
    combo.set_font_families(families, current="Segoe UI")

    # Typing completely nonexistent font should revert to previous valid
    combo.setEditText("CompletelyNonExistentFont12345")
    combo._on_editing_finished()
    assert combo.currentText() == "Segoe UI"

    # Empty string should revert to previous valid
    combo.setEditText("")
    combo._on_editing_finished()
    assert combo.currentText() == "Segoe UI"


def test_main_window_searchable_font_combos(qapp):
    win = MainWindow()
    try:
        assert isinstance(win.title_font_combo, SearchableFontComboBox)
        assert isinstance(win.track_font_combo, SearchableFontComboBox)
        assert isinstance(win.intro_title_font_combo, SearchableFontComboBox)

        # Change font via searchable combo
        win.title_font_combo.setEditText("Arial")
        win.title_font_combo._on_editing_finished()
        proj = win._project()
        assert proj["title_font_family"] == "Arial"
    finally:
        dispose_window(win)
