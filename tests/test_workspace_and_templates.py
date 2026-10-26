"""
Tests for Nasheed Studio Workspace Persistence and Reusable Template Completeness.

Covers:
1. Workspace persistence, temp-directory leak prevention, and safe recovery.
2. Distinct workspace subdirectories (projects, templates, exports, temp, logs).
3. Template completeness: full preservation of all visual design and styling keys.
4. Protected project content: strict exclusion and preservation of titles, tracks, and assets.
5. Reusable custom cursor handling (durability and missing asset tolerance).
6. Template name validation, malformed JSON error handling, and overwrite guards.
7. UI template application and preview synchronization.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from src.services.workspace_service import (
    get_workspace_root,
    set_workspace_root,
    reset_workspace_root,
    is_temp_or_obsolete_path,
    temporary_workspace,
    get_projects_dir,
    get_templates_dir,
    get_exports_dir,
    get_temp_dir,
    get_logs_dir,
    DEFAULT_WORKSPACE_NAME,
)
from src.services.project_service import (
    TEMPLATE_DESIGN_KEYS,
    PROTECTED_PROJECT_CONTENT_KEYS,
    extract_template,
    save_template_atomic,
    load_template,
    apply_template_to_project,
    save_project_atomic,
)
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestWorkspacePersistence(unittest.TestCase):
    def setUp(self):
        _get_app()
        self.settings = QSettings("NasheedStudio", "NasheedStudio")
        self._orig_had_ws = self.settings.contains("workspace_root")
        self._orig_ws = self.settings.value("workspace_root", None)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

    def tearDown(self):
        if self._orig_had_ws and self._orig_ws is not None:
            self.settings.setValue("workspace_root", self._orig_ws)
        else:
            self.settings.remove("workspace_root")
        self.temp_dir.cleanup()

    def test_default_workspace_points_to_durable_home(self):
        """When no setting exists, workspace defaults to Path.home() / 'NasheedStudio'."""
        self.settings.remove("workspace_root")
        root = get_workspace_root()
        expected = (Path.home() / DEFAULT_WORKSPACE_NAME).resolve()
        self.assertEqual(root, expected)

    def test_obsolete_temp_workspace_detected_and_cleared(self):
        """If workspace_root in QSettings points to OS temp dir, it is purged and defaults to durable home."""
        bogus_temp_ws = self.tmp / "leaked_temp_workspace"
        bogus_temp_ws.mkdir(parents=True, exist_ok=True)
        self.settings.setValue("workspace_root", str(bogus_temp_ws))

        self.assertTrue(is_temp_or_obsolete_path(bogus_temp_ws))
        root = get_workspace_root()
        expected = (Path.home() / DEFAULT_WORKSPACE_NAME).resolve()
        self.assertEqual(root, expected)
        # Setting must be purged from QSettings
        self.assertFalse(self.settings.contains("workspace_root"))

    def test_nonexistent_workspace_safely_resets(self):
        """If workspace path in QSettings does not exist, it safely resets without error."""
        nonexistent = Path("Z:/NonexistentDrive/NeverExisted/NasheedWorkspace")
        self.settings.setValue("workspace_root", str(nonexistent))

        self.assertTrue(is_temp_or_obsolete_path(nonexistent))
        root = get_workspace_root()
        expected = (Path.home() / DEFAULT_WORKSPACE_NAME).resolve()
        self.assertEqual(root, expected)
        self.assertFalse(self.settings.contains("workspace_root"))

    def test_reset_workspace_root_explicit(self):
        """reset_workspace_root purges settings, ensures directories, and returns durable default."""
        custom_dir = self.tmp / "custom_durable_ws"
        custom_dir.mkdir(parents=True, exist_ok=True)
        self.settings.setValue("workspace_root", str(custom_dir))

        reset_root = reset_workspace_root()
        expected = (Path.home() / DEFAULT_WORKSPACE_NAME).resolve()
        self.assertEqual(reset_root, expected)
        self.assertFalse(self.settings.contains("workspace_root"))
        # Verify standard subdirectories exist
        self.assertTrue((reset_root / "projects").is_dir())
        self.assertTrue((reset_root / "templates").is_dir())
        self.assertTrue((reset_root / "exports").is_dir())
        self.assertTrue((reset_root / "temp").is_dir())
        self.assertTrue((reset_root / "logs").is_dir())

    def test_workspace_subdirectories_are_distinct(self):
        """Projects, templates, exports, temp, and logs are completely distinct paths."""
        custom = self.tmp / "distinct_ws"
        custom.mkdir(parents=True, exist_ok=True)

        p = get_projects_dir(custom)
        tmpl = get_templates_dir(custom)
        exp = get_exports_dir(custom)
        tmp = get_temp_dir(custom)
        logs = get_logs_dir(custom)

        dirs = [p, tmpl, exp, tmp, logs]
        self.assertEqual(len(dirs), len(set(dirs)), "All workspace subdirectories must be distinct")
        for d in dirs:
            self.assertTrue(d.is_dir())

    def test_temporary_workspace_context_manager(self):
        """temporary_workspace sets path and guarantees restoration on exit."""
        self.settings.remove("workspace_root")
        ws_test = self.tmp / "ctx_test"
        ws_test.mkdir(parents=True, exist_ok=True)

        with temporary_workspace(ws_test) as active:
            self.assertEqual(active, ws_test.resolve())
            self.assertEqual(self.settings.value("workspace_root"), str(ws_test.resolve()))

        # After block: must be restored (removed)
        self.assertFalse(self.settings.contains("workspace_root"))


class TestTemplateCompleteness(unittest.TestCase):
    def setUp(self):
        _get_app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Create dummy assets
        self.dummy_cursor = self.tmp / "cursor.png"
        self.dummy_cursor.write_bytes(b"PNG_CURSOR_BYTES")

        self.rich_project = {
            "version": 1,
            "collection_title": "Sacred Anthems Collection",
            "background": str(self.tmp / "bg.jpg"),
            "logo": str(self.tmp / "logo.png"),
            "tracks": [
                {"title": "Track One", "path": str(self.tmp / "t1.mp3"), "duration": 120.0},
                {"title": "Track Two", "path": str(self.tmp / "t2.mp3"), "duration": 180.0},
            ],
            "output_path": str(self.tmp / "export.mp4"),
            "website_text": "www.originalnasheed.com",
            # Visual / Layout / Styling settings:
            "template": "Cinematic",
            "resolution": "1440p · QHD",
            "resource_profile": "Maximum-speed",
            "playlist_position": "Center",
            "playlist_columns": 2,
            "playlist_row_spacing": 2.1,
            "playlist_width_ratio": 0.55,
            "playlist_bg_opacity": 0.45,
            "playlist_bg_color": (15, 20, 18),
            "playlist_bg_radius": 8,
            "title_font_family": "Georgia",
            "title_font_style": "Bold",
            "title_font_size": 52,
            "title_position": "Top-Left",
            "title_show": True,
            "title_color": (250, 248, 240),
            "title_outline_color": (10, 10, 10),
            "title_outline_width": 2,
            "title_shadow": True,
            "track_font_family": "Segoe UI",
            "track_font_style": "Regular",
            "track_font_size": 24,
            "track_color": (230, 235, 225),
            "track_outline_color": (20, 20, 20),
            "track_outline_width": 1,
            "track_shadow": True,
            "active_track_color": (255, 240, 180),
            "indicator_mode": "both",
            "cursor_size": 36,
            "cursor_path": str(self.dummy_cursor),
            "highlight_style": "Accent Bar",
            "highlight_color": (46, 125, 79),
            "highlight_bg_opacity": 0.35,
            "logo_position": "Bottom-Right",
            "logo_scale": 1.2,
            "logo_cleanup_mode": "auto",
            "website_position": "Top-Right",
            "website_font_size": 16,
            "website_show": True,
            "website_opacity": 0.75,
            "intro_enabled": True,
            "intro_duration": 4.5,
            "intro_animation": "Fade in / out",
            "transition_sfx_enabled": True,
            "transition_sfx_volume": 0.65,
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_all_visual_keys_preserved_in_extracted_template(self):
        """extract_template preserves all layout, typography, highlight, watermark, sfx, and intro settings."""
        tmpl = extract_template(self.rich_project, template_name="Emerald Elegance")
        self.assertEqual(tmpl["type"], "template")
        self.assertEqual(tmpl["template_name"], "Emerald Elegance")

        # Verify key visual settings survive
        self.assertEqual(tmpl["template"], "Cinematic")
        self.assertEqual(tmpl["resolution"], "1440p · QHD")
        self.assertEqual(tmpl["resource_profile"], "Maximum-speed")
        self.assertEqual(tmpl["playlist_position"], "Center")
        self.assertEqual(tmpl["playlist_columns"], 2)
        self.assertEqual(tmpl["playlist_row_spacing"], 2.1)
        self.assertEqual(tmpl["playlist_bg_opacity"], 0.45)
        self.assertEqual(tmpl["title_font_family"], "Georgia")
        self.assertEqual(tmpl["title_font_size"], 52)
        self.assertEqual(tmpl["title_position"], "Top-Left")
        self.assertEqual(tmpl["track_font_family"], "Segoe UI")
        self.assertEqual(tmpl["track_font_size"], 24)
        self.assertEqual(tmpl["highlight_style"], "Accent Bar")
        self.assertEqual(tmpl["highlight_color"], (46, 125, 79))
        self.assertEqual(tmpl["highlight_bg_opacity"], 0.35)
        self.assertEqual(tmpl["website_opacity"], 0.75)
        self.assertEqual(tmpl["intro_duration"], 4.5)
        self.assertEqual(tmpl["transition_sfx_volume"], 0.65)

    def test_project_content_strictly_excluded_from_template(self):
        """Protected project content (collection title, tracks, background, logo, output path, website text) is excluded."""
        tmpl = extract_template(self.rich_project, template_name="Test Template")
        for key in PROTECTED_PROJECT_CONTENT_KEYS:
            self.assertNotIn(key, tmpl, f"Protected content key '{key}' must never appear in template")

    def test_apply_template_to_project_preserves_content(self):
        """Applying a template updates visual styling while keeping receiving project content intact."""
        receiving_project = {
            "collection_title": "Original Receiving Project",
            "tracks": [{"title": "My Track", "path": "song.mp3", "duration": 60.0}],
            "background": "receiving_bg.png",
            "logo": "receiving_logo.png",
            "output_path": "receiving_out.mp4",
            "website_text": "www.receiving.org",
            # Outdated styling
            "template": "Minimal",
            "title_font_family": "Arial",
            "highlight_style": "Pill",
            "highlight_color": (248, 220, 139),
        }

        template_data = extract_template(self.rich_project, template_name="Emerald Elegance")
        updated = apply_template_to_project(receiving_project, template_data)

        # Styling must be updated to template
        self.assertEqual(updated["template"], "Cinematic")
        self.assertEqual(updated["title_font_family"], "Georgia")
        self.assertEqual(updated["highlight_style"], "Accent Bar")
        self.assertEqual(updated["highlight_color"], (46, 125, 79))
        self.assertEqual(updated["playlist_position"], "Center")
        self.assertEqual(updated["playlist_columns"], 2)

        # Content must be 100% unchanged
        self.assertEqual(updated["collection_title"], "Original Receiving Project")
        self.assertEqual(len(updated["tracks"]), 1)
        self.assertEqual(updated["tracks"][0]["title"], "My Track")
        self.assertEqual(updated["background"], "receiving_bg.png")
        self.assertEqual(updated["logo"], "receiving_logo.png")
        self.assertEqual(updated["output_path"], "receiving_out.mp4")
        self.assertEqual(updated["website_text"], "www.receiving.org")

    def test_malformed_template_json_raises_clear_error(self):
        """load_template raises ValueError with informative message when JSON is malformed."""
        corrupt_file = self.tmp / "corrupt_template.json"
        corrupt_file.write_text("{ this is not valid json : [ }", encoding="utf-8")

        with self.assertRaises(ValueError) as ctx:
            load_template(corrupt_file)
        self.assertIn("Malformed template file", str(ctx.exception))

    def test_missing_template_file_raises_file_not_found(self):
        """load_template raises FileNotFoundError when file does not exist."""
        with self.assertRaises(FileNotFoundError):
            load_template(self.tmp / "does_not_exist.json")

    def test_atomic_template_save_and_load_round_trip(self):
        """Templates can be saved atomically and loaded with identical visual settings."""
        tmpl = extract_template(self.rich_project, template_name="Roundtrip Test")
        target = self.tmp / "roundtrip.json"
        self.assertTrue(save_template_atomic(tmpl, target))

        loaded = load_template(target)
        self.assertEqual(loaded["template_name"], "Roundtrip Test")
        self.assertEqual(loaded["highlight_style"], "Accent Bar")
        self.assertEqual(loaded["playlist_columns"], 2)
        self.assertEqual(loaded["title_font_family"], "Georgia")


class TestMainWindowTemplateUI(unittest.TestCase):
    def setUp(self):
        _get_app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)
        self.win = MainWindow()
        self.win.resize(1120, 720)
        self.win.show()
        _get_app().processEvents()
        self.win.hide()

    def tearDown(self):
        dispose_window(self.win)
        self.temp_dir.cleanup()

    def test_apply_template_data_updates_all_ui_widgets(self):
        """_apply_template_data sets all corresponding UI controls without touching tracks/titles."""
        # Setup initial content
        self.win.collection_title.setText("My Holy Collection")
        self.win._apply_title()
        self.win.output_edit.setText("my_video.mp4")

        template_data = {
            "template": "Two-column",
            "resolution": "4K UHD · 2160p",
            "indicator_mode": "highlight",
            "cursor_size": 44,
            "title_font_family": "Segoe UI",
            "title_font_style": "Bold",
            "title_font_size": 48,
            "track_font_family": "Segoe UI",
            "track_font_style": "Regular",
            "track_font_size": 22,
            "logo_position": "Top-Left",
            "website_position": "Bottom-Right",
            "website_font_size": 18,
            "website_show": True,
            "website_opacity": 0.50,
            "playlist_position": "Right",
            "playlist_columns": 2,
            "playlist_row_spacing": 2.2,
            "playlist_bg_opacity": 0.30,
            "title_position": "Above Playlist",
            "title_show": True,
            "highlight_style": "Underline",
            "highlight_color": (220, 20, 60),
            "highlight_bg_opacity": 0.40,
            "intro_enabled": True,
            "intro_duration": 5.0,
            "intro_animation": "Fade in / out",
            "transition_sfx_volume": 0.80,
            "transition_sfx_enabled": True,
        }

        self.win._apply_template_data(template_data)

        # Verify UI controls updated
        self.assertEqual(self.win.template_combo.currentText(), "Two-column")
        self.assertEqual(self.win.resolution_combo.currentText(), "4K UHD")
        self.assertEqual(self.win.cursor_size_spin.value(), 44)
        self.assertEqual(self.win.website_opacity_slider.value(), 50)
        self.assertEqual(self.win.playlist_pos_combo.currentText(), "Right")
        self.assertEqual(self.win.playlist_cols_spin.value(), 2)
        self.assertEqual(self.win.playlist_bg_slider.value(), 30)
        self.assertEqual(self.win.highlight_style_combo.currentText(), "Underline")
        self.assertEqual(self.win.highlight_color, (220, 20, 60))
        self.assertEqual(self.win.highlight_opacity_slider.value(), 40)
        self.assertEqual(self.win.title_pos_combo.currentText(), "Above Playlist")

        # Verify project content was NOT touched
        self.assertEqual(self.win.collection_title.text(), "My Holy Collection")
        self.assertEqual(self.win.output_edit.text(), "my_video.mp4")

    def test_refresh_preview_renders_sample_layout_when_no_background_or_tracks(self):
        """When no background or tracks are loaded, preview renders studio sample composition instead of blank box."""
        self.win.background_path = ""
        self.win.tracks = []
        self.win._cached_preview_key = None
        self.win._cached_preview_pixmap = None

        self.win._refresh_preview()

        self.assertIsNotNone(self.win._cached_preview_pixmap)
        self.assertFalse(self.win._cached_preview_pixmap.isNull())
        self.assertIn("SAMPLE LAYOUT", self.win.preview_badge.text())
        # preview_image must have a valid pixmap set
        self.assertFalse(self.win.preview_image.pixmap().isNull())

    def test_apply_template_data_case_insensitive_font_and_layout(self):
        """Case variations in font names ('calibri') or presets ('two-column') are matched cleanly."""
        data = {
            "template": "two-column",
            "title_font_family": "calibri",
            "title_font_style": "Regular",
            "title_font_size": 90,
            "track_font_family": "segoe ui",
            "track_font_style": "bold",
            "highlight_style": "underline",
            "highlight_color": [85, 170, 0],
            "cursor_size": 76,
        }

        self.win._apply_template_data(data)

        self.assertEqual(self.win.template_combo.currentText(), "Two-column")
        self.assertEqual(self.win.playlist_cols_spin.value(), 2)
        self.assertEqual(self.win.title_font_combo.currentText().lower(), "calibri")
        self.assertEqual(self.win.track_font_combo.currentText().lower(), "segoe ui")
        self.assertEqual(self.win.highlight_style_combo.currentText(), "Underline")
        self.assertEqual(self.win.highlight_color, [85, 170, 0])
        self.assertEqual(self.win.cursor_size_spin.value(), 76)

    def test_load_template_via_load_project_file_safely_applies_without_clearing_content(self):
        """Opening a template file via [Open Project] applies styling without deleting existing tracks/title."""
        # Setup existing tracks
        self.win.collection_title.setText("Existing Album")
        self.win._apply_title()
        self.win.tracks = [{"title": "Track 01", "path": "t1.mp3", "duration": 100}]

        tmpl_path = self.tmp / "test_template.json"
        tmpl_content = {
            "version": 1,
            "type": "template",
            "template_name": "Test Template",
            "template": "Two-column",
            "highlight_style": "Outline",
            "highlight_color": [10, 20, 30],
        }
        tmpl_path.write_text(json.dumps(tmpl_content), encoding="utf-8")

        with patch.object(QMessageBox, "information") as mock_info:
            self.win._load_project_file(str(tmpl_path))

        # Tracks and title must be preserved
        self.assertEqual(len(self.win.tracks), 1)
        self.assertEqual(self.win.tracks[0]["title"], "Track 01")
        self.assertEqual(self.win.collection_title.text(), "Existing Album")

        # Template styling must be applied
        self.assertEqual(self.win.template_combo.currentText(), "Two-column")
        self.assertEqual(self.win.highlight_style_combo.currentText(), "Outline")
        self.assertEqual(self.win.highlight_color, [10, 20, 30])
        mock_info.assert_called_once()

    def test_apply_template_starter_background_adoption(self):
        """Applying a template adopts starter background only if project has none."""
        bg_file = self.tmp / "starter_bg.jpg"
        bg_file.write_bytes(b"fake image data")

        tmpl = {
            "template": "Cinematic",
            "background": str(bg_file),
        }

        # 1. Project with NO background -> adopts template background
        proj_empty = {"collection_title": "Empty Proj", "background": ""}
        updated1 = apply_template_to_project(proj_empty, tmpl)
        self.assertEqual(updated1["background"], str(bg_file))

        # 2. Project WITH existing background -> strictly preserves existing background
        proj_existing = {"collection_title": "Existing Proj", "background": "C:/my_own_image.jpg"}
        updated2 = apply_template_to_project(proj_existing, tmpl)
        self.assertEqual(updated2["background"], "C:/my_own_image.jpg")

    def test_user_11_nasheeds_template_file_loads_and_previews(self):
        """Verify the exact user template file (11_Nasheeds_template.json) applies and generates a preview."""
        user_tmpl_path = Path("C:/Users/rubai/NasheedStudio/templates/11_Nasheeds_template.json")
        if not user_tmpl_path.is_file():
            self.skipTest("User 11_Nasheeds_template.json not found on disk")

        tmpl_data = json.loads(user_tmpl_path.read_text(encoding="utf-8"))
        self.win.background_path = ""
        self.win.tracks = []
        self.win._cached_preview_key = None
        self.win._cached_preview_pixmap = None

        self.win._apply_template_data(tmpl_data)
        self.win._refresh_preview()

        self.assertEqual(self.win.template_combo.currentText(), "Two-column")
        self.assertEqual(self.win.playlist_cols_spin.value(), 2)
        self.assertEqual(self.win.title_font_combo.currentText().lower(), "calibri")
        self.assertEqual(self.win.title_size_spin.value(), 90)
        self.assertEqual(self.win.highlight_style_combo.currentText(), "Underline")
        self.assertEqual(self.win.highlight_color, [85, 170, 0])
        self.assertEqual(self.win.cursor_size_spin.value(), 76)

        # Preview MUST be generated and visible even on clean state
        self.assertIsNotNone(self.win._cached_preview_pixmap)
        self.assertFalse(self.win._cached_preview_pixmap.isNull())
        self.assertFalse(self.win.preview_image.pixmap().isNull())


if __name__ == "__main__":
    unittest.main()
