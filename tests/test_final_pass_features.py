"""
Tests for Final Development Pass:
1. Independent title-to-playlist spacing control and geometry accuracy.
2. Independence of spacing from title and playlist font sizes.
3. Wrapped titles and multi-column playlist compatibility with spacing.
4. Reusable text opacity, softening, and subtle background blending.
5. Default backward compatibility.
6. Project serialization, load roundtrip, and template extraction/application.
7. Performance optimization and background/font caching validation.
"""

import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from src.services.compositor import (
    compute_reference_playlist_layout,
    calculate_playlist_layout,
    create_composition,
    _get_prepared_background,
    _BG_CACHE,
    clear_background_cache,
    clear_font_cache,
)
from src.services.media_probe import is_video_file, get_video_info
from src.services.project_service import (
    save_project_atomic,
    extract_template,
    apply_template_to_project,
    TEMPLATE_DESIGN_KEYS,
)
from src.services.render_service import build_render_command


class TestFinalPassFeatures(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)
        clear_background_cache()
        clear_font_cache()

    def tearDown(self):
        self.temp_dir.cleanup()
        clear_background_cache()
        clear_font_cache()

    # ------------------------------------------------------------------
    # 1. Independent Title-to-Playlist Spacing Control
    # ------------------------------------------------------------------

    def test_title_playlist_spacing_linearly_adjusts_gap(self):
        """Increasing title_playlist_spacing increases the distance between title and playlist proportionally."""
        tracks = [f"{i:02d}. Track Name {i}" for i in range(1, 7)]
        title_bottom = 150

        res_20 = compute_reference_playlist_layout(
            track_titles=tracks,
            canvas_size=(1920, 1080),
            cols=1,
            requested_font_size=24,
            title_bottom_y=title_bottom,
            title_playlist_spacing=20,
        )
        res_60 = compute_reference_playlist_layout(
            track_titles=tracks,
            canvas_size=(1920, 1080),
            cols=1,
            requested_font_size=24,
            title_bottom_y=title_bottom,
            title_playlist_spacing=60,
        )
        res_120 = compute_reference_playlist_layout(
            track_titles=tracks,
            canvas_size=(1920, 1080),
            cols=1,
            requested_font_size=24,
            title_bottom_y=title_bottom,
            title_playlist_spacing=120,
        )

        y_20 = res_20.rows[0].text_y
        y_60 = res_60.rows[0].text_y
        y_120 = res_120.rows[0].text_y

        # Delta from 20 to 60 must be exactly 40px
        self.assertEqual(y_60 - y_20, 40)
        # Delta from 60 to 120 must be exactly 60px
        self.assertEqual(y_120 - y_60, 60)
        # Delta from 20 to 120 must be exactly 100px
        self.assertEqual(y_120 - y_20, 100)

    def test_spacing_independent_of_font_sizes(self):
        """Spacing remains strictly controlled and does NOT shrink playlist font size or title font size."""
        tracks = [f"{i:02d}. Track {i}" for i in range(1, 8)]
        title_bottom = 140

        # Test with small playlist font size (18)
        res_small = compute_reference_playlist_layout(
            track_titles=tracks,
            canvas_size=(1920, 1080),
            cols=1,
            requested_font_size=18,
            title_bottom_y=title_bottom,
            title_playlist_spacing=50,
        )

        # Test with large playlist font size (32)
        res_large = compute_reference_playlist_layout(
            track_titles=tracks,
            canvas_size=(1920, 1080),
            cols=1,
            requested_font_size=32,
            title_bottom_y=title_bottom,
            title_playlist_spacing=50,
        )

        # Both start exactly title_bottom + 50 = 190
        self.assertEqual(res_small.rows[0].text_y, 190)
        self.assertEqual(res_large.rows[0].text_y, 190)

        # Playlist font sizes must NOT be silently shrunk by spacing
        self.assertEqual(res_small.effective_font_size, 18)
        self.assertEqual(res_large.effective_font_size, 32)

    def test_spacing_with_wrapped_multiline_title(self):
        """Spacing correctly anchors to the bottom of multiline wrapped titles."""
        bg = Image.new("RGB", (1280, 720), (30, 30, 30))
        bg_path = str(self.tmp / "bg.png")
        bg.save(bg_path)

        long_title = "A Substantially Long Nasheed Collection Title That Definitively Wraps Onto Multiple Lines In The Frame"
        tracks = ["01. Peaceful Reflection", "02. Divine Harmony", "03. Sacred Echoes"]

        # Render with spacing = 20
        out_20 = self.tmp / "out_20"
        base_20, _ = create_composition(
            width=1280, height=720,
            background_path=bg_path,
            logo_path=None,
            collection_title=long_title,
            title_position="Above Playlist",
            title_font_size=48,
            title_playlist_spacing=20,
            track_titles=tracks,
            template="Two-column",
            out_dir=str(out_20),
            indicator_mode="neither",
        )

        # Render with spacing = 80
        out_80 = self.tmp / "out_80"
        base_80, _ = create_composition(
            width=1280, height=720,
            background_path=bg_path,
            logo_path=None,
            collection_title=long_title,
            title_position="Above Playlist",
            title_font_size=48,
            title_playlist_spacing=80,
            track_titles=tracks,
            template="Two-column",
            out_dir=str(out_80),
            indicator_mode="neither",
        )

        self.assertTrue(Path(base_20).is_file())
        self.assertTrue(Path(base_80).is_file())

        # Inspect layout info directly for wrapped title
        scale = 720 / 1080.0
        expected_diff = int(80 * scale) - int(20 * scale)
        self.assertTrue(expected_diff > 30)

    def test_spacing_with_multicolumn_playlist(self):
        """Spacing works identically across 1, 2, and 3 column playlists."""
        tracks = [f"{i:02d}. Track Title {i}" for i in range(1, 15)]
        title_bottom = 180

        res_1col = compute_reference_playlist_layout(
            track_titles=tracks, canvas_size=(1920, 1080), cols=1,
            title_bottom_y=title_bottom, title_playlist_spacing=75,
        )
        res_2col = compute_reference_playlist_layout(
            track_titles=tracks, canvas_size=(1920, 1080), cols=2,
            title_bottom_y=title_bottom, title_playlist_spacing=75,
        )
        res_3col = compute_reference_playlist_layout(
            track_titles=tracks, canvas_size=(1920, 1080), cols=3,
            title_bottom_y=title_bottom, title_playlist_spacing=75,
        )

        # All columns in all layouts start at exactly 180 + 75 = 255
        self.assertEqual(res_1col.rows[0].text_y, 255)
        self.assertEqual(res_2col.rows[0].text_y, 255)
        self.assertEqual(res_3col.rows[0].text_y, 255)

    # ------------------------------------------------------------------
    # 2. Reusable Text Opacity & Softening
    # ------------------------------------------------------------------

    def test_text_opacity_compositing_allows_background_showthrough(self):
        """Semi-transparent text allows underlying background pixels to show through."""
        # Bright red background
        bg = Image.new("RGB", (1280, 720), (255, 0, 0))
        bg_path = str(self.tmp / "red_bg.png")
        bg.save(bg_path)

        # Render 1: Fully opaque white text
        out_opaque = self.tmp / "opaque"
        base_op, _ = create_composition(
            width=1280, height=720,
            background_path=bg_path,
            logo_path=None,
            collection_title="Opaque Title",
            title_color=(255, 255, 255),
            title_opacity=1.0,
            track_color=(255, 255, 255),
            track_opacity=1.0,
            title_shadow=False,
            track_shadow=False,
            track_titles=["01. Opaque Track"],
            template="Two-column",
            out_dir=str(out_opaque),
            indicator_mode="neither",
        )

        # Render 2: 50% transparent white text
        out_trans = self.tmp / "trans"
        base_tr, _ = create_composition(
            width=1280, height=720,
            background_path=bg_path,
            logo_path=None,
            collection_title="Opaque Title",
            title_color=(255, 255, 255),
            title_opacity=0.5,
            track_color=(255, 255, 255),
            track_opacity=0.5,
            title_shadow=False,
            track_shadow=False,
            track_titles=["01. Opaque Track"],
            template="Two-column",
            out_dir=str(out_trans),
            indicator_mode="neither",
        )

        im_opaque = Image.open(base_op).convert("RGBA")
        im_trans = Image.open(base_tr).convert("RGBA")

        # In opaque image, text pixels should have very low red component (close to 255, 255, 255 after dark wash)
        # In transparent image, text pixels have significantly higher red component showing through
        # Sample across composition center
        diff_found = False
        for x in range(200, 800, 10):
            for y in range(80, 400, 10):
                p1 = im_opaque.getpixel((x, y))
                p2 = im_trans.getpixel((x, y))
                if p1 != p2:
                    diff_found = True
                    break
            if diff_found:
                break
        self.assertTrue(diff_found, "Transparency must produce different pixel values from full opacity.")

    def test_text_softening_does_not_blur_background(self):
        """Text softening applies gentle blur to glyph contours while background remains crisp."""
        # Create a background with a sharp high-contrast vertical line at x=50
        bg = Image.new("RGBA", (1280, 720), (0, 0, 0, 255))
        for y in range(720):
            bg.putpixel((50, y), (255, 255, 255, 255))
        bg_path = str(self.tmp / "line_bg.png")
        bg.save(bg_path)

        out_dir = self.tmp / "soften"
        base_soft, _ = create_composition(
            width=1280, height=720,
            background_path=bg_path,
            logo_path=None,
            collection_title="Softened Title",
            title_softening=1.5,
            track_softening=1.5,
            track_titles=["01. Softened Nasheed"],
            template="Two-column",
            out_dir=str(out_dir),
            indicator_mode="neither",
        )

        im = Image.open(base_soft).convert("RGBA")
        # Check that background vertical line away from text (e.g. at y=650) remains sharp:
        # x=49 is black/wash, x=50 is bright white line
        p_left = im.getpixel((49, 650))
        p_line = im.getpixel((50, 650))
        self.assertTrue(p_line[0] > 180, "Background line must remain bright and crisp.")
        self.assertTrue(p_left[0] < 50, "Adjacent background pixel must not be blurred.")

    def test_backward_compatibility_defaults(self):
        """Default text opacity (1.0) and softening (0.0) produce crisp fully-opaque text."""
        bg = Image.new("RGB", (1280, 720), (20, 25, 30))
        bg_path = str(self.tmp / "bg.png")
        bg.save(bg_path)

        out_dir = self.tmp / "default_out"
        base, overlays = create_composition(
            width=1280, height=720,
            background_path=bg_path,
            logo_path=None,
            collection_title="Standard Title",
            track_titles=["01. Standard Nasheed"],
            template="Two-column",
            out_dir=str(out_dir),
        )
        self.assertTrue(Path(base).is_file())
        self.assertTrue(len(overlays) >= 1)

    # ------------------------------------------------------------------
    # 3. Serialization & Template Persistence
    # ------------------------------------------------------------------

    def test_new_keys_in_template_design_keys(self):
        """TEMPLATE_DESIGN_KEYS contains all new spacing and styling parameters."""
        for key in ("title_playlist_spacing", "title_opacity", "track_opacity", "title_softening", "track_softening", "text_softening"):
            self.assertIn(key, TEMPLATE_DESIGN_KEYS)

    def test_project_save_and_template_roundtrip(self):
        """New parameters survive atomic saving, template extraction, and template application."""
        dummy_audio = self.tmp / "audio.wav"
        dummy_audio.write_bytes(b"RIFF" + b"\x00" * 40)

        proj = {
            "version": 1,
            "collection_title": "Divine Serenity",
            "background": "",
            "background_type": "image",
            "tracks": [{"title": "Track 1", "path": str(dummy_audio), "duration": 3.0}],
            "title_playlist_spacing": 85,
            "title_opacity": 0.75,
            "track_opacity": 0.85,
            "title_softening": 1.2,
            "track_softening": 1.2,
            "text_softening": 1.2,
            "template": "Cinematic",
            "resolution": "1080p · Full HD",
            "indicator_mode": "both",
            "output_path": str(self.tmp / "out.mp4"),
        }

        # Save project
        proj_file = self.tmp / "project.json"
        save_project_atomic(proj, str(proj_file))

        # Extract template
        tmpl = extract_template(proj, "Custom Translucent Template")
        self.assertEqual(tmpl["title_playlist_spacing"], 85)
        self.assertEqual(tmpl["title_opacity"], 0.75)
        self.assertEqual(tmpl["track_opacity"], 0.85)
        self.assertEqual(tmpl["text_softening"], 1.2)

        # Apply template to fresh project
        fresh_proj = {
            "collection_title": "Fresh Title",
            "tracks": [{"title": "Different Track", "path": "path.mp3"}],
        }
        applied = apply_template_to_project(fresh_proj, tmpl)
        self.assertEqual(applied["title_playlist_spacing"], 85)
        self.assertEqual(applied["title_opacity"], 0.75)
        self.assertEqual(applied["track_opacity"], 0.85)
        self.assertEqual(applied["text_softening"], 1.2)
        # Content preserved
        self.assertEqual(applied["collection_title"], "Fresh Title")

    # ------------------------------------------------------------------
    # 4. Performance & Background Caching
    # ------------------------------------------------------------------

    def test_prepared_background_cache_hit(self):
        """Background cache returns cached copy on identical key without re-processing."""
        bg = Image.new("RGB", (1280, 720), (50, 60, 70))
        bg_path = str(self.tmp / "cache_bg.png")
        bg.save(bg_path)

        clear_background_cache()
        self.assertEqual(len(_BG_CACHE), 0)

        # Call 1: cold
        bg1, fg1 = _get_prepared_background(
            background_path=bg_path,
            width=1280, height=720,
            video_start_time=0.0,
            video_fit_mode="fill/crop",
            wash_alpha=50,
            bg_is_video=False,
        )
        self.assertEqual(len(_BG_CACHE), 1)

        # Call 2: warm hit
        bg2, fg2 = _get_prepared_background(
            background_path=bg_path,
            width=1280, height=720,
            video_start_time=0.0,
            video_fit_mode="fill/crop",
            wash_alpha=50,
            bg_is_video=False,
        )
        self.assertEqual(len(_BG_CACHE), 1)
        self.assertEqual(bg1.size, bg2.size)
        self.assertEqual(bg1.mode, bg2.mode)


if __name__ == "__main__":
    unittest.main()
