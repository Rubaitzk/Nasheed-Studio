"""
Comprehensive automated tests for the Nasheed Studio playlist layout engine.
Covers:
1. Short and long track names.
2. Names longer than 80 characters.
3. Mixed title lengths and titles containing punctuation or non-ASCII characters.
4. Dynamic column selection across 1, 2, 3, and 4 columns.
5. Automatic selection of 3 columns when appropriate.
6. Narrow and wide layouts with user-adjustable column spacing.
7. Output resolution scaling (1080p, 1440p, 4K UHD).
8. Preview and export layout consistency.
9. Save/load and template round-trip persistence.
"""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.services.compositor import calculate_playlist_layout, create_composition, _get_font
from src.services.project_service import (
    save_project_atomic,
    extract_template,
    save_template_atomic,
    load_template,
    apply_template_to_project,
)
from src.ui.main_window import MainWindow

_app = None

def _get_qapp():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestReferenceLayoutEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _get_qapp()

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_dir.name)
        self.bg_path = self.tmp / "bg.png"
        with Image.new("RGB", (1920, 1080), (20, 22, 25)) as img:
            img.save(self.bg_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    # ------------------------------------------------------------------
    # 1. Short and long track names
    # ------------------------------------------------------------------
    def test_short_and_long_track_names_fit_without_premature_ellipsis(self):
        """Short and moderately long track names fit completely without premature ellipses when space allows."""
        titles = [
            "Dua",
            "Sabr",
            "The Way of the Tears (Nasheed of Patience)",
            "Mahum Be Umati Ahmadin",
            "Kun Anta",
            "Qamarun Sidna Nabi",
            "Light Upon Light Throughout The Night",
            "Serna Serna",
        ]
        layout = calculate_playlist_layout(
            track_titles=titles,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.60,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=24,
            track_wrap_text=False,
            title_bottom_y=160,
        )
        items = layout["track_items"]
        self.assertEqual(len(items), 8)
        # Verify complete title "Mahum Be Umati Ahmadin" fits without ellipsis
        mahum = [it for it in items if "Mahum Be Umati Ahmadin" in it["text"]]
        self.assertTrue(bool(mahum))
        self.assertNotIn("…", mahum[0]["text"])
        self.assertEqual(mahum[0]["text"], "04. Mahum Be Umati Ahmadin")

        # Verify "The Way of the Tears (Nasheed of Patience)" fits without ellipsis
        tears = [it for it in items if "The Way of the Tears" in it["text"]]
        self.assertTrue(bool(tears))
        self.assertNotIn("…", tears[0]["text"])

    # ------------------------------------------------------------------
    # 2. Names longer than 80 characters
    # ------------------------------------------------------------------
    def test_names_longer_than_80_chars_wrapping_and_boundary_safety(self):
        """Titles over 80 characters wrap when enabled, or truncate cleanly with prefix at column boundary."""
        title_95_chars = "A Very Long Majestic Nasheed Title Exceeding Ninety Characters In Total Length For Studio Video"
        self.assertGreater(len(title_95_chars), 80)

        # A. With track_wrap_text=True: wraps to second line
        layout_wrap = calculate_playlist_layout(
            track_titles=[title_95_chars, "Normal Track"],
            width=1920,
            height=1080,
            template="Cinematic",
            playlist_position="Left",
            playlist_columns=1,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.30,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=24,
            track_wrap_text=True,
            title_bottom_y=160,
        )
        item_wrap = layout_wrap["track_items"][0]
        self.assertIn("\n", item_wrap["text"], "Long title should wrap onto multiple lines when wrapping is enabled")
        self.assertTrue(item_wrap["text"].startswith("01. "))

        # B. With track_wrap_text=False: truncates at column boundary preserving prefix and ending with …
        layout_nowrap = calculate_playlist_layout(
            track_titles=[title_95_chars, "Short Track"],
            width=1920,
            height=1080,
            template="Cinematic",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.50,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=24,
            track_wrap_text=False,
            title_bottom_y=160,
        )
        item_nowrap = layout_nowrap["track_items"][0]
        self.assertTrue(item_nowrap["text"].endswith("…"))
        self.assertTrue(item_nowrap["text"].startswith("01. "))
        self.assertGreater(len(item_nowrap["text"]), 15)
        # Column 1 starts within boundary
        self.assertLess(layout_nowrap["track_items"][1]["x"], 1920 * 0.70)

    # ------------------------------------------------------------------
    # 3. Mixed title lengths, punctuation, and non-ASCII characters
    # ------------------------------------------------------------------
    def test_mixed_titles_punctuation_and_non_ascii_support(self):
        """Titles with Arabic text, French accents, quotes, and punctuation render cleanly with correct layout."""
        mixed_tracks = [
            'نشيد الهدى والنور (Al-Huda)',
            'Qur\'an: "Surah Al-Kahf" - Verses 1-10',
            'Célébration & Méditation',
            'Track #04: Peace, Mercy & Blessings',
            'صلّى الله عليه وسلم (Salawat)',
        ]
        layout = calculate_playlist_layout(
            track_titles=mixed_tracks,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Center",
            playlist_columns=2,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.60,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=24,
            track_wrap_text=False,
            title_bottom_y=160,
        )
        items = layout["track_items"]
        self.assertEqual(len(items), 5)
        # Arabic title preserved
        self.assertIn('نشيد الهدى والنور', items[0]["text"])
        # French accents preserved
        self.assertIn('Célébration', items[2]["text"])
        # Quotes and punctuation preserved
        self.assertIn('"Surah Al-Kahf"', items[1]["text"])

    # ------------------------------------------------------------------
    # 4. Multi-column scaling: 1, 2, 3, and 4 columns
    # ------------------------------------------------------------------
    def test_multi_column_scaling_1_2_3_4_columns(self):
        """Layout engine correctly supports 1, 2, 3, and 4 columns according to constraints and user preference."""
        tracks_20 = [f"Track Number {i + 1:02d}" for i in range(20)]

        # Explicit 4 columns
        layout_4 = calculate_playlist_layout(
            track_titles=tracks_20,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Center",
            playlist_columns=4,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.85,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=20,
            track_wrap_text=False,
        )
        self.assertEqual(layout_4["num_cols"], 4)
        self.assertEqual(len(layout_4["col_widths"]), 4)

        # Explicit 3 columns
        layout_3 = calculate_playlist_layout(
            track_titles=tracks_20,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Center",
            playlist_columns=3,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.75,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=22,
            track_wrap_text=False,
        )
        self.assertEqual(layout_3["num_cols"], 3)
        self.assertEqual(len(layout_3["col_widths"]), 3)

        # 4 tracks with 1 column
        layout_1 = calculate_playlist_layout(
            track_titles=tracks_20[:4],
            width=1920,
            height=1080,
            template="Cinematic",
            playlist_position="Left",
            playlist_columns=1,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.30,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=24,
            track_wrap_text=False,
        )
        self.assertEqual(layout_1["num_cols"], 1)

    # ------------------------------------------------------------------
    # 5. Three columns fit and selected over two
    # ------------------------------------------------------------------
    def test_three_columns_fit_selected_over_two(self):
        """When playlist has many tracks and sufficient horizontal space, 3 columns is dynamically chosen."""
        fifteen_tracks = [f"Nasheed Hymn {i + 1:02d}" for i in range(15)]
        layout = calculate_playlist_layout(
            track_titles=fifteen_tracks,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Center",
            playlist_columns=1,  # Auto-split requested
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.70,  # Generous width
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=24,
            track_wrap_text=False,
            title_bottom_y=160,
        )
        self.assertEqual(layout["num_cols"], 3, "15 tracks with wide width should dynamically select 3 columns")
        self.assertFalse(layout["overflow"], "Playlist must not overflow frame")
        # 15 tracks across 3 columns gives 5 rows per column
        col_0_items = [it for it in layout["track_items"] if it["box"][0] == layout["track_items"][0]["box"][0]]
        self.assertEqual(len(col_0_items), 5)

    # ------------------------------------------------------------------
    # 6. Narrow and wide layouts with different column-spacing values
    # ------------------------------------------------------------------
    def test_narrow_and_wide_layouts_and_column_spacing(self):
        """User column spacing (20px, 60px, 140px) is strictly respected between all adjacent columns."""
        tracks = [f"Track {i + 1:02d}" for i in range(9)]
        for gap_px in (20, 60, 140):
            layout = calculate_playlist_layout(
                track_titles=tracks,
                width=1920,
                height=1080,
                template="Two-column",
                playlist_position="Left",
                playlist_columns=3,
                playlist_row_spacing=1.85,
                playlist_width_ratio=0.75,
                playlist_x_offset=0,
                playlist_y_offset=0,
                track_font_family="Segoe UI",
                track_font_style="Bold",
                track_font_size=24,
                track_wrap_text=False,
                playlist_col_spacing=gap_px,
            )
            items = layout["track_items"]
            # per_col is 3 (9 // 3). Tracks 0, 3, 6 start columns 0, 1, 2
            x0 = items[0]["x"]
            w0 = layout["col_widths"][0]
            x1 = items[3]["x"]
            w1 = layout["col_widths"][1]
            x2 = items[6]["x"]

            gap_0_1 = x1 - (x0 + w0)
            gap_1_2 = x2 - (x1 + w1)
            self.assertEqual(gap_0_1, gap_px, f"Gap between Col 0 and Col 1 must be {gap_px}px")
            self.assertEqual(gap_1_2, gap_px, f"Gap between Col 1 and Col 2 must be {gap_px}px")

    # ------------------------------------------------------------------
    # 7. All three output resolutions: 1080p, 1440p, 4K UHD
    # ------------------------------------------------------------------
    def test_multi_resolution_scaling_1080p_1440p_4k(self):
        """Full compositions render crisply across 1080p, 1440p, and 4K UHD with proper resolution scaling."""
        tracks = [
            "Kuntu Maitan",
            "Mahum Be Umati Ahmadin",
            "Habbat Karreeh",
            "Hallaka Sirrun Indallah",
            "Fataat al Khair",
            "We are the Heroes",
        ]
        resolutions = [
            (1920, 1080),
            (2560, 1440),
            (3840, 2160),
        ]
        with tempfile.TemporaryDirectory() as tmp_render:
            for w, h in resolutions:
                bg_f = Path(tmp_render) / f"bg_{w}x{h}.png"
                with Image.new("RGB", (w, h), (18, 20, 22)) as im:
                    im.save(bg_f)

                base_p, ov_p = create_composition(
                    width=w,
                    height=h,
                    background_path=str(bg_f),
                    logo_path=None,
                    collection_title="Resolution Quality Verification",
                    track_titles=tracks,
                    template="Two-column",
                    playlist_position="Center",
                    playlist_columns=2,
                    out_dir=tmp_render,
                    indicator_mode="highlight",
                    highlight_style="Pill",
                    active_track_index=1,
                    preview_only_first_overlay=True,
                )
                self.assertTrue(Path(base_p).is_file())
                self.assertEqual(len(ov_p), 1)
                with Image.open(base_p) as b_img, Image.open(ov_p[0]) as o_img:
                    self.assertEqual(b_img.size, (w, h))
                    self.assertEqual(o_img.size, (w, h))

    # ------------------------------------------------------------------
    # 8. Preview/export layout consistency
    # ------------------------------------------------------------------
    def test_preview_and_export_layout_consistency(self):
        """Preview composition and export composition use identical layout metrics and track placements."""
        tracks = ["Track Alpha", "Track Beta Long Title Extension", "Track Gamma"]
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            # 1. Preview render (preview_only_first_overlay=True)
            base_prev, ov_prev = create_composition(
                width=1920,
                height=1080,
                background_path=str(self.bg_path),
                logo_path=None,
                collection_title="Consistency Check",
                track_titles=tracks,
                template="Cinematic",
                playlist_position="Left",
                playlist_columns=2,
                playlist_col_spacing=45,
                out_dir=tmp_a,
                indicator_mode="highlight",
                active_track_index=0,
                preview_only_first_overlay=True,
            )
            # 2. Export render (preview_only_first_overlay=False)
            base_exp, ov_exp = create_composition(
                width=1920,
                height=1080,
                background_path=str(self.bg_path),
                logo_path=None,
                collection_title="Consistency Check",
                track_titles=tracks,
                template="Cinematic",
                playlist_position="Left",
                playlist_columns=2,
                playlist_col_spacing=45,
                out_dir=tmp_b,
                indicator_mode="highlight",
                active_track_index=0,
                preview_only_first_overlay=False,
            )
            with Image.open(base_prev) as img_a, Image.open(base_exp) as img_b:
                self.assertEqual(img_a.size, img_b.size)

            with Image.open(ov_prev[0]) as img_a, Image.open(ov_exp[0]) as img_b:
                self.assertEqual(img_a.size, img_b.size)
                # Overlay pixels for track 0 must be 100% identical between preview and export
                self.assertEqual(img_a.tobytes(), img_b.tobytes(), "Preview overlay and Export overlay must be pixel-identical")

    # ------------------------------------------------------------------
    # 9. Save/load and template round-trip behaviour
    # ------------------------------------------------------------------
    def test_save_load_and_template_roundtrip_all_settings(self):
        """Project and template persistence round-trip preserves all layout controls (cols, gap, max chars)."""
        project_data = {
            "name": "Layout Persistence Test",
            "collection_title": "Divine Peace",
            "template": "Two-column",
            "playlist_position": "Center",
            "playlist_columns": 3,
            "playlist_col_spacing": 85,
            "track_max_chars": 90,
            "track_wrap_text": True,
            "playlist_width_ratio": 0.70,
            "playlist_row_spacing": 1.95,
            "highlight_style": "Accent Bar",
            "tracks": [{"title": "Track 01", "path": "test.mp3", "duration": 120.0}],
        }
        # 1. Project Save & Load
        proj_file = self.tmp / "test_proj.json"
        save_project_atomic(project_data, proj_file)
        loaded_proj = json.loads(proj_file.read_text(encoding="utf-8"))

        self.assertEqual(loaded_proj["playlist_columns"], 3)
        self.assertEqual(loaded_proj["playlist_col_spacing"], 85)
        self.assertEqual(loaded_proj["track_max_chars"], 90)
        self.assertTrue(loaded_proj["track_wrap_text"])
        self.assertEqual(loaded_proj["playlist_position"], "Center")

        # 2. Template Extract & Save
        tmpl_data = extract_template(loaded_proj, template_name="Custom 3Col Template")
        tmpl_file = self.tmp / "test_tmpl.json"
        save_template_atomic(tmpl_data, tmpl_file)
        loaded_tmpl = load_template(tmpl_file)

        self.assertEqual(loaded_tmpl["playlist_columns"], 3)
        self.assertEqual(loaded_tmpl["playlist_col_spacing"], 85)
        self.assertEqual(loaded_tmpl["track_max_chars"], 90)

        # 3. Apply Template to Fresh Project
        fresh_project = {
            "name": "New Project",
            "tracks": [{"title": "New Track", "path": "new.mp3", "duration": 180.0}],
        }
        applied = apply_template_to_project(fresh_project, loaded_tmpl)
        self.assertEqual(applied["playlist_columns"], 3)
        self.assertEqual(applied["playlist_col_spacing"], 85)
        self.assertEqual(applied["track_max_chars"], 90)
        self.assertEqual(len(applied["tracks"]), 1)


if __name__ == "__main__":
    unittest.main()
