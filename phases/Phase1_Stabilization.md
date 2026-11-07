# Phase 1 & 1.5 Stabilization Report: Demo Bugs A, B, C & UX Hardening

## Executive Summary
Phase 1 and Phase 1.5 established the fundamental stability, process lifecycle safety, audio synchronization, and UI responsiveness of Nasheed Studio. All three critical demo bugs (Bug C: detached background encoding processes; Bug A: long filename layout distortion; Bug B: audio timeline drift and validation) were eliminated, followed by title editing freeze resolution, dirty-state project tracking, and recent project history.

---

## 1. Core Issues Resolved

### Bug C — Detached Background Encoding Subprocesses & Cancellation
- **Root Cause**: `render_service.py` originally executed `subprocess.run()` inside an unmanaged `QThread`. When users cancelled renders or closed the application window, child `ffmpeg.exe` processes remained orphaned, continuing CPU/GPU encoding indefinitely in the background and locking temporary files.
- **Solution**:
  - Implemented `ExportJob` with Windows Job Object integration (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`). Any termination of the Python process tree guarantees immediate kernel-level termination of child FFmpeg processes.
  - Added interactive Cancel button with immediate cleanup of intermediate workspace directories and partial output files.
  - Integrated `MainWindow.closeEvent` confirmation dialog: warns the user if an export is actively running, safely terminating the subprocess tree before closing.
  - Added strict duplicate export guards preventing concurrent render collisions.

### Bug A — Long Filename Layout Distortion
- **Root Cause**: UI labels for background and logo assets in `src/ui/main_window.py` were unconstrained `QLabel` widgets displaying raw file paths. Long filenames caused horizontal layout distortion and pushed Inspector controls off-screen.
- **Solution**:
  - Implemented fixed maximum width constraints and `QFontMetrics.elidedText()` truncation (e.g. `very_long_path...bg.jpg`).
  - Added full path inspection tooltips on hover for complete transparency.

### Bug B — Audio Duration Validation & Timeline Drift
- **Root Cause**: Audio files with invalid or unreadable headers, 0-second durations, or corrupted metadata caused timeline desynchronization and downstream FFmpeg concatenation failures.
- **Solution**:
  - Added strict `ffprobe` duration extraction and validation in `media_probe.py`.
  - Enforced duration checks rejecting missing, empty, or negative durations before playlist queuing.

### Phase 1.5 — Title Editing Freeze & State Management
- **Root Cause**: Immediate keystroke preview rerendering during title editing caused UI freezing and thread contention.
- **Solution**:
  - Added explicit Apply workflow with Enter key commitment and Escape key rollback.
  - Added a 1.5-second debounce timer preventing excessive compositor re-rendering while typing.
  - Introduced dirty-state change tracking (`*` unsaved indicator in window title).
  - Added Recent Projects menu (`File → Open Recent`) with durable persistence in user configuration.

---

## 2. Key Architecture Additions
- `src/services/export_job.py`: Managed export lifecycle, Win32 Job Object binding, and thread cleanup.
- `src/services/media_probe.py`: Robust audio/video stream probing and duration extraction.
- `src/services/render_service.py`: Decoupled project validation and FFmpeg command generation (`build_render_command`).
- `tests/test_export_job.py`, `tests/test_duplicate.py`, `tests/test_layout.py`, `tests/test_dirty_state.py`, `tests/test_recent_projects.py`: Comprehensive regression suites.
