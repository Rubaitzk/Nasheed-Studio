# Nasheed Studio — Project Status & Handover Document for ChatGPT

> **Notice for ChatGPT:** This document provides a complete, high-level and deep-dive briefing on the **Nasheed Studio** desktop application. It details the project context, exact current status, recent fixes, architecture, UI layout, visual screenshots, and next steps.

---

## 1. Project Context & Commercial Brief

- **Project Name:** Nasheed Studio
- **Platform:** Standalone Windows Desktop Application (Windows 10 / 11 64-bit)
- **Tech Stack:** Python 3.10+, PySide6 (Qt 6), FFmpeg / FFprobe (via subprocess and Windows Job Object), Pillow (PIL)
- **Primary Purpose:** Automate the creation of high-quality "nasheed collection" playlist videos (1080p Full HD, 1440p QHD, 4K UHD).
- **Core Workflow:**
  1. User selects a background image and an optional logo with position control.
  2. User imports multiple audio tracks (MP3, WAV), arranges their playback sequence, and assigns titles.
  3. The app renders a playlist overlay synchronized with the exact audio durations.
  4. An animated indicator (custom SVG/PNG cursor, moving highlight box, both, or neither) highlights the currently playing track and advances automatically as each track finishes.
  5. User customizes typography (independent title and track fonts/styles/sizes), website watermark text in any corner with opacity control, track transition sound effect (chime) with volume control, and an optional animated intro card.
  6. User previews the composition on an embedded 16:9 canvas and exports the final MP4.
- **Master Specification:** See [Nasheed_App_Agent_Context (1).md](file:///Nasheed_App_Agent_Context%20(1).md) in the project root for the approved master brief and checklist.

---

## 2. Current Implementation Status

**Current Branch:** `main`  
**Latest Commit:** `a5082cb` (*fix(acceptance): cursor/highlight refresh, website opacity slider, crisp single-layer typography, and playlist selection stability*)  
**Test Suite Status:** **142 automated tests passing in 35s (100% pass rate, 0 failures)**  
All tests run headlessly without requiring a physical display server via `pytest tests/`.

### Key Milestones Achieved:
1. **Critical Demo Bugs Fixed (Phase 1):**
   - **Bug A (Layout Distortion):** Extremely long filenames for background/logo or audio tracks no longer distort the three-panel splitters. Fixed via minimum panel widths, filename truncation with ellipsis, and tooltips displaying full paths.
   - **Bug B (Selection Contrast):** Selected audio tracks in the playlist no longer turn black with invisible text. High-contrast theme defines explicit focused, selected, hover, and unselected text/background colors.
   - **Bug C (Process Lifecycle & Zombie FFmpeg):** Export jobs now run under a Win32 **Job Object** (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`). Cancelling export, inducing failure, or closing the application terminates the entire subprocess tree instantly without orphaned FFmpeg/FFprobe processes.
2. **Core Feature Set (Phase 2 & 3):**
   - Background image & logo placement in any of the 4 corners.
   - Multi-track audio list with drag-and-drop reordering, title renaming, and duration computation.
   - SVG and PNG custom cursor support with size scaling; highlight box with color picker and opacity slider.
   - Independent typography for collection title and track items (Windows font enumeration + custom TTF/OTF support).
   - Website watermark in any corner (guaranteed not to overlap logo) with adjustable font size and opacity.
   - Audio transition chime SFX with volume slider; animated intro title card with duration setting.
   - Multi-resolution export: 1080p, 1440p, 4K UHD at 30 FPS.
3. **Data Safety & Workspace Isolation (Stage 1):**
   - Project saves (`.json` / `.nasheed`) are written atomically (write to temp file + replace) to prevent corruption.
   - Output export renders to `.{out_path.stem}.part.mp4` staging file first and renames to `<out_path>` only after FFmpeg completes with code 0. Pre-existing output videos are never deleted or truncated prematurely.
   - Render work directory is isolated in the local user cache/workspace directory (`~/.nasheed_studio/workspace/temp/`) rather than cluttering the user's export destination folder.
   - Reusable templates can be saved and applied independently of projects.
4. **UI Reorganization & Acceptance Polish (Stage 2):**
   - Clean, modern 3-column layout:
     * **Left Column:** Collection Title input (with draft state & apply debounce) + Drag-and-drop Track List + Summary badge (track count & total duration).
     * **Center Column:** Real-time 16:9 Composition Preview Canvas with interactive mode toggles (Intro preview vs Canvas preview).
     * **Right Column (Scrollable):** Grouped into Visual Design & Branding (Template/Resolution, Assets, Typography accordion, Watermark accordion, Cursor/Highlight accordion), Intro & SFX, and Export & Render.
   - Single-layer crisp text rendering (removed muddy duplicate drop-shadow artifacts).
   - Website watermark opacity slider (0% to 100%).
   - Immediate canvas preview refresh whenever cursor asset, size, highlight color, or opacity is changed.
   - Playlist item selection stability (preventing accidental deselection on drag release).

---

## 3. UI Overview & Screenshot Guide

The archive includes 11 full-fidelity UI screenshots in the `screenshots/` directory, captured directly from the live application under various window sizes and DPI scaling settings:

| Screenshot File | Description & What It Shows |
|---|---|
| `screenshot_1440x900_100scale_collapsed.png` | Standard desktop window (1440x900, 100% DPI). Shows the 3-column layout with styling accordions collapsed for high-level overview. |
| `screenshot_1440x900_100scale_expanded.png` | Standard desktop window (1440x900, 100% DPI) with Typography, Watermark, and Cursor/Highlight accordion sections expanded, displaying all sliders, font pickers, and color swatches. |
| `screenshot_1120x720_100scale_collapsed.png` | Minimum supported application size (1120x720) collapsed. Verifies layout stability on smaller laptop screens. |
| `screenshot_1120x720_100scale_expanded.png` | Minimum supported application size (1120x720) expanded with internal panel scrollbars. |
| `screenshot_1440x900_125scale_collapsed.png` | High-DPI Windows display (125% scaling) at 1440x900 collapsed. Shows crisp fonts and proper DPI metric scaling. |
| `screenshot_1440x900_125scale_expanded.png` | High-DPI Windows display (125% scaling) at 1440x900 expanded. |
| `screenshot_1120x720_125scale_collapsed.png` | High-DPI Windows display (125% scaling) at 1120x720 collapsed. |
| `screenshot_1120x720_125scale_expanded.png` | High-DPI Windows display (125% scaling) at 1120x720 expanded. |
| `screenshot_selected_track.png` | Focus on the playlist QListWidget showing active track selection with high-contrast text and selection border (verifies Bug B fix). |
| `screenshot_long_filenames.png` | Demonstrates Bug A fix: background/logo assets and audio tracks with extremely long filenames truncate gracefully with ellipsis without expanding panel widths. |
| `screenshot_running_render.png` | UI state during an active export render: displays live progress bar, percentage, status message, active Cancel button, and disabled settings to prevent state mutations while rendering. |
| `reference/image.png` | Original buyer's reference mockup showing the visual goal for the video composition overlay. |

---

## 4. Architecture & Code Map

```
nasheed_studio/
├── app.py                      # Application entry point; initializes QApplication and MainWindow
├── Nasheed Studio.spec         # PyInstaller specification for standalone Windows executable
├── requirements.txt            # Python dependencies (PySide6, Pillow, pytest)
├── packaging/
│   ├── build_exe.py            # Automated packaging script for PyInstaller
│   ├── DISTRIBUTION_README.txt # Instructions for end-user binary distribution
│   └── README.md               # Packaging developer notes
├── phases/                     # Historical audit & specification documents
│   ├── Phase1.md               # Bug A, B, C root-cause analysis and stabilization
│   ├── Phase1.5.md             # Title draft debounce, dirty state tracking
│   ├── Phase2.md               # Core playlist sync and timeline architecture
│   ├── Phase3.md               # Visual customization and safe closing
│   ├── Stage0_Audit_Report.md  # Comprehensive safety and architecture audit
│   └── Stage2_UI_Proposal.md   # Six-section UI reorganization design document
├── reference/
│   └── image.png               # Target reference image from buyer
├── screenshots/                # Updated live application UI screenshots
├── src/
│   ├── services/
│   │   ├── compositor.py       # Frame composition engine (PIL): canvas, fonts, cursors, highlights, intro cards
│   │   ├── export_job.py       # Windows Job Object export executor, subprocess manager, cancellation & cleanup
│   │   ├── export_service.py   # High-level export facade
│   │   ├── font_service.py     # System font loader and custom TTF/OTF registrar
│   │   ├── media_probe.py      # FFprobe audio/video metadata and duration extractor
│   │   ├── project_service.py  # Atomic project save/load, template manager, and schema validation
│   │   ├── render_service.py   # FFmpeg command builder, filtergraph generator (overlays, transitions, mix)
│   │   ├── timeline.py         # Track start/end timeline calculation
│   │   └── workspace_service.py# Staging directory and temporary render workspace isolation
│   └── ui/
│       ├── icons.py            # Programmatic SVG icons (play, add, remove, up, down, render, etc.)
│       ├── main_window.py      # Main UI window, 3-column splitters, 6 sections, preview canvas (~1.6k LOC)
│       └── style.py            # Complete application QSS stylesheet (dark theme, high-contrast states)
├── tests/                      # Pytest automated test suite (142 tests)
└── tools/
    └── capture_screenshots.py  # Automated script to launch app and capture UI screenshots
```

---

## 5. Next Steps & Current Focus for ChatGPT

1. **Review Final Buyer Requirements Against Delivery Checklist:**
   Review the checklist in `Nasheed_App_Agent_Context (1).md` (Section 10) to verify all items are completed.
2. **Standalone Windows Packaging Verification:**
   The client requires a standalone Windows executable where the buyer does not have Python installed. The spec file `Nasheed Studio.spec` and `packaging/build_exe.py` bundle PySide6 and FFmpeg/FFprobe binaries into `dist/Nasheed Studio/`. Ensure that relative paths to `tools/ffmpeg.exe` and `tools/ffprobe.exe` resolve cleanly whether running from source or from PyInstaller's `sys._MEIPASS` / frozen directory.
3. **Large Collection Performance & Long Renders:**
   Verify behavior with long collections (30–60+ minutes, 15+ tracks). Ensure memory usage remains flat and FFmpeg streaming does not accumulate excessive memory.
4. **Any Buyer Revisions / UI Adjustments:**
   Address any specific buyer feedback on spacing, font defaults, or layout aesthetics.
