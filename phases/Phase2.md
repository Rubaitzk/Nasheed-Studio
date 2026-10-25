# Phase 2 Implementation Report: Timeline Sync, Custom Cursors, 4 Indicator Modes, and Title UX

Phase 2 implemented the core playlist duration synchronization, multi-track timeline generation, custom SVG/PNG cursor loading with real-time resizing, moving track highlights, 4 active track indicator modes, audio normalization before concatenation, and an explicit Apply + 1.5s debounced preview workflow for collection titles.

All features were verified against 63 automated tests and committed to local Git branch `main` (`ff0ffff` and `621fce2`).

---

## 1. Files Changed

- **`src/services/timeline.py` (New)**:
  - Audio duration validation (disallows zero, missing, negative, or invalid durations).
  - Exact cumulative timeline generation (`start_time`, `end_time`, `cumulative_start`, `duration`).
  - Strict preservation of audio timing regardless of playlist title edits or reordering.
- **`src/services/cursor_loader.py` (New)**:
  - Custom cursor asset loader supporting SVG (rendered sharply via `QSvgRenderer` to arbitrary pixel sizes) and PNG/JPG/WEBP raster images (with smooth antialiased resizing).
  - Robust fallback and input validation with clear errors for missing or corrupt files.
- **`src/services/compositor.py`**:
  - Integrated 4 indicator modes: `both`, `cursor_only`, `highlight_only`, `neither`.
  - Added support for custom cursor paths and user-selected cursor pixel dimensions (16px - 96px).
  - Rendered active-track visual bounding box highlights with rounded corners and high-contrast color styling.
  - Positioned custom cursor smoothly beside active track titles with exact baseline alignment.
- **`src/services/render_service.py`**:
  - Enhanced FFmpeg filtergraph generator to synchronize video overlay intervals with calculated audio timeline track boundaries (`enable='between(t,start,end)'`).
  - Added multi-input audio normalization (`aformat=sample_rates=44100:channel_layouts=stereo`) before audio concatenation, preventing FFmpeg concat crashes when combining audio tracks with differing sample rates or channels.
  - Implemented clean video passthrough when indicator mode is set to `neither` (zero overlay inputs).
- **`src/ui/main_window.py`**:
  - Added "Active Track Indicator" UI section with Mode selector combo (`Both`, `Cursor only`, `Highlight only`, `Neither`), custom cursor upload/reset buttons, and a size spinbox (16–96 px).
  - Integrated explicit **Apply** button beside playlist title input with disabled state styling.
  - Implemented `Enter` (`returnPressed`) to apply title and `Escape` (`eventFilter`) to cancel drafts without dirtying project state.
  - Implemented single-shot 1.5-second (1500 ms) auto-apply timer.
  - Guaranteed zero draft loss: auto-commits pending edits before saving projects or starting renders.
- **`tests/test_timeline.py` (New)**:
  - 6 unit tests verifying cumulative start times, contiguous intervals, invalid duration rejection, reordering timeline updates, and saved/reopened persistence.
- **`tests/test_indicators.py` (New)**:
  - 8 unit tests verifying SVG rendering, PNG loading/resizing, corrupt file handling, and all 4 indicator modes in composition output.
- **`tests/test_phase2_render.py` (New)**:
  - 4 integration tests verifying filtergraph construction for `both`, `neither`, audio normalization filter inclusion, and custom cursor validation.
- **`tests/test_title_responsiveness.py` (Updated)**:
  - Expanded to 11 regression tests covering explicit Apply, Enter key, Escape revert, 1.5s auto-apply timeout, draft serialization safety, and unsaved changes detection.

---

## 2. Key Architecture & Fixes

1. **Audio Timeline Synchronization**:
   - `build_timeline()` calculates precise cumulative seconds: Track 1 starts at 0.0s, Track 2 at duration(Track 1), etc.
   - FFmpeg overlays use `enable='between(t,start,end)'` matching the exact audio segments.
2. **Audio Concat Normalization**:
   - Audio tracks with differing sample rates (e.g. 48 kHz vs 44.1 kHz) or channel counts (mono vs stereo) previously caused FFmpeg `concat` filter errors.
   - Solved by prepending `[i:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}]` before `concat=n=N:v=0:a=1[outa]`.
3. **Custom Cursor SVG/PNG Support**:
   - SVG vectors are rendered to QImage with `QSvgRenderer` to ensure crisp rendering at any resolution (1080p, 1440p, 4K).
   - Raster images are loaded via Pillow and scaled using `Resampling.LANCZOS`.
4. **Title Draft & Commit UX**:
   - Resolved GUI thread freezing and accidental draft loss by separating the input draft from the committed project title, backing it with an Apply button, keyboard shortcuts, a 1.5s idle timer, and auto-commit before export/save.

---

## 3. Test Verification
All 63 tests passed:
```
============================= 63 passed in 10.08s =============================
```
