# Phase 1.5 Stabilization Report: Responsiveness and Project Management

Phase 1.5 resolved the playlist-title editing freeze, implemented full project dirty-state tracking with unsaved-changes protection, and added persistent Recent Projects management with automatic menu deduplication and missing-file handling.

All changes were verified against 41 automated regression tests and committed to local Git branch `main` (`331cfa1`).

---

## 1. Files Changed

- **`src/ui/main_window.py`**:
  - Implemented single-shot debounced preview generation (`_preview_timer`, 300 ms) preventing synchronous image compositing on every keystroke.
  - Implemented project dirty tracking (`_is_dirty`, `_last_saved_snapshot`, `_loading_project`).
  - Added unsaved-changes guard dialogs to `new_project()`, `open_project()`, and `open_recent_project()`.
  - Added persistent Recent Projects submenu under `Project -> Open recent` using `QSettings("NasheedStudio", "NasheedStudio")`.
  - Implemented graceful handling of missing recent files with user warnings and automatic removal from history.
- **`tests/test_title_responsiveness.py` (New)**:
  - Regression suite verifying debounced preview updates during rapid typing, clearing title completely without crashing, typing replacement text, repeated backspace/typing cycles, and pasting long text strings (300+ chars).
- **`tests/test_dirty_state.py` (New)**:
  - Regression suite verifying all 6 dirty-state scenarios (edit -> save -> new project, edit -> save -> edit -> new project warning, modify unsaved new project warning, failed save preserves dirty state, open saved project without edits, open saved project and modify).
- **`tests/test_recent_projects.py` (New)**:
  - Regression suite verifying save-to-recent insertion, deduplication and MRU reordering (capped at 10), missing project detection and removal, unsaved changes guard when opening recent, and clearing recent project list.

---

## 2. Root Cause Analysis & Fixes

### Task A — Playlist Title Editing Freeze (Windows "Not Responding")
- **Root Cause**:
  `collection_title.textChanged` was directly wired to `_refresh_preview()`. Every keystroke, deletion, or backspace synchronously invoked `create_composition()`, Pillow image compositing, font rendering, and temporary disk I/O on the main Qt GUI thread. Rapid typing flooded the event loop, freezing the application.
- **Fix Applied**:
  Replaced direct connection with single-shot timer debouncing (`_preview_timer` with `_schedule_preview(300)`). Keystrokes reset the timer; preview compositing only fires once typing ceases. Added `_flush_preview()` on `editingFinished`.

### Task B — Project Save & Dirty-State Management
- **Root Cause**:
  The application lacked dirty-state tracking. Users could accidentally discard edits by opening another project or clicking New Project without warning. Furthermore, failed save attempts had no transactional integrity.
- **Fix Applied**:
  Added boolean `_is_dirty` and deep snapshot tracking `_last_saved_snapshot`. Guarded state modifications with `_mark_dirty()`, ignored during project loading via `_loading_project`. `has_unsaved_changes()` evaluates dirty state against the initial defaults or the last saved snapshot. All destructive project transitions (`new_project`, `open_project`, `open_recent_project`) now prompt the user with a confirmation dialog.

### Task C — Recent Projects Menu UX
- **Root Cause**:
  No recent projects history existed, requiring users to repeatedly navigate the file dialog.
- **Fix Applied**:
  Added `Open recent` submenu under `Project`. Serialized recent paths into `QSettings`. Implemented MRU list capped at 10 items, deduplication, tooltip previews, "Clear recent projects" action, and automatic verification that project files exist before opening.

---

## 3. Test Verification
All 41 tests passed:
- `tests/test_title_responsiveness.py` (5 passed)
- `tests/test_dirty_state.py` (6 passed)
- `tests/test_recent_projects.py` (5 passed)
- `tests/test_export_job.py` (6 passed)
- `tests/test_duplicate.py` (6 passed)
- `tests/test_layout.py` (5 passed)
- `tests/test_selection.py` (8 passed)
