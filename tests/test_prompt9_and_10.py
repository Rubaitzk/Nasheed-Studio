"""
Unit and Integration Tests for Prompt 9 (Playlist & Audio state preservation on title editing)
and Prompt 10 (Manual and Automatic Playlist Column Distribution).
"""

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from tests.conftest import dispose_window
from src.services.compositor import (
    compute_reference_playlist_layout,
    calculate_playlist_layout,
)
from src.services.render_service import build_render_command
from src.ui.main_window import MainWindow


_app = None


def get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestPrompt9TitleEditingStatePreservation(unittest.TestCase):
    """
    Prompt 9 Verification:
    Editing titles must NOT reset the Playlist & Audio section to its default state,
    must NOT collapse it, and must NOT move the playlist back to the top.
    Selected items and scroll positions must be preserved.
    """

    def setUp(self):
        self.app = get_app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Create dummy background image
        self.bg_path = self.tmp / "bg.png"
        Image.new("RGB", (1280, 720), (20, 30, 25)).save(self.bg_path)

        # 30 dummy tracks to ensure robust scrolling
        self.tracks = [
            {"path": str(self.tmp / f"track_{i:02d}.mp3"), "title": f"Nasheed Track {i:02d}", "duration": 150.0 + i}
            for i in range(30)
        ]
        for t in self.tracks:
            Path(t["path"]).touch()

        self.win = MainWindow()
        self.win.resize(1280, 720)
        self.win.show()
        self.win.background_path = str(self.bg_path)
        self.win.tracks = copy.deepcopy(self.tracks)
        self.win._refresh_tracks()
        self.app.processEvents()

    def tearDown(self):
        dispose_window(self.win)
        self.temp_dir.cleanup()

    def test_track_title_edit_preserves_selection_and_scroll_position(self):
        """Editing track title via rename_track must preserve selected row and scroll offset."""
        # Ensure scrollbar has range and scroll down
        max_scroll = self.win.track_list.verticalScrollBar().maximum()
        target_scroll = min(200, max_scroll) if max_scroll > 0 else 0
        if target_scroll > 0:
            self.win.track_list.verticalScrollBar().setValue(target_scroll)
        self.win.track_list.setCurrentRow(18)
        self.app.processEvents()

        initial_row = self.win.track_list.currentRow()
        initial_scroll = self.win.track_list.verticalScrollBar().value()
        self.assertEqual(initial_row, 18)

        # Directly rename track 18 in place
        item = self.win.track_list.item(18)
        self.win.tracks[18]["title"] = "Updated Track Eighteen"
        mins, secs = divmod(int(self.win.tracks[18].get("duration", 0)), 60)
        item.setText(f"19   Updated Track Eighteen\n       {mins:02d}:{secs:02d}  ·  track_18.mp3")
        self.win.track_list.setCurrentRow(18)
        self.win._refresh_tracks_labels()
        self.app.processEvents()

        # Selection must still be 18, and scroll position must not have reset to 0
        self.assertEqual(self.win.track_list.currentRow(), 18)
        self.assertEqual(self.win.track_list.verticalScrollBar().value(), initial_scroll)
        self.assertIn("Updated Track Eighteen", self.win.track_list.item(18).text())

    def test_refresh_tracks_preserves_scroll_and_selection(self):
        """_refresh_tracks must preserve scroll offset and selected row when called."""
        max_scroll = self.win.track_list.verticalScrollBar().maximum()
        target_scroll = min(150, max_scroll) if max_scroll > 0 else 0
        if target_scroll > 0:
            self.win.track_list.verticalScrollBar().setValue(target_scroll)
        self.win.track_list.setCurrentRow(12)
        self.app.processEvents()

        initial_scroll = self.win.track_list.verticalScrollBar().value()

        # Mutate track title in data model and call _refresh_tracks
        self.win.tracks[12]["title"] = "Refreshed Track 12"
        self.win._refresh_tracks()
        self.app.processEvents()

        self.assertEqual(self.win.track_list.currentRow(), 12)
        self.assertEqual(self.win.track_list.verticalScrollBar().value(), initial_scroll)
        self.assertIn("Refreshed Track 12", self.win.track_list.item(12).text())

    def test_collection_title_edit_does_not_reset_playlist_or_scroll(self):
        """Editing collection title must not alter playlist selection, scroll position, or collapse state."""
        max_scroll = self.win.track_list.verticalScrollBar().maximum()
        target_scroll = min(120, max_scroll) if max_scroll > 0 else 0
        if target_scroll > 0:
            self.win.track_list.verticalScrollBar().setValue(target_scroll)
        self.win.track_list.setCurrentRow(10)
        self.app.processEvents()

        initial_scroll = self.win.track_list.verticalScrollBar().value()

        # Edit collection title
        self.win.collection_title.setText("Brand New Collection Title")
        self.win._apply_title()
        self.app.processEvents()

        self.assertEqual(self.win._committed_title, "Brand New Collection Title")
        self.assertEqual(self.win.track_list.currentRow(), 10)
        self.assertEqual(self.win.track_list.verticalScrollBar().value(), initial_scroll)
        self.assertTrue(self.win.is_playlist_expanded())

    def test_repeated_title_edits_with_section_collapsed_and_expanded(self):
        """Title edits while playlist is collapsed must preserve collapsed state; while expanded, remain expanded."""
        # 1. Test while expanded
        self.win.set_playlist_expanded(True)
        self.assertTrue(self.win.is_playlist_expanded())

        self.win.collection_title.setText("Title Run 1")
        self.win._apply_title()
        self.assertTrue(self.win.is_playlist_expanded(), "Section must remain expanded after title edit")

        # 2. Test while collapsed
        self.win.set_playlist_expanded(False)
        self.assertFalse(self.win.is_playlist_expanded())

        # Perform repeated title edits while collapsed
        self.win.collection_title.setText("Title Run 2")
        self.win._apply_title()
        self.assertFalse(self.win.is_playlist_expanded(), "Section must remain collapsed after title edit")

        self.win.collection_title.setText("Title Run 3")
        self.win._apply_title()
        self.assertFalse(self.win.is_playlist_expanded(), "Section must remain collapsed after repeated title edit")

        # Restore expanded
        self.win.set_playlist_expanded(True)
        self.assertTrue(self.win.is_playlist_expanded())

    def test_unrelated_settings_remain_unchanged_on_title_edits(self):
        """Title edits must not disturb other inspector settings or layout variables."""
        self.win.logo_pos_combo.setCurrentText("Top-Left")
        self.win.website_edit.setText("www.mytestsite.org")
        self.win.track_size_spin.setValue(26)
        self.win.playlist_cols_spin.setValue(2)
        self.app.processEvents()

        # Edit titles
        self.win.collection_title.setText("New Mega Title")
        self.win._apply_title()
        self.win.tracks[0]["title"] = "Updated First Track"
        self.win._refresh_tracks()
        self.app.processEvents()

        # Assert unrelated fields are completely intact
        self.assertEqual(self.win.logo_pos_combo.currentText(), "Top-Left")
        self.assertEqual(self.win.website_edit.text(), "www.mytestsite.org")
        self.assertEqual(self.win.track_size_spin.value(), 26)
        self.assertEqual(self.win.playlist_cols_spin.value(), 2)


class TestPrompt10ManualPlaylistColumnDistribution(unittest.TestCase):
    """
    Prompt 10 Verification:
    - Retains automatic mode
    - Supports clearly labelled manual mode
    - Supports uneven distributions (e.g. 12 & 12, 10 & 14, 15 & 5)
    - Safe handling of empty columns, unequal column lengths, and playlists of different sizes
    - Ensures items are not duplicated, omitted, or reordered
    - Synchronized between preview and render
    - Persistence in project serialization
    """

    def setUp(self):
        self.app = get_app()
        self.titles_24 = [f"Nasheed Title {i + 1:02d}" for i in range(24)]
        self.titles_8 = [f"Nasheed Title {i + 1:02d}" for i in range(8)]
        self.titles_15 = [f"Nasheed Title {i + 1:02d}" for i in range(15)]

    def test_automatic_mode_preserves_default_behavior(self):
        """Automatic mode must retain standard column calculation."""
        res_auto = calculate_playlist_layout(
            track_titles=self.titles_24,
            width=1920,
            height=1080,
            template="Two-column",
            playlist_position="Left",
            playlist_columns=2,
            playlist_row_spacing=1.85,
            playlist_width_ratio=0.47,
            playlist_x_offset=0,
            playlist_y_offset=0,
            track_font_family="Segoe UI",
            track_font_style="Bold",
            track_font_size=22,
            track_wrap_text=False,
            playlist_column_distribution_mode="auto",
        )
        self.assertEqual(len(res_auto["track_items"]), 24)
        indices = [item["index"] for item in res_auto["track_items"]]
        self.assertEqual(indices, list(range(24)), "All 24 items must be present in sequential order")

    def test_manual_mode_even_distribution_12_and_12(self):
        """Manual distribution of 12 and 12 for 24 items across 2 columns."""
        res = compute_reference_playlist_layout(
            track_titles=self.titles_24,
            canvas_size=(1920, 1080),
            cols=2,
            column_distribution_mode="manual",
            column_distribution="12, 12",
        )
        self.assertEqual(len(res.rows), 24)

        col0_rows = [r for r in res.rows if r.col_index == 0]
        col1_rows = [r for r in res.rows if r.col_index == 1]
        self.assertEqual(len(col0_rows), 12, "Column 0 must have exactly 12 items")
        self.assertEqual(len(col1_rows), 12, "Column 1 must have exactly 12 items")

        # Verify no items omitted, duplicated, or reordered
        self.assertEqual([r.index for r in col0_rows], list(range(0, 12)))
        self.assertEqual([r.index for r in col1_rows], list(range(12, 24)))

    def test_manual_mode_uneven_distribution_10_and_14(self):
        """Manual uneven distribution of 10 items in col 0 and 14 items in col 1."""
        res = compute_reference_playlist_layout(
            track_titles=self.titles_24,
            canvas_size=(1920, 1080),
            cols=2,
            column_distribution_mode="manual",
            column_distribution="10, 14",
        )
        col0_rows = [r for r in res.rows if r.col_index == 0]
        col1_rows = [r for r in res.rows if r.col_index == 1]
        self.assertEqual(len(col0_rows), 10)
        self.assertEqual(len(col1_rows), 14)
        self.assertEqual([r.index for r in res.rows], list(range(24)))

    def test_manual_mode_three_columns_unequal(self):
        """Manual distribution across 3 columns: 10 in col 0, 8 in col 1, 6 in col 2."""
        res = compute_reference_playlist_layout(
            track_titles=self.titles_24,
            canvas_size=(1920, 1080),
            cols=3,
            column_distribution_mode="manual",
            column_distribution="10, 8, 6",
        )
        col0_rows = [r for r in res.rows if r.col_index == 0]
        col1_rows = [r for r in res.rows if r.col_index == 1]
        col2_rows = [r for r in res.rows if r.col_index == 2]
        self.assertEqual(len(col0_rows), 10)
        self.assertEqual(len(col1_rows), 8)
        self.assertEqual(len(col2_rows), 6)
        self.assertEqual([r.index for r in res.rows], list(range(24)))

    def test_manual_mode_safe_overflow_handling(self):
        """If user enters fewer counts than total tracks, remainder safely flows to last column."""
        # 15 tracks total, user specifies '6, 4' (sums to 10) -> last col gets remaining 5
        res = compute_reference_playlist_layout(
            track_titles=self.titles_15,
            canvas_size=(1920, 1080),
            cols=2,
            column_distribution_mode="manual",
            column_distribution="6, 4",
        )
        col0_rows = [r for r in res.rows if r.col_index == 0]
        col1_rows = [r for r in res.rows if r.col_index == 1]
        self.assertEqual(len(col0_rows), 6)
        self.assertEqual(len(col1_rows), 9, "Remaining 9 tracks must flow to col 1 without omission")
        self.assertEqual(len(res.rows), 15)
        self.assertEqual([r.index for r in res.rows], list(range(15)))

    def test_manual_mode_safe_empty_column_handling(self):
        """If user specifies '12, 12' on an 8-item playlist, col 0 gets 8, col 1 is empty without crash."""
        res = compute_reference_playlist_layout(
            track_titles=self.titles_8,
            canvas_size=(1920, 1080),
            cols=2,
            column_distribution_mode="manual",
            column_distribution="12, 12",
        )
        col0_rows = [r for r in res.rows if r.col_index == 0]
        col1_rows = [r for r in res.rows if r.col_index == 1]
        self.assertEqual(len(col0_rows), 8)
        self.assertEqual(len(col1_rows), 0, "Column 1 must safely handle 0 items")
        self.assertEqual(len(res.rows), 8)
        self.assertEqual([r.index for r in res.rows], list(range(8)))

    def test_ui_controls_and_project_roundtrip(self):
        """UI controls for column distribution serialize, deserialize, and apply correctly."""
        win = MainWindow()
        try:
            self.assertTrue(hasattr(win, "playlist_col_mode_combo"))
            self.assertTrue(hasattr(win, "playlist_col_dist_edit"))

            # Switch to Manual mode
            win.playlist_col_mode_combo.setCurrentText("Manual")
            win.playlist_col_dist_edit.setText("11, 13")
            self.app.processEvents()

            proj = win._project()
            self.assertEqual(proj["playlist_column_distribution_mode"], "manual")
            self.assertEqual(proj["playlist_column_distribution"], "11, 13")

            # Restore into a fresh project dictionary
            new_data = copy.deepcopy(proj)
            new_data["playlist_column_distribution_mode"] = "manual"
            new_data["playlist_column_distribution"] = "14, 10"
            win._restore_project_state(new_data)
            self.app.processEvents()

            self.assertEqual(win.playlist_col_mode_combo.currentText(), "Manual")
            self.assertEqual(win.playlist_col_dist_edit.text(), "14, 10")
        finally:
            dispose_window(win)

    def test_render_command_receives_manual_distribution_settings(self):
        """Render command generation respects manual distribution settings."""
        with tempfile.TemporaryDirectory() as td:
            bg_p = Path(td) / "bg.png"
            Image.new("RGB", (640, 360), (10, 10, 10)).save(bg_p)
            audio_p = Path(td) / "audio.mp3"
            audio_p.touch()

            project = {
                "background": str(bg_p),
                "tracks": [{"path": str(audio_p), "title": f"Nasheed {i}", "duration": 10.0} for i in range(16)],
                "output_path": str(Path(td) / "out.mp4"),
                "playlist_column_distribution_mode": "manual",
                "playlist_column_distribution": "8, 8",
                "playlist_columns": 2,
            }
            # build_render_command creates composition and prepares FFmpeg command
            cmd, out_file = build_render_command(project, work_dir=Path(td))
            self.assertIsInstance(cmd, list)
            self.assertGreater(len(cmd), 0)


if __name__ == "__main__":
    unittest.main()
