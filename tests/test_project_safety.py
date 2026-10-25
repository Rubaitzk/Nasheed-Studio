"""
Tests for Stage 1 Project Safety, Atomic Saving, Templates, and Asset Management.

Requirements covered:
1. Atomic project save: temporary file write with fsync; target never corrupted on error.
2. Separate template operations: templates store styling/design only; never wipe tracklists.
3. Missing asset detection on load.
4. Asset relinking workflow.
5. Managed asset bundling: copy-and-verify into project bundle without touching originals.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services.project_service import (
    save_project_atomic,
    extract_template,
    save_template_atomic,
    load_template,
    apply_template_to_project,
    check_missing_assets,
    relink_asset,
    bundle_managed_assets,
    TEMPLATE_DESIGN_KEYS,
)
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window


class TestProjectSafety(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        self.sample_project = {
            "version": 1,
            "collection_title": "Original Collection Title",
            "background": str(self.tmp / "bg.png"),
            "logo": str(self.tmp / "logo.png"),
            "tracks": [
                {"title": "Track One", "path": str(self.tmp / "t1.wav"), "duration": 10.0},
                {"title": "Track Two", "path": str(self.tmp / "t2.wav"), "duration": 12.0},
            ],
            "template": "Minimal",
            "resolution": "1440p · QHD",
            "indicator_mode": "highlight_only",
            "cursor_size": 48,
            "title_font_family": "Calibri",
            "title_font_style": "Bold",
            "title_font_size": 50,
            "track_font_family": "Arial",
            "track_font_style": "Regular",
            "track_font_size": 24,
            "logo_position": "Top-Left",
            "website_text": "www.original.org",
            "website_position": "Bottom-Right",
            "website_font_size": 18,
            "intro_enabled": True,
            "intro_duration": 4.0,
            "intro_animation": "Zoom in",
            "transition_sfx_enabled": True,
            "transition_sfx_path": str(self.tmp / "whoosh.wav"),
            "transition_sfx_volume": 0.85,
            "output_path": str(self.tmp / "output.mp4"),
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # 1. Atomic Project Saving
    # ------------------------------------------------------------------
    def test_atomic_project_save_success(self):
        """Atomic save creates a valid JSON file."""
        target = self.tmp / "proj.json"
        success = save_project_atomic(self.sample_project, target)
        self.assertTrue(success)
        self.assertTrue(target.exists())

        loaded = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(loaded["collection_title"], "Original Collection Title")
        self.assertEqual(len(loaded["tracks"]), 2)

    def test_atomic_project_save_preserves_existing_on_error(self):
        """If writing fails midway, original project file is preserved without corruption."""
        target = self.tmp / "existing_project.json"
        original_data = '{"original": "valid_content_that_must_not_be_corrupted"}'
        target.write_text(original_data, encoding="utf-8")

        # Mock json.dumps to simulate serialization/IO crash
        with patch("json.dumps", side_effect=TypeError("Simulated serialization crash")):
            with self.assertRaises(IOError):
                save_project_atomic(self.sample_project, target)

        # Target must be completely unchanged
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), original_data)

    # ------------------------------------------------------------------
    # 2. Template Separation & Application
    # ------------------------------------------------------------------
    def test_template_extraction_excludes_tracks_and_titles(self):
        """Extracting a template preserves visual design keys and excludes tracks/titles."""
        tmpl = extract_template(self.sample_project, template_name="Nasheed Cinema")

        self.assertEqual(tmpl["type"], "template")
        self.assertEqual(tmpl["template_name"], "Nasheed Cinema")
        self.assertEqual(tmpl["template"], "Minimal")
        self.assertEqual(tmpl["resolution"], "1440p · QHD")
        self.assertEqual(tmpl["title_font_family"], "Calibri")

        # Must NOT contain collection title, tracks, or specific file paths
        self.assertNotIn("collection_title", tmpl)
        self.assertNotIn("tracks", tmpl)
        self.assertNotIn("background", tmpl)
        self.assertNotIn("logo", tmpl)
        self.assertNotIn("output_path", tmpl)

    def test_template_save_and_load(self):
        """Templates can be saved and loaded atomically."""
        tmpl = extract_template(self.sample_project, "My Preset")
        tmpl_file = self.tmp / "my_preset.json"
        save_template_atomic(tmpl, tmpl_file)

        loaded = load_template(tmpl_file)
        self.assertEqual(loaded["template_name"], "My Preset")
        self.assertEqual(loaded["cursor_size"], 48)

    def test_apply_template_preserves_collection_and_tracks(self):
        """Applying a template updates visual design while preserving current collection and tracks."""
        base_proj = {
            "collection_title": "Sacred Recitations",
            "tracks": [{"title": "Surah Al-Fatihah", "path": "quran.mp3", "duration": 45.0}],
            "background": "custom_bg.png",
            "logo": "custom_logo.png",
            "output_path": "recitations.mp4",
            "template": "Cinematic",
            "title_font_family": "Segoe UI",
        }

        template_data = {
            "template": "Two-column",
            "title_font_family": "Georgia",
            "title_font_size": 60,
            "indicator_mode": "both",
        }

        updated = apply_template_to_project(base_proj, template_data)

        # Styling updated
        self.assertEqual(updated["template"], "Two-column")
        self.assertEqual(updated["title_font_family"], "Georgia")
        self.assertEqual(updated["title_font_size"], 60)
        self.assertEqual(updated["indicator_mode"], "both")

        # Collection title and tracklist strictly preserved
        self.assertEqual(updated["collection_title"], "Sacred Recitations")
        self.assertEqual(len(updated["tracks"]), 1)
        self.assertEqual(updated["tracks"][0]["title"], "Surah Al-Fatihah")
        self.assertEqual(updated["background"], "custom_bg.png")

    # ------------------------------------------------------------------
    # 3. Missing Asset Detection & Relinking
    # ------------------------------------------------------------------
    def test_check_missing_assets(self):
        """check_missing_assets detects missing files across all media types."""
        # Create only background; leave logo, cursor, and tracks missing
        real_bg = self.tmp / "real_bg.png"
        real_bg.write_bytes(b"dummy")

        proj = dict(self.sample_project)
        proj["background"] = str(real_bg)

        missing = check_missing_assets(proj)
        self.assertNotIn("background", missing)
        self.assertIn("logo", missing)
        self.assertIn("tracks", missing)
        self.assertEqual(len(missing["tracks"]), 2)

    def test_relink_asset(self):
        """relink_asset updates old path to new path in tracks or top-level assets."""
        old_track = str(self.tmp / "t1.wav")
        new_track = str(self.tmp / "new_t1_relocated.wav")

        relinked = relink_asset(self.sample_project, old_track, new_track)
        self.assertEqual(relinked["tracks"][0]["path"], new_track)
        self.assertEqual(relinked["tracks"][1]["path"], str(self.tmp / "t2.wav"))

    # ------------------------------------------------------------------
    # 4. Managed Asset Bundling (Copy-first, verify, preserve originals)
    # ------------------------------------------------------------------
    def test_bundle_managed_assets(self):
        """bundle_managed_assets copies assets into project bundle without touching originals."""
        orig_bg = self.tmp / "source_bg.png"
        orig_bg.write_bytes(b"BACKGROUND_BYTES_12345")

        orig_track = self.tmp / "source_track.mp3"
        orig_track.write_bytes(b"AUDIO_DATA_67890")

        proj = {
            "background": str(orig_bg),
            "tracks": [{"title": "Song 1", "path": str(orig_track)}],
        }

        bundle_dir = self.tmp / "MyProjectBundle"
        managed = bundle_managed_assets(proj, bundle_dir)

        # Verify new paths are inside bundle
        new_bg = Path(managed["background"])
        new_track = Path(managed["tracks"][0]["path"])

        self.assertTrue(new_bg.is_file())
        self.assertTrue(new_track.is_file())
        self.assertEqual(new_bg.parent.name, "images")
        self.assertEqual(new_track.parent.name, "audio")

        # Verify contents match
        self.assertEqual(new_bg.read_bytes(), b"BACKGROUND_BYTES_12345")
        self.assertEqual(new_track.read_bytes(), b"AUDIO_DATA_67890")

        # Verify originals still exist and were NOT deleted
        self.assertTrue(orig_bg.exists())
        self.assertTrue(orig_track.exists())
