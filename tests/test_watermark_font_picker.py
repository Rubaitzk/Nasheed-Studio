"""
Automated tests for the independent Watermark & Website Text Font Family picker,
backwards compatibility with pre-change projects, preview cache invalidation,
and Intro Card independent watermark font rendering & export.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QLabel

from src.services.compositor import create_composition, create_intro_card
from src.services.media_probe import extract_video_frame
from src.services.render_service import render_project
from src.ui.main_window import MainWindow, CollapsibleSection
from src.ui.widgets.searchable_combo import SearchableFontComboBox
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


def test_watermark_font_picker_placement_and_labels(window, qapp):
    """Font Family uses shared SearchableFontComboBox right below Position and above Font Size."""
    window.inspector_tabs.setCurrentIndex(1)
    qapp.processEvents()
    text_tab = window.inspector_tabs.widget(1)
    assert isinstance(window.website_font_combo, SearchableFontComboBox)
    assert text_tab.isAncestorOf(window.website_font_combo)
    assert window.website_font_combo.lineEdit().isClearButtonEnabled()

    # Locate the Watermark & Website Text collapsible section
    sec_web = None
    for sec in text_tab.findChildren(CollapsibleSection):
        if "Watermark & Website Text" in sec.toggle_btn.text():
            sec_web = sec
            break
    assert sec_web is not None

    # Verify ordering inside sec_web: website_pos_combo -> website_font_combo -> website_size_spin
    pos_y = window.website_pos_combo.mapTo(sec_web, window.website_pos_combo.rect().topLeft()).y()
    font_y = window.website_font_combo.mapTo(sec_web, window.website_font_combo.rect().topLeft()).y()
    size_y = window.website_size_spin.mapTo(sec_web, window.website_size_spin.rect().topLeft()).y()
    assert pos_y < font_y < size_y

    # Verify shortened offset labels are present without "Watermark X-Offs" truncation
    label_texts = [lbl.text() for lbl in sec_web.findChildren(QLabel)]
    assert "X-Offset:" in label_texts
    assert "Y-Offset:" in label_texts
    assert "Watermark X-Offset:" not in label_texts
    assert "Watermark Y-Offset:" not in label_texts


def test_new_project_default_is_segoe_ui(window, qapp):
    """Brand-new projects default watermark font to Segoe UI and serialize it."""
    assert window.website_font_family == "Segoe UI"
    assert window.website_font_combo.currentText() == "Segoe UI"
    proj = window._project()
    assert proj["website_font_family"] == "Segoe UI"

    # Also verify after switching and calling new_project()
    window.website_font_combo.setCurrentText("Georgia")
    qapp.processEvents()
    assert window.website_font_family == "Georgia"

    window._is_dirty = False
    window.new_project()
    qapp.processEvents()
    assert window.website_font_family == "Segoe UI"
    assert window.website_font_combo.currentText() == "Segoe UI"


def test_custom_font_save_load_roundtrip(window, qapp, tmp_path):
    """Save/load round trip preserves custom watermark font with spaces in name."""
    window.website_edit.setText("www.customroundtrip.com")
    window.website_font_combo.setCurrentText("Times New Roman")
    qapp.processEvents()
    assert window.website_font_family == "Times New Roman"

    proj_path = tmp_path / "custom_wm_font.json"
    window._write_project(str(proj_path))
    saved = json.loads(proj_path.read_text(encoding="utf-8"))
    assert saved["website_font_family"] == "Times New Roman"

    win2 = MainWindow()
    try:
        win2.resize(1366, 768)
        win2.show()
        win2._load_project_file(str(proj_path))
        qapp.processEvents()
        assert win2.website_font_family == "Times New Roman"
        assert win2.website_font_combo.currentText() == "Times New Roman"
    finally:
        dispose_window(win2)


@pytest.mark.parametrize("omitted_mode", ["missing", "none", "empty"])
def test_old_project_without_watermark_font_falls_back_to_track_font(window, qapp, tmp_path, omitted_mode):
    """Loading a pre-change project without website_font_family restores track_font_family so rendering matches."""
    sample_bg = Path("tests/fixtures/images/sample_bg.png").resolve()
    old_proj = {
        "project_version": 2,
        "collection_title": "Legacy Watermark Fallback",
        "background": str(sample_bg),
        "tracks": [],
        "track_font_family": "Georgia",
        "title_font_family": "Arial",
        "website_text": "www.legacymatch.org",
        "website_show": True,
        "website_position": "Top-Right",
        "website_font_size": 22,
    }
    if omitted_mode == "none":
        old_proj["website_font_family"] = None
    elif omitted_mode == "empty":
        old_proj["website_font_family"] = ""

    proj_path = tmp_path / f"legacy_{omitted_mode}.json"
    proj_path.write_text(json.dumps(old_proj, indent=2), encoding="utf-8")

    window._load_project_file(str(proj_path))
    qapp.processEvents()

    assert window.website_font_family == "Georgia"
    assert window.website_font_combo.currentText() == "Georgia"

    # Confirm rendered output matches what pre-change create_composition produced (website_font_family=None -> track_font_family)
    legacy_dir = tmp_path / "legacy_ref"
    new_dir = tmp_path / "loaded_ref"
    base_legacy, _ = create_composition(
        width=1280,
        height=720,
        background_path=str(sample_bg),
        logo_path=None,
        collection_title="Legacy Watermark Fallback",
        track_titles=["01. Example Nasheed One"],
        template="Cinematic",
        out_dir=str(legacy_dir),
        track_font_family="Georgia",
        website_text="www.legacymatch.org",
        website_show=True,
        website_font_size=22,
        website_font_family=None,
    )
    base_loaded, _ = create_composition(
        width=1280,
        height=720,
        background_path=str(sample_bg),
        logo_path=None,
        collection_title="Legacy Watermark Fallback",
        track_titles=["01. Example Nasheed One"],
        template="Cinematic",
        out_dir=str(new_dir),
        track_font_family="Georgia",
        website_text="www.legacymatch.org",
        website_show=True,
        website_font_size=22,
        website_font_family=window.website_font_family,
    )
    assert Path(base_legacy).read_bytes() == Path(base_loaded).read_bytes()


def test_watermark_font_independent_from_title_and_track_fonts(window, qapp):
    """Changing track or title fonts does not alter watermark font, and vice versa."""
    window.website_font_combo.setCurrentText("Courier New")
    qapp.processEvents()
    assert window.website_font_family == "Courier New"

    window.track_font_combo.setCurrentText("Georgia")
    window.title_font_combo.setCurrentText("Arial")
    window.intro_title_font_combo.setCurrentText("Times New Roman")
    qapp.processEvents()

    assert window.website_font_family == "Courier New"
    assert window.website_font_combo.currentText() == "Courier New"

    # Changing watermark font leaves track, title, and intro title fonts intact
    window.website_font_combo.setCurrentText("Segoe Script")
    qapp.processEvents()
    assert window.track_font_combo.currentText() == "Georgia"
    assert window.title_font_combo.currentText() == "Arial"
    assert window.intro_title_font_combo.currentText() == "Times New Roman"


def test_preview_cache_key_and_intro_card_update_on_watermark_font_change(window, qapp, tmp_path):
    """Changing watermark font invalidates main preview cache_key, intro preview, and intro export."""
    sample_audio = Path("tests/fixtures/audio/sample_tone.wav").resolve()
    sample_bg = Path("tests/fixtures/images/sample_bg.png").resolve()

    window.website_edit.setText("www.independentintro.org")
    window.website_show_check.setChecked(True)
    window.intro_check.setChecked(True)
    window.intro_title_font_combo.setCurrentText("Arial")
    window.track_font_combo.setCurrentText("Arial")
    window.website_font_combo.setCurrentText("Georgia")
    window._refresh_preview()
    qapp.processEvents()

    key_georgia = window._cached_preview_key
    img_main_georgia = window.preview_image.pixmap().toImage()

    # Capture intro preview with Georgia watermark (different from Arial intro title!)
    window._toggle_intro_preview()
    qapp.processEvents()
    img_intro_georgia = window.preview_image.pixmap().toImage()
    window._toggle_intro_preview()
    qapp.processEvents()

    # Switch watermark font to Courier New -> cache_key and both previews must change
    window.website_font_combo.setCurrentText("Courier New")
    window._refresh_preview()
    qapp.processEvents()
    key_courier = window._cached_preview_key
    img_main_courier = window.preview_image.pixmap().toImage()

    assert key_georgia != key_courier
    assert img_main_georgia != img_main_courier

    window._toggle_intro_preview()
    qapp.processEvents()
    img_intro_courier = window.preview_image.pixmap().toImage()
    assert img_intro_georgia != img_intro_courier
    window._toggle_intro_preview()
    qapp.processEvents()

    # Export short video with intro enabled -> verify exported intro frame matches Courier New (not Arial)
    out_mp4 = tmp_path / "intro_wm_test.mp4"
    proj = window._project()
    proj["background"] = str(sample_bg)
    proj["tracks"] = [{"title": "Track 1", "path": str(sample_audio), "duration": 1.0}]
    proj["intro_enabled"] = True
    proj["intro_duration"] = 1.5
    proj["output_path"] = str(out_mp4)
    assert proj["website_font_family"] == "Courier New"
    assert proj["intro_title_font_family"] == "Arial"
    render_project(proj)

    # Compare exported frame at midpoint of intro (0.75s, fully faded in) against direct Courier New vs Arial intro card
    card_courier = create_intro_card(
        width=1920,
        height=1080,
        background_path=str(sample_bg),
        logo_path=None,
        collection_title=proj["collection_title"],
        template=proj.get("template", "Cinematic"),
        out_dir=str(tmp_path / "card_courier"),
        title_font_family="Arial",
        website_text="www.independentintro.org",
        website_show=True,
        website_font_size=proj["intro_website_font_size"],
        website_font_family="Courier New",
        website_font_style="Regular",
    )
    card_arial = create_intro_card(
        width=1920,
        height=1080,
        background_path=str(sample_bg),
        logo_path=None,
        collection_title=proj["collection_title"],
        template=proj.get("template", "Cinematic"),
        out_dir=str(tmp_path / "card_arial"),
        title_font_family="Arial",
        website_text="www.independentintro.org",
        website_show=True,
        website_font_size=proj["intro_website_font_size"],
        website_font_family="Arial",
        website_font_style="Regular",
    )
    exported_intro_frame = extract_video_frame(str(out_mp4), 0.75).convert("RGB")
    arr_exp = np.array(exported_intro_frame, dtype=np.int16)
    arr_courier = np.array(Image.open(card_courier).convert("RGB"), dtype=np.int16)
    arr_arial = np.array(Image.open(card_arial).convert("RGB"), dtype=np.int16)

    diff_courier = float(np.abs(arr_exp - arr_courier).mean())
    diff_arial = float(np.abs(arr_exp - arr_arial).mean())
    assert diff_courier < diff_arial
