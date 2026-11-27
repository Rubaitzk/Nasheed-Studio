"""
Automated tests verifying Inspector tab reordering, Playlist Layout & Grid
relocation to the Text tab, project compatibility, and live UI behaviors.
"""

import json
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow, CollapsibleSection
from tests.conftest import dispose_window


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def window(qapp):
    win = MainWindow()
    win.resize(1366, 768)
    win.show()
    qapp.processEvents()
    yield win
    dispose_window(win)


def _section_titles_in_tab(win: MainWindow, tab_index: int) -> list[str]:
    scroll = win.inspector_tabs.widget(tab_index)
    content = scroll.widget()
    layout = content.layout()
    titles = []
    for idx in range(layout.count()):
        item = layout.itemAt(idx)
        w = item.widget() if item else None
        if isinstance(w, CollapsibleSection):
            titles.append(w.toggle_btn.text().replace("▼", "").replace("▶", "").strip())
    return titles


def test_inspector_tab_order_is_exact(window):
    """The tab order must be exactly Canvas, Text, Indicator, Audio, Intro."""
    tabs = [window.inspector_tabs.tabText(i) for i in range(window.inspector_tabs.count())]
    assert tabs == ["Canvas", "Text", "Indicator", "Audio", "Intro"]
    assert window.inspector_tabs.usesScrollButtons() is True


def test_audio_and_intro_controls_reside_in_matching_tabs(window):
    """Audio tab (index 3) and Intro tab (index 4) contain their respective widgets."""
    audio_tab = window.inspector_tabs.widget(3)
    intro_tab = window.inspector_tabs.widget(4)

    assert audio_tab.isAncestorOf(window.audio_normalize_check)
    assert audio_tab.isAncestorOf(window.sfx_check)
    assert intro_tab.isAncestorOf(window.intro_check)
    assert intro_tab.isAncestorOf(window.intro_dur_spin)
    assert intro_tab.isAncestorOf(window.intro_title_edit)


def test_playlist_layout_grid_is_child_of_text_tab_not_canvas(window):
    """Playlist Layout & Grid and all its controls belong to Text tab (index 1) directly after Playlist Track Typography."""
    canvas_tab = window.inspector_tabs.widget(0)
    text_tab = window.inspector_tabs.widget(1)

    grid_controls = [
        window.playlist_pos_combo,
        window.playlist_cols_spin,
        window.col_spacing_spin,
        window.playlist_col_mode_combo,
        window.playlist_col_dist_edit,
        window.playlist_x_offset_spin,
        window.playlist_y_offset_spin,
        window.playlist_bg_slider,
    ]
    for ctrl in grid_controls:
        assert text_tab.isAncestorOf(ctrl), f"{ctrl} should be inside Text tab"
        assert not canvas_tab.isAncestorOf(ctrl), f"{ctrl} should NOT be inside Canvas tab"

    canvas_sections = _section_titles_in_tab(window, 0)
    text_sections = _section_titles_in_tab(window, 1)

    assert canvas_sections == [
        "Canvas & Preset",
        "Background Canvas",
        "Logo Overlay",
        "Ambient Particles Effect",
    ]
    assert text_sections == [
        "Collection Title",
        "Playlist Track Typography",
        "Playlist Layout & Grid",
        "Watermark & Website Text",
    ]


def test_legacy_project_loads_and_saves_with_identical_values(window, qapp, tmp_path):
    """A project JSON saved before the UI reordering loads and re-saves identical values."""
    legacy_project = {
        "project_version": 2,
        "collection_title": "Legacy Intro & Grid Test",
        "tracks": [],
        "playlist_position": "Right",
        "playlist_columns": 3,
        "playlist_col_spacing": 85,
        "playlist_column_distribution_mode": "manual",
        "playlist_column_distribution": "4, 4, 2",
        "playlist_x_offset": 42,
        "playlist_y_offset": -18,
        "playlist_bg_opacity": 0.55,
        "intro_enabled": True,
        "intro_duration": 4.5,
        "intro_animation": "Zoom in",
        "intro_title_text": "Welcome Intro",
        "intro_blur_radius": 32,
        "intro_card_opacity": 0.65,
        "intro_title_y_offset": -15,
        "intro_logo_y_offset": 12,
        "intro_website_y_offset": 20,
    }
    proj_path = tmp_path / "legacy_project.json"
    proj_path.write_text(json.dumps(legacy_project, indent=2), encoding="utf-8")

    window._load_project_file(str(proj_path))
    qapp.processEvents()

    assert window.playlist_pos_combo.currentText() == "Right"
    assert window.playlist_cols_spin.value() == 3
    assert window.col_spacing_spin.value() == 85
    assert window.playlist_col_mode_combo.currentText() == "Manual"
    assert window.playlist_col_dist_edit.text() == "4, 4, 2"
    assert window.playlist_x_offset_spin.value() == 42
    assert window.playlist_y_offset_spin.value() == -18
    assert window.playlist_bg_slider.value() == 55

    assert window.intro_check.isChecked() is True
    assert window.intro_dur_spin.value() == pytest.approx(4.5)
    assert window.intro_anim_combo.currentText() == "Zoom in"
    assert window.intro_title_edit.text() == "Welcome Intro"
    assert window.intro_blur_spin.value() == 32
    assert window.intro_card_opacity_slider.value() == 65

    resaved_path = tmp_path / "resaved_project.json"
    window._write_project(str(resaved_path))
    resaved = json.loads(resaved_path.read_text(encoding="utf-8"))
    for key in [
        "playlist_position",
        "playlist_columns",
        "playlist_col_spacing",
        "playlist_column_distribution_mode",
        "playlist_column_distribution",
        "playlist_x_offset",
        "playlist_y_offset",
        "playlist_bg_opacity",
        "intro_enabled",
        "intro_duration",
        "intro_animation",
        "intro_title_text",
        "intro_blur_radius",
        "intro_card_opacity",
    ]:
        assert resaved[key] == legacy_project[key]


def test_text_tab_grid_controls_update_live_preview_and_intro_preview(window, qapp):
    """Editing Columns/Column Gap/Panel Opacity updates preview; Preview Intro Card works cleanly."""
    window.inspector_tabs.setCurrentIndex(1)
    qapp.processEvents()

    window._refresh_preview()
    qapp.processEvents()
    before_img = window.preview_image.pixmap().toImage()

    window.playlist_cols_spin.setValue(2)
    window.col_spacing_spin.setValue(110)
    window.playlist_bg_slider.setValue(75)
    window._refresh_preview()
    qapp.processEvents()
    after_img = window.preview_image.pixmap().toImage()
    assert before_img != after_img

    # Switch to Intro tab (index 4), enable intro & toggle Preview Intro Card
    window.inspector_tabs.setCurrentIndex(4)
    window.intro_check.setChecked(True)
    window.intro_title_edit.setText("Live Intro Preview Verification")
    qapp.processEvents()

    window.preview_intro_btn.click()
    qapp.processEvents()
    assert getattr(window, "_previewing_intro", False) is True
    intro_img = window.preview_image.pixmap().toImage()
    assert intro_img != after_img

    # Toggle back off
    window.preview_intro_btn.click()
    qapp.processEvents()
    assert getattr(window, "_previewing_intro", False) is False
