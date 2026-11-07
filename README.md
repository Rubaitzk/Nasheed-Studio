# NCN Studio (Nasheed Video Automation Studio)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Qt 6 / PySide6](https://img.shields.io/badge/Qt-6.5+-green.svg)](https://www.qt.io/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-6.0+-orange.svg)](https://ffmpeg.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20x64-lightgrey.svg)](https://microsoft.com/windows)
[![Tests](https://img.shields.io/badge/tests-340+%20passing-brightgreen.svg)](tests/)

**NCN Studio** is a high-performance desktop workstation engineered to automate the production of publication-ready Nasheed playlist videos for YouTube and digital distribution. Combining an asynchronous, GPU-accelerated **PySide6 (Qt 6)** graphical interface with an industrial-grade **FFmpeg** multimedia rendering engine, NCN Studio enables content creators to build videos featuring synchronized active track indicators, dynamic multi-column layouts, customizable typography, brand logos, website watermarks, animated intro sequences, frosted glass cards, and transition sound effects.

---

## Architecture Overview

NCN Studio follows a clean, decoupled architecture separating UI state management, rendering composition, media probing, process management, and export pipelines.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        NCN Studio UI (PySide6)                         │
│  ┌───────────────────────┬───────────────────┬──────────────────────┐  │
│  │     Playlist Pane     │  16:9 Viewport    │   Inspector Panel    │  │
│  │ (Multi-Select, Reorder│ (Live Scrubber &  │(4 Scrollable Tabs,   │  │
│  │  Manual Columns Split)│  Playback Sync)   │ Visual Fine-Tuning)  │  │
│  └───────────────────────┴───────────────────┴──────────────────────┘  │
│                                  │                                     │
├──────────────────────────────────┼─────────────────────────────────────┤
│                          Core Services                                 │
│  ┌───────────────────────┬───────────────────┬──────────────────────┐  │
│  │   Compositor Service  │  Render Service   │    Export Service    │  │
│  │  (Pillow 16:9 Canvas, │ (FFmpeg Filter-   │ (Two-Stage Staging,  │  │
│  │  Zero-Halo Compositing│  graph Generator) │  Atomic Save/Export) │  │
│  ├───────────────────────┼───────────────────┼──────────────────────┤  │
│  │    Font / Probing     │  Project Service  │   Process Manager    │  │
│  │ (Registry Discovery & │ (Atomic JSON I/O, │ (Win32 Job Objects,  │  │
│  │  Silent FFprobe API)  │  Presets Engine)  │  Subprocess Cleanup) │  │
│  └───────────────────────┴───────────────────┴──────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### Module Responsibilities

| Subsystem | Primary Module | Core Functionality |
| :--- | :--- | :--- |
| **UI Shell** | `src/ui/main_window.py` | 3-pane layout, event loops, real-time preview sync, debounced updates. |
| **Icons & Style** | `src/ui/icons.py`, `src/ui/style.py` | Embedded SVG vector icons, theme tokens, high-contrast dark styling. |
| **Compositor** | `src/services/compositor.py` | 16:9 canvas layout, N-column auto-flow, antialiased pills, frosted glass intro card. |
| **Timeline Engine** | `src/services/timeline.py` | Cumulative audio timeline calculator, interval bounds, track duration validation. |
| **Render Engine** | `src/services/render_service.py` | FFmpeg complex filtergraphs, audio normalization, SFX delays, intro silence. |
| **Process Manager** | `src/services/process_manager.py` | Win32 Job Object binding (`KILL_ON_JOB_CLOSE`), process tracking, clean kill. |
| **Export Service** | `src/services/export_job.py` | Threaded rendering jobs, progress streaming, cancellation, workspace staging. |
| **Project Service** | `src/services/project_service.py` | Atomic JSON read/write (`os.replace`), preset loader, dirty state tracking. |
| **Font Service** | `src/services/font_service.py` | Windows Registry font discovery, fallback fall-through, Pillow font metrics. |
| **Media Probing** | `src/services/media_probe.py` | Headless stream inspection, sample rates, channels, duration validation. |

---

## Core Features

- **Dynamic N-Column Playlist Engine**: Distributes tracks intelligently across 1, 2, 3, or 4 columns with automatic bounding-box safety and boundary padding. Supports manual column splits.
- **Synchronized Active Indicators**: 4 distinct indicator modes (`both`, `cursor_only`, `highlight_only`, `neither`). Supports custom vector SVG and raster cursors with dynamic scaling and X-offset alignment.
- **Antialiased Pill Accent Bar**: Subpixel-smooth rounded accent bar with centered multiline highlight alignment and zero corner fringe over light, dark, or transparent backgrounds.
- **Frosted Glass Intro Presentation**: Cinematic Gaussian blur backdrop with customizable frosted presentation card, independent typography, duration, and audio intro track with fade curves.
- **Interactive Preview Playback**: Live playback engine with Play/Pause toggle, real-time timeline scrubber, synchronized indicator tracking, and continuous audio preview across track boundaries.
- **50-Step Undo/Redo Engine**: Full Command Pattern history stack with `Ctrl+Z`, `Ctrl+Y`, `Alt+Up/Down` reordering, `Delete` shortcut, and active text-input safety guards.
- **Watermark & Logo Positioning**: Bidirectional X/Y offsets, dynamic logo scaling preserving aspect ratio, native `QColorDialog` hex color picking, and collision avoidance algorithms.
- **Zero-Fringe Typography**: Windows system font discovery via Registry scanning with resolution scaling across 1080p, 1440p, and 4K UHD.
- **Unconstrained CRF 18 Master Video Export**: Studio-grade master video encoding pipeline with multi-input audio normalization and sample-accurate transition SFX.
- **Bulletproof Process Lifecycle**: Subprocesses attached to Windows Job Objects (`KILL_ON_JOB_CLOSE`), guaranteeing zero orphaned processes or memory leaks.

---

## Installation & Setup

### Prerequisites
- **Operating System:** Windows 10 (1903+) or Windows 11 (64-bit)
- **Python:** Python 3.10 or higher
- **FFmpeg:** FFmpeg 6.0+ static binaries (placed in `tools/` or available in system `PATH`)

### Quick Start (Source Code)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Rubaitzk/Nasheed-Studio.git
   cd Nasheed-Studio
   ```

2. **Create and activate a virtual environment:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Verify FFmpeg binaries:**
   Ensure `ffmpeg.exe` and `ffprobe.exe` are placed in the `tools/` folder or installed in your system PATH:
   ```powershell
   .\tools\ffmpeg.exe -version
   .\tools\ffprobe.exe -version
   ```

5. **Launch NCN Studio:**
   ```powershell
   python app.py
   ```

---

## Operational Guide

### 1. Project Setup
- **New Project:** Click `File → New Project` (`Ctrl+N`).
- **Workspace:** On initial launch, a dedicated workspace is initialized at `C:\Users\<User>\NasheedStudio\` containing `projects/`, `exports/`, and `logs/`.

### 2. Building the Playlist
- Click **Add Audio** (`Ctrl+O`) to import `.mp3`, `.wav`, `.aac`, `.flac`, `.ogg`, or `.m4a` files.
- Reorder tracks using **Move Up** (`Alt+Up`) and **Move Down** (`Alt+Down`).
- Remove tracks individually with `Delete` or select multiple tracks using `Shift+Click` / `Ctrl+Click` for bulk removal.
- Edit track titles inline; changes are debounced and update the live preview automatically.

### 3. Visual Styling & Fine Tuning
- **Layout Tab:** Select 1 to 4 columns or enable Manual Column Distribution. Configure Big Title and Nasheed Title X/Y offsets.
- **Text & Font Tab:** Customize font family, style, and size for collection title and track items. Adjust website watermark text, hex color, opacity, and X/Y offsets.
- **Indicator Tab:** Choose active track indicator mode (`Both`, `Cursor Only`, `Highlight Only`, `Neither`). Configure cursor size, custom SVG/PNG cursor path, and Cursor X-Offset.
- **Sound & Intro Tab:** Configure intro sequence duration, transition animation (Fade, Zoom, Slide), intro audio track with fade-in/out, and transition SFX audio.

### 4. Interactive Preview Playback
- Use the preview scrubber and Play/Pause button (`Space`) to test track transitions, audio sync, and visual indicator animations before exporting.
- Adjust preview volume or toggle mute directly from the preview toolbar.

### 5. Master Video Export
- Click **Export Video** in the bottom control panel.
- Select output resolution (1080p Full HD, 1440p 2K, 2160p 4K UHD).
- Select quality preset:
  - **Master Quality (CRF 18)**: Default visually lossless archival quality.
  - **Balanced (CRF 22)**: Fast turnaround with excellent compression.
- Monitor real-time progress and timecode. Renders can be safely cancelled at any moment with clean temporary workspace purging.

---

## Keyboard Shortcuts Reference

| Shortcut | Context | Action |
| :--- | :--- | :--- |
| `Ctrl+N` | Global | Create a new project |
| `Ctrl+O` | Global | Add audio tracks to playlist |
| `Ctrl+S` | Global | Save current project |
| `Ctrl+Shift+S` | Global | Save project as new file |
| `Ctrl+Z` | Global (outside text fields) | Undo last action |
| `Ctrl+Y` / `Ctrl+Shift+Z` | Global (outside text fields) | Redo last undone action |
| `Alt+Up` | Playlist | Move selected track up |
| `Alt+Down` | Playlist | Move selected track down |
| `Delete` | Playlist | Remove selected track(s) |
| `Enter` | Title Input | Commit title draft |
| `Escape` | Title Input | Cancel title draft |
| `Space` | Preview Player | Toggle Play / Pause |

---

## Developer Guide & Testing

### Running Automated Test Suite
NCN Studio includes over 340 regression, unit, and integration tests covering the entire feature matrix:

```powershell
# Run entire test suite
.\.venv\Scripts\python.exe -m pytest

# Run specific functional suites
.\.venv\Scripts\python.exe -m pytest tests/test_undo_and_shortcuts.py
.\.venv\Scripts\python.exe -m pytest tests/test_watermark_controls.py
.\.venv\Scripts\python.exe -m pytest tests/test_preview_audio_continuous.py
.\.venv\Scripts\python.exe -m pytest tests/test_lifecycle_and_export_settings.py
```

### Building Standalone Windows Executable
To package a standalone Windows executable (`dist/NCN Studio/NCN Studio.exe`):

```powershell
# Compile via PyInstaller using project spec
pyinstaller nasheed_studio.spec --noconfirm

# Or execute full distribution builder
python build_release.py
```

---

## Troubleshooting & Diagnostics

- **FFmpeg not detected:** Ensure `ffmpeg.exe` and `ffprobe.exe` are placed in `tools/` or present in Windows system `PATH`.
- **Audio concat issues:** NCN Studio automatically normalizes mixed sample rates and channel counts to stereo 44.1 kHz via `aformat` filters prior to concatenation.
- **Process management:** All worker subprocesses are assigned to Windows Job Objects. If Python terminates unexpectedly, Windows kernel limits terminate child encoders automatically.
- **Log inspection:** Detailed export and diagnostic logs are written to `<Workspace>/logs/`.

---

## Project Phases & Evolution
For detailed architectural breakdown and engineering history across each milestone, see the [`phases/`](phases/) directory:
- [`Phase 1: Stabilization & Bug Fixes`](phases/Phase1_Stabilization.md)
- [`Phase 2: Timeline Sync & Indicator Modes`](phases/Phase2_CoreFeatures.md)
- [`Phase 3: Visual Customization & Safe Closing`](phases/Phase3_VisualCustomization.md)
- [`Phase 4: Production Hardening & Master Encoding Engine`](phases/Phase4_ProductionHardening.md)
- [`Phase 5: Client Delivery & Post-Delivery Polish`](phases/Phase5_ClientDeliveryAndPolish.md)
