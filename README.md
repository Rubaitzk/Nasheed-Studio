# Nasheed Studio

A professional Windows desktop application designed to automate the production of high-quality Nasheed playlist collection videos with synchronized track indicators, flexible multi-column layouts, customizable branding, and high-resolution MP4 export.

---

## Delivery Package Structure

The project is delivered as a comprehensive, self-contained master distribution package (`final_deliverable/` or `Nasheed_Studio_Complete_Project_v1.0.zip`), containing everything needed for both immediate end-user operation and future developer maintenance:

```
final_deliverable/
├── Application/
│   └── Nasheed Studio/
│       ├── Nasheed Studio.exe        # Standalone executable (zero external dependencies required)
│       ├── _internal/                # Bundled Python 3.10 runtime & PySide6 Qt 6 libraries
│       └── tools/                    # Static FFmpeg 8.1 & FFprobe binaries
├── Source_Code/                      # Complete clean Python source code
│   ├── app.py                        # Application entry point
│   ├── build_release.py              # Automated packaging & distribution builder
│   ├── nasheed_studio.spec           # PyInstaller build specification
│   ├── requirements.txt              # Python runtime dependencies
│   ├── src/                          # Modular services and PySide6 UI components
│   └── assets/                       # Bundled fonts, icons, and templates
├── Documentation/                    # Comprehensive user and technical guides
│   ├── USER_GUIDE.md                 # End-user operational guide & feature walkthrough
│   ├── DEVELOPER_GUIDE.md            # Architecture, pipeline, and developer build instructions
│   ├── TROUBLESHOOTING.md            # Diagnostics, process lifecycle, and FAQs
│   ├── INSTALLATION.md               # Quick-start extraction and launch guide
│   └── ACCEPTANCE_TEST_GUIDE.md      # 25-step manual QA verification checklist
├── Evidence/                         # Real-world verification proofs and audit reports
│   ├── ultra_detail_master_render_1080p.mp4  # Verified 12.75 Mbps CRF 18 master export
│   ├── verification_render_1080p_crf22.mp4   # Verified 6.40 Mbps balanced export
│   ├── verification_audit_report.txt         # Zero-orphan process lifecycle audit report
│   ├── ultra_detail_frame_03s.png            # Frame proof at 3.0s
│   ├── ultra_detail_frame_15s_loop.png       # Seamless video background loop proof at 15.0s
│   └── clean_environment_test_export_1080p.mp4 # Standalone clean-machine test export
├── Templates/                        # Reusable Nasheed design layout presets (JSON)
├── Scripts/                          # Test suite runner and automated build scripts
└── MANIFEST.md                       # Delivery manifest, file index, and SHA-256 checksums
```

---

## Key Features

### 1. Ultra Detail · Master Quality Rendering Engine
- **Restored Unconstrained CRF 18:** Encodes via `libx264` with no artificial bitrate clamping (`-maxrate` and `-bufsize` omitted in master mode). Preserves the finest details, including starry skies, atmospheric smoke, particle effects, and film grain on looping video backgrounds without macroblocking or color banding.
- **Studio-Grade AAC Audio:** 320 kbps AAC stereo encoding preserving full dynamic audio range and crisp acoustics.
- **Selectable Quality Presets:**
  - **Ultra Detail · Master Quality (Recommended):** Unconstrained CRF 18, 320 kbps audio (~12–14 Mbps total bitrate; ~850–900 MB for a 10-minute 1080p video).
  - **High Quality · Balanced:** CRF 22 with gentle caps, 192 kbps audio (~5–6 Mbps total bitrate; ~400–450 MB for 10 minutes).
  - **Web / Fast:** CRF 26 with tighter caps, 128 kbps audio (~2.5–3.5 Mbps total bitrate; ~200–250 MB for 10 minutes).
- **Multi-Resolution Export:** Supports 1080p Full HD (1920×1080), 1440p QHD (2560×1440), and 4K UHD (3840×2160).
- **Atomic Two-Stage Export:** Renders to a temporary `.part.mp4` file and atomically commits upon 100% completion, protecting existing files from corruption.

### 2. Process Lifecycle Management & Zero Zombie Safety
- **Centralized `ProcessManager`:** All child subprocesses (`ffmpeg.exe`, `ffprobe.exe`) are launched through a centralized manager (`src/services/process_manager.py`) with `CREATE_NO_WINDOW` creation flags, completely eliminating black command-window flashing and Command Prompt hosts.
- **Win32 Job Object Protection:** Background render jobs are assigned to a Windows Job Object configured with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. Even if the application terminates unexpectedly, Windows automatically reaps all child processes.
- **Bounded Graceful Termination:** Subprocesses receive graceful termination signals followed by bounded timeout escalation (`wait(2.0)` → `terminate()` → `kill()`).
- **Comprehensive Cleanup Hooks:** Safe shutdown triggers on normal exit, window close (`closeEvent`), render cancellation, render failure, and Python `atexit`.

### 3. Looping Video & Image Backgrounds
- **Seamless MP4 Video Backgrounds:** Import any MP4 or MOV video. The rendering engine loops the background seamlessly across the entire timeline to match the combined duration of all audio tracks.
- **Still Image Backgrounds:** Full support for PNG, JPG, JPEG, and WebP images.
- **Aspect-Aware Scaling:** Auto-centers and scales media to 16:9 canvas dimensions without distortion.

### 4. Audio & Playlist Management
- **Multi-Format Ingestion:** Import MP3, WAV, AAC, FLAC, and M4A audio files.
- **Automated Metadata Extraction:** Millisecond-accurate duration probing using bundled FFprobe.
- **Interactive Editing:** Double-click any track in the playlist pane to rename display titles independently of original filenames.
- **Flexible Ordering:** Drag-and-drop reordering with live preview canvas updates.
- **Layout Columns:** Choose between 1-column and 2-column layouts with adjustable column gap, playlist width, and horizontal/vertical positioning.

### 5. Active Track Indicators
- **Independent Highlight Modes:**
  - **Pill:** Modern rounded pill highlight behind the active track.
  - **Rectangle:** Clean rectangular highlight box with adjustable margins and padding.
  - **Outline:** Sleek border outline accent.
  - **Glass:** Frosted, translucent backdrop accent.
  - Full control over highlight color, opacity, and margin offsets.
- **Custom Animated Cursors:**
  - Built-in pointers or custom image cursors (PNG/SVG).
  - Adjustable size and font-cap-height-normalized vertical alignment.
  - Toggle cursor and highlight independently or use both simultaneously.

### 6. Typography, Branding & Watermarks
- **Independent Typography Controls:** Separate font family, style (Regular, Bold, Italic), and size controls for Collection Title and Playlist items.
- **Bundled Fonts:** Ships with modern typography including Montserrat, Bebas Neue, Oswald, and Cinzel, alongside full Windows system font discovery.
- **Brand Logo:** 4-corner placement (Top-Left, Top-Right, Bottom-Left, Bottom-Right) with adjustable scale, alpha opacity, and background cleanup.
- **Website Watermark:** Corner website URL watermark with collision-avoiding safety margins.

### 7. Intro Animation & Sound Effects
- **Intro Sequence:** Configurable opening card with animated collection title, subtitle, duration (1–10s), and fade/slide/zoom transitions.
- **Track Transition SFX:** Optional audio cues (chimes, clicks, or custom sound effects) that trigger at each track transition with custom volume control.

---

## Quick Start (No Python Required)

1. Unzip the delivery archive (`final_deliverable.zip` or `Nasheed_Studio_Complete_Project_v1.0.zip`).
2. Open the `Application\Nasheed Studio\` folder.
3. Double-click **`Nasheed Studio.exe`**.
4. The application launches immediately. No Python, FFmpeg, or external codecs are required.

---

## Running from Source (Developer Setup)

### Requirements
- **OS:** Windows 10 or Windows 11 (64-bit)
- **Python:** 3.10 (recommended)
- **FFmpeg & FFprobe:** Included in `tools/` or available on system `PATH`

### Step-by-Step Setup
```powershell
# 1. Navigate to the project root
cd Source_Code

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Launch the application
python app.py

# 5. Run the automated test suite (246 tests)
python -m pytest tests/ -v
```

---

## Building Standalone Executables

To reproduce the self-contained Windows executable bundling the Python runtime, PySide6, FFmpeg, and assets:

```powershell
python build_release.py
```

The compiled release package will be generated inside `release_build/`.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
