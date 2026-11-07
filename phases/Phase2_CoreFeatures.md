# Phase 2 Implementation Report: Timeline Sync, Custom Cursors, 4 Indicator Modes, and Title UX

## Executive Summary
Phase 2 implemented precise playlist audio duration synchronization, multi-track cumulative timeline calculation, custom SVG and raster cursor rendering with dynamic scaling, track highlight overlays, 4 active track indicator modes, and audio format normalization prior to concatenation.

---

## 1. Features & Architectural Components

### Cumulative Audio Timeline Engine (`timeline.py`)
- Calculates exact cumulative timestamp offsets across all tracks:
  $$\text{start\_time}_{k} = \sum_{i=0}^{k-1} \text{duration}_i, \quad \text{end\_time}_k = \text{start\_time}_k + \text{duration}_k$$
- Validates audio durations, strictly rejecting 0-second or negative duration tracks.
- Guarantees strict preservation of audio timing regardless of playlist title edits or track reordering.

### Custom Cursor Loader & Dynamic Scaler
- Full support for monochrome/colored vector SVGs via `QSvgRenderer`, rendering razor-sharp cursors at arbitrary pixel resolutions.
- Raster cursor support (`.png`, `.jpg`, `.webp`) with smooth bilinear/bicubic resampling.
- Dynamic size adjustment from 16px to 96px with live preview feedback.

### 4 Active Track Indicator Modes
Compositor and rendering pipeline support four distinct indicator presentation styles:
1. `both`: Simultaneous custom cursor pointer and row highlight box.
2. `cursor_only`: Cursor pointer positioned beside active track title without background highlight.
3. `highlight_only`: Bounding highlight box around active track without cursor pointer.
4. `neither`: Clean typography presentation without cursor or highlight overlays.

### Multi-Input Audio Normalization
- Problem: Audio tracks with differing sample rates (e.g. 48 kHz vs 44.1 kHz) or channel topologies (mono vs stereo) previously caused FFmpeg `concat` filter crashes.
- Solution: Pre-filters all audio inputs with `aformat=sample_rates=44100:channel_layouts=stereo` prior to concatenation, guaranteeing seamless playback across mixed-format playlists.

### Title UX & Draft Preservation
- Added explicit Apply button, Enter key apply shortcut, and Escape key cancel filter.
- Implemented single-shot 1.5-second debounce timer preventing preview render contention.
- Guaranteed zero draft loss: auto-commits pending edits before saving projects or starting renders.

---

## 2. Regression Coverage
- `tests/test_timeline.py`: Cumulative timestamps, contiguous intervals, and persistence.
- `tests/test_indicators.py`: SVG rendering, PNG loading/resizing, and 4 indicator modes in compositor output.
- `tests/test_phase2_render.py`: FFmpeg filtergraph construction across all indicator modes and audio normalization.
- `tests/test_title_responsiveness.py`: Explicit Apply, Enter key, Escape revert, 1.5s timeout, and draft serialization safety.
