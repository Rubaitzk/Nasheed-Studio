"""
Timeline & Duration synchronization regression tests (Task E).

Required tests per brief:
- Contiguous track intervals.
- Correct cumulative start times.
- Reordered tracks producing the correct timeline.
- Invalid, zero, missing, or unreadable durations.
- Title edits not changing audio timing.
- Saved/reopened projects preserving the correct order and timeline inputs.
"""

import json
import unittest
from src.services.timeline import build_timeline


class TimelineTests(unittest.TestCase):

    def test_entries_are_contiguous(self):
        """All track intervals must be strictly contiguous."""
        tracks = [
            {"title": "Track 1", "path": "t1.mp3", "duration": 5.0},
            {"title": "Track 2", "path": "t2.mp3", "duration": 7.5},
            {"title": "Track 3", "path": "t3.mp3", "duration": 2.0},
        ]
        result = build_timeline(tracks)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].start, 0.0)
        self.assertEqual(result[0].end, 5.0)
        self.assertEqual(result[1].start, 5.0)
        self.assertEqual(result[1].end, 12.5)
        self.assertEqual(result[2].start, 12.5)
        self.assertEqual(result[2].end, 14.5)

    def test_correct_cumulative_start_times(self):
        """Start times must equal the sum of durations of all preceding tracks."""
        tracks = [
            {"title": "Alpha", "path": "a.wav", "duration": 10.2},
            {"title": "Beta", "path": "b.wav", "duration": 15.3},
            {"title": "Gamma", "path": "c.wav", "duration": 4.5},
        ]
        entries = build_timeline(tracks)
        self.assertAlmostEqual(entries[0].start, 0.0)
        self.assertAlmostEqual(entries[1].start, 10.2)
        self.assertAlmostEqual(entries[2].start, 25.5)
        self.assertAlmostEqual(entries[2].end, 30.0)

    def test_reordered_tracks_produce_correct_timeline(self):
        """Reordering tracks changes timeline intervals based on new order."""
        t1 = {"title": "First", "path": "1.mp3", "duration": 10.0}
        t2 = {"title": "Second", "path": "2.mp3", "duration": 20.0}

        order_a = build_timeline([t1, t2])
        self.assertEqual(order_a[0].title, "First")
        self.assertEqual((order_a[0].start, order_a[0].end), (0.0, 10.0))
        self.assertEqual(order_a[1].title, "Second")
        self.assertEqual((order_a[1].start, order_a[1].end), (10.0, 30.0))

        # Swap order
        order_b = build_timeline([t2, t1])
        self.assertEqual(order_b[0].title, "Second")
        self.assertEqual((order_b[0].start, order_b[0].end), (0.0, 20.0))
        self.assertEqual(order_b[1].title, "First")
        self.assertEqual((order_b[1].start, order_b[1].end), (20.0, 30.0))

    def test_rejects_invalid_zero_missing_negative_durations(self):
        """Zero, missing, negative, or unreadable duration values must be rejected."""
        # Zero duration
        with self.assertRaises(ValueError):
            build_timeline([{"title": "Zero", "path": "a.mp3", "duration": 0}])

        # Negative duration
        with self.assertRaises(ValueError):
            build_timeline([{"title": "Negative", "path": "a.mp3", "duration": -5.0}])

        # Missing duration key
        with self.assertRaises(ValueError):
            build_timeline([{"title": "Missing", "path": "a.mp3"}])

        # None duration
        with self.assertRaises(ValueError):
            build_timeline([{"title": "None", "path": "a.mp3", "duration": None}])

        # Unreadable string duration
        with self.assertRaises(ValueError):
            build_timeline([{"title": "BadStr", "path": "a.mp3", "duration": "not_a_number"}])

    def test_title_edits_do_not_change_audio_timing(self):
        """Renaming a track changes only the title, leaving timing identical."""
        orig = [{"title": "Old Title", "path": "track.mp3", "duration": 12.0}]
        edited = [{"title": "New Clean Nasheed Title", "path": "track.mp3", "duration": 12.0}]

        entry_orig = build_timeline(orig)[0]
        entry_edited = build_timeline(edited)[0]

        self.assertEqual((entry_orig.start, entry_orig.end), (entry_edited.start, entry_edited.end))
        self.assertEqual(entry_orig.duration, entry_edited.duration)
        self.assertEqual(entry_edited.title, "New Clean Nasheed Title")

    def test_saved_reopened_project_preserves_order_and_timeline(self):
        """Simulating project JSON serialization/deserialization preserves exact timeline order."""
        project_dict = {
            "version": 1,
            "tracks": [
                {"title": "Track 01", "path": "first.mp3", "duration": 35.0},
                {"title": "Track 02", "path": "second.mp3", "duration": 45.5},
                {"title": "Track 03", "path": "third.mp3", "duration": 20.0},
            ]
        }
        # Serialize to JSON and reload
        loaded_dict = json.loads(json.dumps(project_dict))
        entries = build_timeline(loaded_dict["tracks"])

        self.assertEqual([e.title for e in entries], ["Track 01", "Track 02", "Track 03"])
        self.assertEqual([(e.start, e.end) for e in entries], [(0.0, 35.0), (35.0, 80.5), (80.5, 100.5)])


if __name__ == "__main__":
    unittest.main()
