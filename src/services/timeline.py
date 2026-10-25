"""Pure timeline calculations shared by preview and rendering."""
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TimelineEntry:
    index: int
    title: str
    path: str
    duration: float
    start: float
    end: float


def build_timeline(tracks: Iterable[dict], intro_duration: float = 0.0) -> list[TimelineEntry]:
    """Build contiguous track intervals from tracks with known durations, offset by optional intro."""
    entries: list[TimelineEntry] = []
    cursor = max(0.0, float(intro_duration or 0.0))
    for index, track in enumerate(tracks):
        duration = float(track.get("duration", 0) or 0)
        if duration <= 0:
            raise ValueError(f"Track {index + 1} has no valid duration")
        start = cursor
        cursor += duration
        entries.append(TimelineEntry(index, str(track.get("title") or f"Track {index + 1}"), str(track["path"]), duration, start, cursor))
    return entries
