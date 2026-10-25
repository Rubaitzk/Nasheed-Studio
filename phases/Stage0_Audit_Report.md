# Stage 0 Comprehensive Audit Report: Post-Phase 3 Stabilization

**Date:** 2026-10-25  
**Baseline Git Commit:** `2e163cb` (Branch: `main`)  
**Baseline Test Suite:** 90 passing automated tests in 14.52s (100% pass rate)

---

## 1. File Lifecycle Matrix
Every file and directory created or touched during the application lifecycle:

| Operation | Files / Directories Created | Location | Cleanup / Persistence Lifecycle |
|---|---|---|---|
| **Save Project** | `<name>.json` | Path chosen by user (default suggested: `~/nasheed_project.json`) | **Persistent**. Written via non-atomic `Path(path).write_text(payload)`. Updates `HKEY_CURRENT_USER\Software\NasheedStudio\NasheedStudio\recent_projects`. |
| **Open Project** | *None* | Read-only access from target `.json` | Updates `recent_projects` in Windows Registry / QSettings. |
| **Preview Update** | `composition.png`, `cursor_000.png`, `preview.png` | `%TEMP%\nasheed_prev_<random>\` or `%TEMP%\nasheed_intro_prev_<random>\` | **Temporary**. Managed by `tempfile.TemporaryDirectory()`; automatically unlinked upon context exit. |
| **Export Start** | Intermediate folder: `.{out_path.stem}_render_work\` containing `composition.png`, `cursor_000.png`...`cursor_N.png`, and `intro_card.png` | **`out_path.parent` (directly in user's video folder beside export)** | **Temporary during render**. Created by `build_render_command`. |
| **Export Complete** | Final video: `<out_path>` (MP4) | `out_path` | **Persistent**. Intermediate `.{stem}_render_work\` directory is removed via `shutil.rmtree()`. |
| **Export Cancelled** | Partial video: `<out_path>` | `out_path` | `ExportJob._finish` unlinks `self._output_path` and runs `shutil.rmtree()` on `work_dir`. **Note: If a pre-existing video file had that name, it is permanently deleted!** |
| **Export Failed** | Partial video: `<out_path>` | `out_path` | Same as Cancel: unlinks `self._output_path` and deletes `work_dir`. **Overwrites and deletes any pre-existing video.** |
| **App Close (Clean)** | *None* | N/A | No files created. |
| **App Close (Dirty)** | `<name>.json` (if user chooses "Save") | User-chosen path | Triggers `save_project()` / `save_project_as()`. |

---

## 2. Unexplained File Beside Exported Videos
- **Exact Name**: `.{out_path.stem}_render_work` (e.g., `.nasheed_collection_render_work` or `.my_video_render_work`).
- **Exact Code Location**: `src/ui/main_window.py:1290`:
  ```python
  out_path = Path(project["output_path"]).expanduser().resolve()
  work_dir = out_path.parent / f".{out_path.stem}_render_work"
  ```
- **Purpose**: It is the intermediate working directory used by `build_render_command` to store intermediate composited image frames before feeding them as inputs to FFmpeg:
  1. `composition.png`: The full-resolution base background canvas with layout, collection title, playlist track titles, logo, and website watermark.
  2. `cursor_000.png`, `cursor_001.png`, ...: The transparent overlay images for each playlist track index containing the active track cursor indicator and highlight box.
  3. `intro_card.png`: The standalone intro title card image (when intro is enabled).
- **Why It Appears Beside Exported Videos**:
  `work_dir` is hardcoded to be created in the user's export folder (`out_path.parent`) right beside the target video. Because Windows Explorer does not hide directories prefixed with a dot unless the OS `FILE_ATTRIBUTE_HIDDEN` flag is set, Windows users see this folder sitting directly next to their MP4. Furthermore, if an export is currently running, if FFmpeg or Python is interrupted/killed, or if Windows file locks delay `shutil.rmtree()`, this folder and its `.png` files remain permanently visible in the user's personal video folder.

---

## 3. Window Close Prompt & Save Target
- **Why It Prompts**:
  In `MainWindow.closeEvent()` (`src/ui/main_window.py:1366`), `self.has_unsaved_changes()` is evaluated.
  `has_unsaved_changes()` returns `True` whenever:
  1. `self._is_dirty` is True (user typed, changed dropdown, reordered tracks, etc.), OR
  2. An unapplied title draft exists, OR
  3. For a project with an existing `project_path`: current UI state differs from `_last_saved_snapshot`, OR
  4. For a new/unsaved project (`not self.project_path`): any non-default state is present (i.e. tracks loaded, background selected, logo selected, collection title modified, website text entered, SFX enabled, intro enabled).
  Therefore, if a user imported any media or adjusted any setting and attempts to close the window, `closeEvent()` intercepts the close and shows `QMessageBox.warning("Unsaved Changes", "Do you want to save changes before closing?", Save | Discard | Cancel)`.
- **Where the Resulting JSON is Written**:
  When the user selects **Save**:
  `self.save_project()` is invoked:
  - If the project was already saved or loaded from a file (`self.project_path` is non-empty): it writes directly to `self.project_path` (e.g. `C:\Users\<user>\Documents\my_project.json`).
  - If it is a new project (`self.project_path` is empty): it calls `self.save_project_as()`, which displays `QFileDialog.getSaveFileName` with initial path suggested as `str(Path.home() / "nasheed_project.json")`. The file is written to wherever the user chooses in that dialog.

---

## 4. Nature of the Project JSON File
- **Status**: The JSON file is the **actual, primary project format** of Nasheed Studio.
- **Not an Auxiliary or Autosave File**: It is NOT an auxiliary metadata file or a background autosave. It stores the complete editable state:
  `version`, `collection_title`, `background` (path), `logo` (path), `logo_position`, `tracks` (list of dicts with `title`, `path`, `duration`), `template`, `resolution`, `indicator_mode`, `cursor_path`, `cursor_size`, `title_font_family`, `title_font_style`, `title_font_size`, `track_font_family`, `track_font_style`, `track_font_size`, `website_text`, `website_position`, `website_font_size`, `transition_sfx_enabled`, `transition_sfx_path`, `transition_sfx_volume`, `intro_enabled`, `intro_duration`, `intro_animation`, and `output_path`.
- Currently, there is no separate autosave file or automatic background recovery file.

---

## 5. Export Overwrite Behavior & Data Loss Hazards
- **Silent Overwrites**:
  1. In `src/ui/main_window.py:render_video()`, the code does **not** check `out_path.exists()`.
  2. In `src/services/render_service.py:145`, the FFmpeg command is hardcoded with `-y`:
     ```python
     command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", ...]
     ```
     `-y` forces FFmpeg to silently overwrite the target output file without user prompting.
- **Destructive Deletion on Cancel/Failure**:
  In `src/services/export_job.py:341` and `348`:
  ```python
  elif terminal_state == STATE_CANCELLED:
      if self._output_path.exists():
          self._output_path.unlink(missing_ok=True)
  else:  # FAILED
      if self._output_path.exists():
          self._output_path.unlink(missing_ok=True)
  ```
  If the user exports to a filename that already existed, FFmpeg truncates the file immediately at render start. If the user then cancels or if FFmpeg fails, `ExportJob` deletes `self._output_path`. **The user's original pre-existing video is permanently destroyed.**
- **Missing Protection**: There is no confirmation dialog (Overwrite / Choose Another Name / Cancel) and no atomic staging (e.g. rendering to a temporary file like `.{stem}.part.mp4` and renaming only after FFmpeg exits with code 0).

---

## 6. Asset References & Portability
- **Storage**: All assets (`background`, `logo`, `cursor_path`, `transition_sfx_path`, and `tracks[i]['path']`) are stored as **absolute filesystem paths** (e.g., `D:\Audio\Nasheed01.mp3`).
- **Vulnerability to Moved Assets**:
  - `MainWindow._load_project_file()` loads paths without verifying existence.
  - `validate_project()` strictly requires all asset files to exist on disk:
    ```python
    for track in tracks:
        if not Path(track["path"]).is_file():
            raise FileNotFoundError(f"Audio file not found: {track['path']}")
    ```
  - If any asset is moved, renamed, deleted, or if the project file is opened on another machine, `validate_project()` raises `FileNotFoundError` and export is blocked.
  - There is currently no missing-asset indicator, no relinking dialog, and no "Managed Mode" to copy assets into a project bundle.

---

## 7. UI Complexity & Clutter Analysis
- **Right Panel Scroll Overload**: The right panel stacks 7 separate `QGroupBox` containers inside a scroll area (`VIDEO DESIGN`, `TYPOGRAPHY & FONTS`, `WEBSITE WATERMARK`, `INTRO PRESENTATION`, `TRANSITION SOUND EFFECT`, `EXPORT`, `RENDER`). Users must scroll repeatedly to access basic controls.
- **Scattered Domain Logic**:
  - Audio tracks are managed in the left panel, but transition sound effects are buried in the right panel.
  - Video design, typography, and watermark are split across 3 distinct boxes despite all governing the visual layout.
  - Output path is in an `EXPORT` box, while Render and Cancel buttons are in a separate `RENDER` box.
- **Proposed Unified Organization (Stage 2)**:
  1. **Project & Workspace Header**: Workspace selector, Project name, Save/Save As/Template actions, and status.
  2. **Playlist & Audio**: Collection title, audio tracks management, track reordering, and transition SFX toggle/volume.
  3. **Visual Design & Typography**: Layout template, Resolution, Typography (Title & Tracks font/size), Website watermark & logo positioning, and cursor/indicator modes (with collapsible advanced settings).
  4. **Intro Sequence**: Enable toggle, duration, and animation style.
  5. **Composition Preview**: Interactive visual preview with timeline scrubber.
  6. **Export & Render**: Output filename, collision protection, render resource profile (Background / Balanced / Max Speed), progress, and Cancel.

---

## 8. FFmpeg Configuration & CPU Resource Consumption
- **Command Construction**:
  `src/services/render_service.py` sets:
  `-c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k -movflags +faststart -shortest`
- **Thread Settings**:
  - `-threads` is **not set** (unconstrained). FFmpeg uses all available CPU logical cores.
  - `-filter_threads` is **not set**.
- **Process Priority**:
  - `subprocess.Popen` in `export_job.py` spawns `ffmpeg.exe` at `NORMAL_PRIORITY_CLASS`.
  - On multi-core systems, FFmpeg consumes 85–100% CPU during video encoding, causing Windows desktop sluggishness and UI lag.
- **CPU Bottlenecks**:
  1. Frame-by-frame zoom filter evaluation: `scale=w='iw*(1+0.06*t/...)':h=...:eval=frame`.
  2. Overlay filter cascade: Chained per-track overlay filters `[v0][1:v]overlay...[v1][2:v]overlay...` execute software pixel blending across every frame.
  3. `libx264` software encoding: Consumes the vast majority of CPU cycles.

---

## 9. Test Coverage Inventory & Missing Test Cases
- **Existing Coverage (90 Passing Tests)**:
  - Process lifecycle and Job Object termination (`test_export_job.py`, `test_duplicate.py`)
  - Dirty state tracking and safe closing (`test_dirty_state.py`, `test_close_confirmation.py`)
  - Timeline arithmetic and audio synchronization (`test_timeline.py`)
  - Title editing responsiveness and auto-apply timer (`test_title_responsiveness.py`)
  - SVG/PNG cursor rendering and modes (`test_indicators.py`)
  - Typography discovery, 4-corner watermark, overlap avoidance (`test_typography_website.py`)
  - Intro card generation, animation syntax, transition SFX mixing (`test_intro_sfx.py`)
  - Panel layout constraints and list widget accessibility contrast (`test_layout.py`, `test_selection.py`)
- **Missing Test Coverage (Required for Stabilization)**:
  1. **Export Destination Collision & Overwrite Safety**:
     - Handling pre-existing destination files (Overwrite / Rename / Cancel options).
     - Preservation of pre-existing video when a new render fails or is cancelled.
     - Atomic publishing: writing to a `.part.mp4` staging file and renaming only upon FFmpeg success.
  2. **Work Directory Isolation**:
     - Ensuring `work_dir` is placed in an isolated temporary/cache directory rather than the user's export folder.
     - Collision safety for concurrent/sequential jobs targeting different videos.
  3. **Atomic Project Persistence**:
     - Writing to a `.tmp` file and replacing target to prevent project corruption during power loss/disk errors.
  4. **Workspace & Asset Management**:
     - Relinking missing assets when original files are moved.
     - Managed mode (copying assets into project folder).
     - Independent template save/load operations vs project save/load.
  5. **Configurable Render Resource Usage**:
     - Verification of thread constraints (`-threads`, `-filter_threads`) and process priority (`BELOW_NORMAL_PRIORITY_CLASS`, `IDLE_PRIORITY_CLASS`).
     - Performance benchmarks comparing Background-friendly, Balanced, and Maximum-speed modes.
  6. **Interactive Visual Preview**:
     - Timeline scrubber time-seeking and intro-to-track visual transitions.
