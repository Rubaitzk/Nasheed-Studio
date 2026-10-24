import unittest
from src.services.timeline import build_timeline

class TimelineTests(unittest.TestCase):
    def test_entries_are_contiguous(self):
        tracks = [
            {"title": "A", "path": "a.mp3", "duration": 5},
            {"title": "B", "path": "b.mp3", "duration": 7.5},
            {"title": "C", "path": "c.mp3", "duration": 2},
        ]
        result = build_timeline(tracks)
        self.assertEqual([(x.start, x.end) for x in result], [(0, 5), (5, 12.5), (12.5, 14.5)])

    def test_rejects_invalid_duration(self):
        with self.assertRaises(ValueError):
            build_timeline([{"title": "A", "path": "a.mp3", "duration": 0}])

if __name__ == "__main__":
    unittest.main()
