# Nasheed Studio

A modern Windows desktop application designed to automate the production of high-quality Nasheed playlist collection videos with synchronized track indicators, flexible multi-column layouts, customizable branding, and high-resolution MP4 export.

---

## Overview

**Nasheed Studio** empowers content creators to design and render professional playlist videos without requiring manual video editing software or command-line scripting. The application combines a responsive 3-panel PySide6 interface with an FFmpeg-backed rendering engine, producing Full HD (1080p), 2K (1440p), and 4K (2160p) videos.

---

## Key Features

### 1. Dynamic Backgrounds
- **Image Backgrounds:** Full support for PNG, JPG, JPEG, and WebP images.
- **Video Backgrounds:** Loopable MP4 video background support with seamless playback synchronization across the full audio timeline.

### 2. Audio & Playlist Management
- **Multi-Track Import:** Add MP3, WAV, AAC, FLAC, and M4A audio files.
- **Interactive Editing:** Double-click to rename titles independently of original filenames.
- **Flexible Ordering:** Reorder tracks via drag-and-drop or toolbar controls.
- **Flexible Columns:** 1-column, 2-column, or multi-column layouts with adjustable spacing, widths, and positioning.
- **Automatic Duration Detection:** Precise audio probing using FFprobe for accurate track-by-track timelines.

### 3. Active Track Indicators
- **Independent Highlight Modes:**
  - **Pill:** Rounded pill-style highlight.
  - **Rectangle:** Thick solid rectangular highlight box with adjustable padding.
  - **Outline:** Sleek border bounding box.
  - **Glass:** Frosted, translucent backdrop accent.
  - Full control over highlight color, opacity, and margin offsets.
- **Custom Cursors:**
  - Choose between built-in pointers or custom image cursors (PNG/SVG).
  - Adjustable size and font-cap-height-normalized vertical alignment.
  - Toggle cursor and highlight independently or use both simultaneously.

### 4. Typography & Branding
- **Independent Typography Controls:** Configure fonts, styles, weights, and sizes separately for the Collection Title and Playlist items.
- **Bundled Fonts:** Ships with modern typography including Montserrat, Bebas Neue, Oswald, and Cinzel, alongside full Windows system font enumeration.
- **Brand Logo & Watermark:**
  - 4-corner placement (Top-Left, Top-Right, Bottom-Left, Bottom-Right).
  - Adjustable scale and alpha opacity blending.
  - Optional corner website text watermark with non-overlapping safety boundaries.

### 5. Intro Animation & Sound Effects
- **Intro Sequence:** Configurable opening card with animated title, subtitle, duration, and fade transitions.
- **Audio Cues:** Optional track-transition sound effects (chimes, clicks, or custom audio) with volume control.

### 6. Templates & Presets
- **Built-in Reference Layouts:** Includes ready-to-use presets inspired by popular Nasheed channel aesthetics (Monochrome Lion, Two-Column Warrior, Battlefield Knight, Glass Highlight).
- **User Template Library:** Save, import, and export custom JSON design presets (`user_templates/`) to streamline future productions.
- **Atomic Project Files:** Save and reopen `.nasheed` / `.json` project files safely without risk of data corruption.

### 7. Engine Safety & Process Lifecycle
- **Zero-Halo Compositing:** Crisp single-layer alpha blending without muddy shadows or color bleeding.
- **Win32 Job Object & Process Manager:** Prevents orphaned FFmpeg processes or zombie conhost windows during cancellation or app exit.
- **Atomic Staging Export:** Renders to a `.part.mp4` file first and commits only upon 100% successful render completion, ensuring existing outputs are never corrupted.

---

## Project Structure

```
nasheed_studio/
├── app.py                      # Main application entry point
├── build_release.py            # Automated standalone packaging script
├── assemble_only.py            # Packaging assembly helper
├── requirements.txt            # Python dependencies
├── assets/                     # Core bundled assets and typography
│   └── fonts/                  # Bundled Google fonts (Montserrat, Cinzel, etc.)
├── src/
│   ├── services/               # Core business logic and rendering services
│   │   ├── compositor.py       # Layout calculation and Pillow overlay renderer
│   │   ├── export_job.py       # Threaded render job with Win32 Job Object binding
│   │   ├── export_service.py   # FFmpeg command builder and export validation
│   │   ├── font_service.py     # System and custom font discovery and metric calculations
│   │   ├── media_probe.py      # FFprobe metadata extraction (audio durations, video streams)
│   │   ├── process_manager.py  # Centralized child process tracker and clean termination
│   │   ├── project_service.py  # Atomic project and template I/O
│   │   ├── render_service.py   # Multi-pass video rendering pipeline
│   │   └── workspace_service.py# Temporary render staging and cache cleanup
│   └── ui/                     # PySide6 graphical user interface
│       ├── main_window.py      # Primary 3-column application window and state handlers
│       ├── icons.py            # Dynamic SVG and vector icon generators
│       └── style.py            # High-contrast dark theme stylesheet
├── templates/                  # Built-in reference layout presets
├── user_templates/             # Reusable user template presets and documentation
└── tools/                      # Local FFmpeg / FFprobe binaries (optional)
```

---

## Installation & Setup

### Option A: Standalone Windows Executable (Recommended for End Users)
If using the packaged release:
1. Extract the `Nasheed_Studio_Windows_x64.zip` distribution.
2. Launch `Nasheed Studio.exe`.
3. No Python or external dependencies required.

### Option B: Running from Source

#### Requirements
- **OS:** Windows 10 or 11 (64-bit)
- **Python:** 3.10, 3.11, or 3.12
- **FFmpeg & FFprobe:** Installed and available on your system `PATH`, or placed inside the `tools/` directory (`tools/ffmpeg.exe`, `tools/ffprobe.exe`).

#### Step-by-Step Setup
1. **Clone the repository:**
   ```powershell
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

4. **Verify FFmpeg:**
   ```powershell
   ffmpeg -version
   ffprobe -version
   ```

5. **Launch the application:**
   ```powershell
   python app.py
   ```

---

## Workflow Guide

1. **Set Background:** Choose an image or loopable MP4 video background.
2. **Add Tracks:** Click **Add Tracks** to select audio files. Drag to reorder, or double-click to rename titles.
3. **Configure Layout & Typography:**
   - Adjust column count (1 or 2), row spacing, and playlist width.
   - Select custom fonts, sizes, and colors for titles and tracks.
   - Choose between **Pill**, **Rectangle**, **Outline**, or **Glass** highlight styles.
   - Select or import a custom cursor icon and adjust its scale.
4. **Branding & Intro:**
   - Select an optional brand logo and choose its corner placement.
   - Configure the opening intro card and track-change sound effect if desired.
5. **Preview & Render:**
   - Check the 16:9 interactive preview canvas.
   - Choose resolution (**1080p Full HD**, **1440p 2K**, or **2160p 4K UHD**).
   - Set output destination and click **Render MP4**.

---

## Building Standalone Executables

To build a clean, self-contained Windows executable bundling PyInstaller, FFmpeg, fonts, and preset templates:

```powershell
python build_release.py
```

The compiled release will be assembled in `dist/` and zipped for distribution.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
