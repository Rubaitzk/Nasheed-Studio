"""
Tests for UI offset adjusters (cursor & highlight y-offsets), text color pickers,
outline cache invalidation, and preview-to-render parity.
"""

import io
import os
import json
import tempfile
from pathlib import Path
import pytest
from PIL import Image

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.ui.main_window import MainWindow
from src.services.render_service import build_render_command
from src.services.compositor import create_composition


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_ui_has_offset_adjusters(qapp):
    win = MainWindow()
    assert hasattr(win, "cursor_y_offset_spin")
    assert hasattr(win, "highlight_y_offset_spin")

    assert win.cursor_y_offset_spin.minimum() == -50
    assert win.cursor_y_offset_spin.maximum() == 50
    assert win.cursor_y_offset_spin.value() == 0

    assert win.highlight_y_offset_spin.minimum() == -50
    assert win.highlight_y_offset_spin.maximum() == 50
    assert win.highlight_y_offset_spin.value() == 0


def test_ui_has_text_color_selectors(qapp):
    win = MainWindow()
    assert hasattr(win, "title_color_btn")
    assert hasattr(win, "title_color_reset_btn")
    assert hasattr(win, "track_color_btn")
    assert hasattr(win, "track_color_reset_btn")

    # Defaults must be pure white (#FFFFFF)
    assert win.title_color == (255, 255, 255)
    assert win.track_color == (255, 255, 255)

    # Test setting track color and reset
    win.set_track_color((200, 100, 50))
    assert win.track_color == (200, 100, 50)
    assert "#C86432" in win.track_color_btn.text()

    win.reset_track_color()
    assert win.track_color == (255, 255, 255)
    assert "#FFFFFF" in win.track_color_btn.text()


def test_preview_cache_invalidation_on_outline_and_offset_changes(qapp):
    """Verify that changing outline width, corner style, or offsets changes cache_key."""
    win = MainWindow()
    win.tracks = [{"title": "Track 1", "path": "dummy.mp3", "duration": 30.0}]

    win._refresh_preview()
    key1 = win._cached_preview_key

    # Change outline thickness
    win.highlight_outline_spin.setValue(8)
    win._refresh_preview()
    key2 = win._cached_preview_key
    assert key1 != key2, "Cache key did not change when outline thickness changed"

    # Change cursor vertical offset
    win.cursor_y_offset_spin.setValue(15)
    win._refresh_preview()
    key3 = win._cached_preview_key
    assert key2 != key3, "Cache key did not change when cursor y offset changed"

    # Change highlight vertical offset
    win.highlight_y_offset_spin.setValue(-10)
    win._refresh_preview()
    key4 = win._cached_preview_key
    assert key3 != key4, "Cache key did not change when highlight y offset changed"

    # Change track text color
    win.set_track_color((255, 200, 100))
    win._refresh_preview()
    key5 = win._cached_preview_key
    assert key4 != key5, "Cache key did not change when track color changed"


def test_project_serialization_includes_all_new_properties(qapp):
    win = MainWindow()
    win.cursor_y_offset_spin.setValue(12)
    win.highlight_y_offset_spin.setValue(-7)
    win.set_track_color((255, 255, 255))
    win.set_title_color((240, 240, 250))
    win.highlight_outline_spin.setValue(5)
    win.highlight_corner_combo.setCurrentText("Square (Sharp)")
    win.highlight_target_combo.setCurrentText("Surround Text")

    proj = win._project()
    assert proj["cursor_y_offset"] == 12
    assert proj["highlight_y_offset"] == -7
    assert proj["track_color"] == (255, 255, 255)
    assert proj["title_color"] == (240, 240, 250)
    assert proj["highlight_outline_width"] == 5
    assert proj["highlight_corner_radius"] == 0
    assert proj["highlight_target"] == "text"


def test_render_and_preview_parity_with_offsets(qapp):
    """Ensure project settings with adjusters and colors are forwarded accurately to render pipeline."""
    project = {
        "collection_title": "GYM Nasheeds",
        "background": "assets/lion_clean_bg.png",
        "logo": "assets/ncn_logo.png",
        "cursor_path": "assets/paw_cursor.png",
        "cursor_size": 50,
        "cursor_y_offset": 8,
        "highlight_y_offset": -5,
        "track_color": [255, 255, 255],
        "title_color": [255, 255, 255],
        "highlight_style": "Outline",
        "highlight_color": [255, 255, 127],
        "highlight_outline_width": 4,
        "highlight_corner_radius": 0,
        "highlight_target": "text",
        "tracks": [
            {"title": "Track 1", "duration": 10.0, "path": "assets/dragon-studio-cartoon-cat-meow-487661.mp3"},
        ],
        "output_path": "test_output.mp4",
    }

    with tempfile.TemporaryDirectory() as tmp_render, tempfile.TemporaryDirectory() as tmp_prev:
        work_path = Path(tmp_render)
        cmd, effective_out = build_render_command(project, work_dir=work_path)
        render_overlay = work_path / "cursor_000.png"
        assert render_overlay.is_file()

        # Preview invocation with exact same parameters
        base_prev, ov_prev = create_composition(
            width=1920,
            height=1080,
            background_path="assets/lion_clean_bg.png",
            logo_path="assets/ncn_logo.png",
            collection_title="GYM Nasheeds",
            track_titles=["Track 1"],
            template="Cinematic",
            out_dir=tmp_prev,
            indicator_mode="both",
            cursor_path="assets/paw_cursor.png",
            cursor_size=50,
            cursor_y_offset=8,
            highlight_y_offset=-5,
            track_color=[255, 255, 255],
            title_color=[255, 255, 255],
            highlight_style="Outline",
            highlight_color=[255, 255, 127],
            highlight_outline_width=4,
            highlight_corner_radius=0,
            highlight_target="text",
            preview_only_first_overlay=True,
            active_track_index=0,
        )

        with open(render_overlay, "rb") as f_r, open(ov_prev[0], "rb") as f_p:
            data_r = f_r.read()
            data_p = f_p.read()

        with Image.open(io.BytesIO(data_r)) as im_r, Image.open(io.BytesIO(data_p)) as im_p:
            assert im_r.size == im_p.size == (1920, 1080)
            bbox_r = im_r.getbbox()
            bbox_p = im_p.getbbox()
            # Render and Preview overlay bounding boxes must be pixel-identical!
            assert bbox_r == bbox_p, f"Displacement detected! Render bbox {bbox_r} != Preview bbox {bbox_p}"
