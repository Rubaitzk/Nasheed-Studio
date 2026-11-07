import sys
import tempfile
import time
import wave
from pathlib import Path
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer

from src.ui.main_window import MainWindow
from tests.conftest import dispose_window

_app = None

def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app

def _create_dummy_wav(path: Path, duration_sec: float = 2.0):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"\x00" * int(44100 * 2 * 2 * duration_sec))

class TestPreviewAudioContinuous(unittest.TestCase):
    def setUp(self):
        _get_app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.audio1 = self.tmp_path / "track1.wav"
        self.audio2 = self.tmp_path / "track2.wav"
        _create_dummy_wav(self.audio1, 3.0)
        _create_dummy_wav(self.audio2, 3.0)

        self.win = MainWindow()
        self.win.tracks = [
            {"title": "Track 1", "path": str(self.audio1), "duration": 3.0},
            {"title": "Track 2", "path": str(self.audio2), "duration": 3.0},
        ]
        self.win._refresh_tracks()

    def tearDown(self):
        if hasattr(self, "win"):
            self.win._release_preview_player()
            dispose_window(self.win)
        self.temp_dir.cleanup()

    def test_continuous_playback_no_repeated_seeking(self):
        win = self.win
        win._start_preview_playback()
        player = win._preview_audio_player
        self.assertIsNotNone(player)

        set_pos_calls = []
        orig_set_pos = player.setPosition
        def hooked_set_pos(pos):
            set_pos_calls.append(pos)
            return orig_set_pos(pos)
        player.setPosition = hooked_set_pos

        # Simulate 5 consecutive playback ticks
        for _ in range(5):
            win._on_preview_timeline_tick()
            _get_app().processEvents()

        # Regular timeline ticks MUST NOT call setPosition repeatedly on playing player
        self.assertEqual(len(set_pos_calls), 0, f"Expected 0 setPosition calls during normal playback ticks, got {len(set_pos_calls)}")

        # An intentional user seek MUST invoke setPosition
        win._seek_preview(1.5)
        _get_app().processEvents()
        self.assertGreaterEqual(len(set_pos_calls), 1)
        self.assertEqual(set_pos_calls[-1], 1500)

    def test_track_transition_and_seek_to_next_track(self):
        win = self.win
        win._start_preview_playback()
        self.assertEqual(win._preview_audio_current_track_idx, 0)

        # Seek into Track 2 (at 3.5s)
        win._seek_preview(3.5)
        _get_app().processEvents()

        self.assertEqual(win._preview_audio_current_track_idx, 1)
        self.assertEqual(win._preview_active_visual_idx, 1)

    def test_no_startup_drift_during_audio_buffering(self):
        """Verify timeline holds at 0.0s while audio decoder is buffering (cur_pos_ms == 0)."""
        win = self.win
        win._start_preview_playback()
        self.assertEqual(win._preview_current_time, 0.0)

        # Simulate 3 ticks where audio player is in PlayingState but buffering at 0ms
        for _ in range(3):
            win._last_playback_tick = time.monotonic() - 0.1
            win._on_preview_timeline_tick()
            _get_app().processEvents()
            # Must remain held at start, not drift forward to 0.3s
            self.assertLess(win._preview_current_time, 0.05)

    def test_monotonic_forward_progress_no_backward_snapping(self):
        """Verify playhead never snaps backwards during continuous playback."""
        win = self.win
        win._start_preview_playback()
        win._preview_current_time = 0.50

        # If audio player reports a jittered lower position (e.g. 400ms = 0.40s)
        orig_pos = win._preview_audio_player.position
        win._preview_audio_player.position = lambda: 400

        try:
            win._on_preview_timeline_tick()
            # Must not decrease below 0.50s
            self.assertGreaterEqual(win._preview_current_time, 0.50)
        finally:
            win._preview_audio_player.position = orig_pos

    def test_end_of_media_no_restart_loop(self):
        """Verify that when a track ends (EndOfMedia), _sync_playback_state does not restart it."""
        win = self.win
        win._start_preview_playback()
        player = win._preview_audio_player

        play_calls = []
        orig_play = player.play
        player.play = lambda: play_calls.append(True)

        orig_status = player.mediaStatus
        orig_state = player.playbackState
        player.mediaStatus = lambda: QMediaPlayer.MediaStatus.EndOfMedia
        player.playbackState = lambda: QMediaPlayer.PlaybackState.StoppedState

        try:
            # Sync tick when media is at EndOfMedia
            win._sync_playback_state(win._preview_current_time, is_playing=True, is_seek=False)
            # play() MUST NOT be called to loop the finished media
            self.assertEqual(len(play_calls), 0)
        finally:
            player.play = orig_play
            player.mediaStatus = orig_status
            player.playbackState = orig_state

if __name__ == "__main__":
    unittest.main()
