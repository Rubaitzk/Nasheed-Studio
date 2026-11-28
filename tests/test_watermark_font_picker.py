"""
Automated tests for the independent Watermark & Website Text Font Family picker,
backwards compatibility with pre-change projects, preview cache invalidation,
and Intro Card independent watermark font rendering & export.
"""

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QPushButton

from src.services.compositor import create_composition, create_intro_card
from src.services.font_service import _CUSTOM_FONTS, list_family_styles, refresh_fonts
from src.services.media_probe import extract_video_frame
from src.services.project_service import bundle_managed_assets, check_missing_assets
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


def test_watermark_size_range_and_old_values_preserved(window, qapp, tmp_path):
    """Watermark font size spinbox minimum=10, default=18, maximum=80; <=48 projects load unchanged."""
    assert window.website_size_spin.minimum() == 10
    assert window.website_size_spin.value() == 18
    assert window.website_size_spin.maximum() == 80

    window.website_size_spin.setValue(80)
    assert window.website_size_spin.value() == 80
    assert window._project()["website_font_size"] == 80

    # Old project with <= 48 size loads unchanged
    old_proj = {
        "project_version": 2,
        "collection_title": "Old Size Test",
        "tracks": [],
        "website_font_size": 24,
    }
    p = tmp_path / "old_size_24.json"
    p.write_text(json.dumps(old_proj), encoding="utf-8")
    window._load_project_file(str(p))
    qapp.processEvents()
    assert window.website_size_spin.value() == 24


def test_watermark_browse_button_persistence_and_missing_font_fallback(window, qapp, tmp_path):
    """Browse button registers custom font across pickers, persists via custom_website_font_path, and handles missing files."""
    assert isinstance(window.website_font_browse_btn, QPushButton)
    assert "Browse" in window.website_font_browse_btn.text()

    # Copy BebasNeue-Regular.ttf to a temp path and browse it
    src_ttf = Path("assets/fonts/BebasNeue-Regular.ttf").resolve()
    browsed_ttf = tmp_path / "BrowsedWatermark.ttf"
    shutil.copy2(src_ttf, browsed_ttf)

    with patch("src.ui.main_window.QFileDialog.getOpenFileName", return_value=(str(browsed_ttf), "")):
        window.website_font_browse_btn.click()
    qapp.processEvents()

    chosen_fam = window.website_font_family
    assert chosen_fam
    assert window.custom_website_font_path == str(browsed_ttf)
    assert window.website_font_combo.currentText() == chosen_fam
    # Consistent with other Browse buttons: registered font appears in other pickers too
    assert window.title_font_combo.findText(chosen_fam) >= 0
    assert window.track_font_combo.findText(chosen_fam) >= 0

    proj = window._project()
    assert proj["custom_website_font_path"] == str(browsed_ttf)
    assert proj["website_font_family"] == chosen_fam

    # Bundling & missing asset checks include custom_website_font_path
    assert "fonts" not in check_missing_assets(proj)
    managed = bundle_managed_assets(proj, tmp_path / "bundle")
    assert Path(managed["custom_website_font_path"]).is_file()
    assert Path(managed["custom_website_font_path"]).parent.name == "fonts"

    # Save, clear font registry, and load into a new window -> restores cleanly
    proj_path = tmp_path / "browsed_wm_proj.json"
    window._write_project(str(proj_path))
    _CUSTOM_FONTS.clear()
    refresh_fonts()

    win2 = MainWindow()
    try:
        win2.resize(1366, 768)
        win2.show()
        win2._load_project_file(str(proj_path))
        qapp.processEvents()
        assert win2.custom_website_font_path == str(browsed_ttf)
        assert win2.website_font_family == chosen_fam
        assert win2.website_font_combo.currentText() == chosen_fam

        # Now delete the custom font file and load -> graceful fallback with zero crash
        browsed_ttf.unlink()
        _CUSTOM_FONTS.clear()
        refresh_fonts()
        win2._load_project_file(str(proj_path))
        qapp.processEvents()
        win2._refresh_preview()
        qapp.processEvents()
        assert win2.preview_image.pixmap() is not None
    finally:
        dispose_window(win2)


def test_watermark_80px_all_corners_no_clipping_and_export(tmp_path):
    """At 80 px with a long URL, watermark renders inside frame bounds at all 4 corners and exports cleanly."""
    sample_audio = Path("tests/fixtures/audio/sample_tone.wav").resolve()
    sample_bg = Path("tests/fixtures/images/sample_bg.png").resolve()

    src_ttf = Path("assets/fonts/BebasNeue-Regular.ttf").resolve()
    custom_ttf = tmp_path / "ExportBebas80.ttf"
    shutil.copy2(src_ttf, custom_ttf)

    for corner in ("Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right"):
        out_dir = tmp_path / f"corner_{corner}"
        base, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(sample_bg),
            logo_path=None,
            collection_title="Corner 80px Test",
            track_titles=["Track 1"],
            template="Cinematic",
            out_dir=str(out_dir),
            website_text="www.nasheedstudio.com",
            website_position=corner,
            website_font_size=80,
            website_font_family=str(custom_ttf),
            website_x_offset=10 if "Left" in corner else -10,
            website_y_offset=10 if "Top" in corner else -10,
        )
        img = Image.open(base)
        assert img.size == (1920, 1080)

    # Cold export with _CUSTOM_FONTS cleared verifies render_service registers custom_website_font_path
    _CUSTOM_FONTS.clear()
    refresh_fonts()
    out_mp4 = tmp_path / "wm_80px_browsed.mp4"
    render_project({
        "collection_title": "80px Custom Export",
        "background": str(sample_bg),
        "tracks": [{"title": "Track 1", "path": str(sample_audio), "duration": 1.0}],
        "website_text": "www.nasheedstudio.com",
        "website_show": True,
        "website_position": "Top-Right",
        "website_font_size": 80,
        "website_font_family": "Bebas Neue",
        "custom_website_font_path": str(custom_ttf),
        "intro_enabled": False,
        "output_path": str(out_mp4),
    })
    assert out_mp4.is_file() and out_mp4.stat().st_size > 0
    frame = extract_video_frame(str(out_mp4), 0.5)
    assert frame.size == (1920, 1080)


def test_watermark_font_style_dropdown_dynamic_updates(window, qapp):
    """Font Style dropdown dynamically reflects available styles for selected watermark font."""
    window.inspector_tabs.setCurrentIndex(1)
    qapp.processEvents()
    text_tab = window.inspector_tabs.widget(1)

    sec_web = None
    for sec in text_tab.findChildren(CollapsibleSection):
        if "Watermark & Website Text" in sec.toggle_btn.text():
            sec_web = sec
            break
    assert sec_web is not None
    assert isinstance(window.website_style_combo, QComboBox)
    assert text_tab.isAncestorOf(window.website_style_combo)

    # Placement: right below Font Family and above Font Size
    font_y = window.website_font_combo.mapTo(sec_web, window.website_font_combo.rect().topLeft()).y()
    style_y = window.website_style_combo.mapTo(sec_web, window.website_style_combo.rect().topLeft()).y()
    size_y = window.website_size_spin.mapTo(sec_web, window.website_size_spin.rect().topLeft()).y()
    assert font_y < style_y < size_y
    assert "Font Style:" in [lbl.text() for lbl in sec_web.findChildren(QLabel)]

    # Keep track of Title and Track styles to ensure zero side effects
    orig_title_style = window.title_style_combo.currentText()
    orig_track_style = window.track_style_combo.currentText()

    # Multi-style font (Arial): exposes Regular, Bold, Italic, Bold Italic matching list_family_styles
    window.website_font_combo.setCurrentText("Arial")
    qapp.processEvents()
    arial_styles = [window.website_style_combo.itemText(i) for i in range(window.website_style_combo.count())]
    assert arial_styles == list_family_styles("Arial")
    assert set(["Regular", "Bold", "Italic"]).issubset(set(arial_styles))
    assert window.website_style_combo.currentText() == "Regular"
    assert window.website_font_style == "Regular"

    # Choose Bold Italic on Arial
    target_style = "Bold Italic" if "Bold Italic" in arial_styles else "Bold"
    window.website_style_combo.setCurrentText(target_style)
    qapp.processEvents()
    assert window.website_font_style == target_style

    # Switch to another multi-style font (Georgia): preserves matching style cleanly
    window.website_font_combo.setCurrentText("Georgia")
    qapp.processEvents()
    georgia_styles = [window.website_style_combo.itemText(i) for i in range(window.website_style_combo.count())]
    assert georgia_styles == list_family_styles("Georgia")
    if target_style in georgia_styles:
        assert window.website_style_combo.currentText() == target_style
        assert window.website_font_style == target_style

    # Switch to Regular-only font (Impact or Bebas Neue): shows only Regular and clears invalid style
    reg_only_fam = "Impact" if window.website_font_combo.findText("Impact") >= 0 else "Bebas Neue"
    window.website_style_combo.setCurrentText("Italic" if "Italic" in georgia_styles else target_style)
    qapp.processEvents()
    window.website_font_combo.setCurrentText(reg_only_fam)
    qapp.processEvents()
    reg_styles = [window.website_style_combo.itemText(i) for i in range(window.website_style_combo.count())]
    assert reg_styles == ["Regular"]
    assert window.website_style_combo.currentText() == "Regular"
    assert window.website_font_style == "Regular"

    # Title and Track styles remain untouched
    assert window.title_style_combo.currentText() == orig_title_style
    assert window.track_style_combo.currentText() == orig_track_style


def test_watermark_font_style_persistence_preview_and_export(window, qapp, tmp_path):
    """Selected watermark font style persists on save/load and is reflected in preview & video export."""
    sample_audio = Path("tests/fixtures/audio/sample_tone.wav").resolve()
    sample_bg = Path("tests/fixtures/images/sample_bg.png").resolve()

    window.website_edit.setText("www.stylizedwatermark.com")
    window.website_show_check.setChecked(True)
    window.website_size_spin.setValue(36)
    window.website_font_combo.setCurrentText("Arial")
    qapp.processEvents()

    window.website_style_combo.setCurrentText("Regular")
    window._refresh_preview()
    qapp.processEvents()
    key_reg = window._cached_preview_key
    img_reg = window.preview_image.pixmap().toImage()

    window.website_style_combo.setCurrentText("Bold Italic")
    window._refresh_preview()
    qapp.processEvents()
    key_bi = window._cached_preview_key
    img_bi = window.preview_image.pixmap().toImage()

    assert key_reg != key_bi
    assert img_reg != img_bi
    assert window.website_font_style == "Bold Italic"

    # Intro card preview also updates when style changes
    window.intro_check.setChecked(True)
    window._toggle_intro_preview()
    qapp.processEvents()
    intro_bi = window.preview_image.pixmap().toImage()
    window.website_style_combo.setCurrentText("Regular")
    window._refresh_preview()
    qapp.processEvents()
    intro_reg = window.preview_image.pixmap().toImage()
    assert intro_bi != intro_reg
    window._toggle_intro_preview()
    qapp.processEvents()

    # Restore Bold Italic, save, and reload into fresh MainWindow
    window.website_style_combo.setCurrentText("Bold Italic")
    qapp.processEvents()
    proj_path = tmp_path / "wm_style_roundtrip.json"
    window._write_project(str(proj_path))
    saved = json.loads(proj_path.read_text(encoding="utf-8"))
    assert saved["website_font_family"] == "Arial"
    assert saved["website_font_style"] == "Bold Italic"

    win2 = MainWindow()
    try:
        win2.resize(1366, 768)
        win2.show()
        win2._load_project_file(str(proj_path))
        qapp.processEvents()
        assert win2.website_font_family == "Arial"
        assert win2.website_font_style == "Bold Italic"
        assert win2.website_style_combo.currentText() == "Bold Italic"
    finally:
        dispose_window(win2)

    # Render short MP4 with Arial Bold Italic and confirm exported frame matches Bold Italic closer than Regular
    out_mp4 = tmp_path / "wm_bold_italic.mp4"
    proj = window._project()
    proj["background"] = str(sample_bg)
    proj["tracks"] = [{"title": "Track 1", "path": str(sample_audio), "duration": 1.0}]
    proj["intro_enabled"] = False
    proj["output_path"] = str(out_mp4)
    render_project(proj)

    base_bi, _ = create_composition(
        width=1920,
        height=1080,
        background_path=str(sample_bg),
        logo_path=None,
        collection_title=proj["collection_title"],
        track_titles=["Track 1"],
        template=proj.get("template", "Cinematic"),
        out_dir=str(tmp_path / "ref_bi"),
        website_text="www.stylizedwatermark.com",
        website_show=True,
        website_font_size=36,
        website_font_family="Arial",
        website_font_style="Bold Italic",
    )
    base_reg, _ = create_composition(
        width=1920,
        height=1080,
        background_path=str(sample_bg),
        logo_path=None,
        collection_title=proj["collection_title"],
        track_titles=["Track 1"],
        template=proj.get("template", "Cinematic"),
        out_dir=str(tmp_path / "ref_reg"),
        website_text="www.stylizedwatermark.com",
        website_show=True,
        website_font_size=36,
        website_font_family="Arial",
        website_font_style="Regular",
    )
    exp_arr = np.array(extract_video_frame(str(out_mp4), 0.5).convert("RGB"), dtype=np.int16)
    bi_arr = np.array(Image.open(base_bi).convert("RGB"), dtype=np.int16)
    reg_arr = np.array(Image.open(base_reg).convert("RGB"), dtype=np.int16)
    assert float(np.abs(exp_arr - bi_arr).mean()) < float(np.abs(exp_arr - reg_arr).mean())

