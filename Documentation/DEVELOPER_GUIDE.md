# Nasheed Studio — Developer & Build Guide

## 1. Architecture Overview

Nasheed Studio is architected as a modular, thread-safe Windows desktop application combining a **PySide6 (Qt 6)** graphical interface with a high-performance **FFmpeg** multimedia rendering pipeline.

### Deliverable Package Layout
The project is organized into self-contained directories within the master delivery package:

```
final_deliverable/
├── Application/              # Compiled standalone Windows x64 application
│   └── Nasheed Studio/       # Contains Nasheed Studio.exe, _internal/, and tools/
├── Source_Code/              # Complete clean Python source tree
│   ├── app.py                # Main application entry point
│   ├── build_release.py      # Automated release packaging script
│   ├── nasheed_studio.spec   # PyInstaller build specification
│   ├── requirements.txt      # Python dependencies
│   ├── assets/               # Bundled Google fonts (Montserrat, Cinzel, etc.)
│   ├── src/                  # Core source code
│   │   ├── services/         # Business logic and rendering engine
│   │   │   ├── compositor.py         # 16:9 canvas layout and Pillow overlay generator
│   │   │   ├── export_job.py         # Threaded export job with Win32 Job Object binding
│   │   │   ├── export_service.py     # Two-stage atomic export validator
│   │   │   ├── font_service.py       # Font discovery, Pillow metrics & cap-height calculation
│   │   │   ├── media_probe.py        # FFprobe metadata extraction with silent execution
│   │   │   ├── process_manager.py    # Centralized child process tracker & termination
│   │   │   ├── project_service.py    # Atomic project & template JSON I/O
│   │   │   ├── render_service.py     # FFmpeg pipeline builder & QualityPreset profiles
│   │   │   ├── timeline.py           # Audio duration & boundary calculator
│   │   │   └── workspace_service.py  # User directory management & staging cleanup
│   │   └── ui/               # PySide6 user interface
│   │       ├── main_window.py        # Primary 3-column application window
│   │       ├── icons.py              # Dynamic SVG and vector icon generators
│   │       └── style.py              # Dark theme styling tokens
│   └── tests/                # Automated pytest suite (246 unit and integration tests)
├── Documentation/            # Complete user and technical guides
├── Evidence/                 # Clean-room test logs, screenshots, and export samples
├── Templates/                # Seed design template presets (JSON)
├── Scripts/                  # Automated verification and build helpers
└── MANIFEST.md               # SHA-256 integrity checksums
```

---

## 2. Core Service Architectures

### Process Lifecycle Manager (`process_manager.py`)
To prevent orphaned background processes or zombie `conhost.exe` command shells:
- All external binaries (`ffmpeg.exe`, `ffprobe.exe`) are launched via `process_manager.launch_process()`.
- Windows flag `subprocess.CREATE_NO_WINDOW = 0x08000000` is enforced across all process invocations, preventing command shell spawning.
- Maintains an active process registry (`_active_processes`) protected by threading locks.
- Implements bounded termination (`terminate_process(proc, timeout_sec=2.0)`): attempts graceful standard input exit, escalates to `terminate()`, and finally executes `kill()` if necessary.
- Automatic cleanup hooks registered via `atexit.register(cleanup_all_processes)`.

### Win32 Job Object Protection (`export_job.py`)
- Background render tasks execute on a dedicated `QThread`.
- Windows Win32 Job Objects are instantiated via `ctypes`:
  - `JobObjectExtendedLimitInformation` is configured with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x2000)`.
  - The render process is assigned to this job object immediately upon launch.
  - If the application process crashes or is killed, Windows automatically terminates all child and grandchild processes at the operating system level.

### Video Rendering Engine & Quality Presets (`render_service.py`)
The rendering engine builds an FFmpeg filter graph capable of combining:
1. **Looping Video Backgrounds:** Invokes `-stream_loop -1 -i bg.mp4` with a complex filter chain scaling and cropping to the canvas aspect ratio.
2. **Audio Track Timeline:** Concatenates sequential audio streams, normalizes sample rates to 48,000 Hz, and layers transition SFX at exact track boundaries.
3. **Pillow Overlay Overlays:** Renders typography, active track indicators, and logos to high-resolution PNG overlay streams with clean alpha compositing.

#### Quality Preset Definitions (`QualityPreset`)
```python
class QualityPreset(str, Enum):
    ULTRA_DETAIL = "ultra_detail"  # Master quality (CRF 18 unconstrained, 320 kbps AAC)
    HIGH = "high"                  # High quality (CRF 22, capped, 192 kbps AAC)
    BALANCED = "balanced"          # Balanced web (CRF 24, capped, 160 kbps AAC)
    FAST = "fast"                  # Fast draft (CRF 28, capped, 128 kbps AAC)
```
- In **Ultra Detail** mode, `-maxrate` and `-bufsize` are intentionally omitted to allow unconstrained peak bitrate for complex scenes (starry skies, grain, particles), yielding ~12–14 Mbps at 1080p.
- In **High / Balanced / Fast** modes, rate-limiting parameters ensure predictable, compact file sizes.

### Atomic Staging & Export Safety (`export_service.py`)
- Renders initially to an isolated staging file: `<output_path>.part.mp4`.
- On completion, verifies output existence, non-zero file size, and valid container headers via `FFprobe`.
- Performs an atomic replace to the final destination `<output_path>` via `os.replace()`.
- On error or user cancellation, cleanly removes the `.part.mp4` file, ensuring existing destination files are never corrupted.

---

## 3. Developer Environment Setup

### Prerequisites
- **Operating System:** Windows 10 (version 1903+) or Windows 11 (64-bit)
- **Python:** 3.10.x (exact runtime bundled in release)
- **FFmpeg:** Windows static build of FFmpeg 7+ or 8+ placed in `tools/`

### Step-by-Step Environment Setup

```powershell
# 1. Open PowerShell and navigate to the project root
cd D:\path\to\nasheed_studio

# 2. Create Python 3.10 virtual environment
python -m venv .venv

# 3. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 4. Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller>=6.0 pytest pytest-cov

# 5. Verify local tools
.\tools\ffmpeg.exe -version
.\tools\ffprobe.exe -version

# 6. Launch application in development mode
python app.py
```

---

## 4. Running the Automated Test Suite

The test suite contains 246 unit, integration, and UI tests covering layout calculation, font metrics, process lifecycle, project serialization, and FFmpeg filter-graph generation:

```powershell
# Run full test suite
.\.venv\Scripts\python.exe -m pytest tests/ -v

# Run process lifecycle tests specifically
.\.venv\Scripts\python.exe -m pytest tests/test_process_manager.py -v

# Run export and rendering tests
.\.venv\Scripts\python.exe -m pytest tests/test_render_service.py tests/test_export_job.py -v
```

---

## 5. Building the Standalone Executable

The build automation script `build_release.py` compiles the application into a standalone distribution:

```powershell
# Full release build with pre-flight checks and automated test execution:
python build_release.py

# Optional flags:
#   --clean       Removes previous dist/ and build/ folders before packaging
#   --skip-tests  Skips pytest execution (for rapid packaging iteration)
python build_release.py --clean
```

### Build Pipeline Stages:
1. **Phase 1 — Pre-flight Checks:** Verifies Python 3.10 runtime, PySide6, Pillow, spec file, and static FFmpeg binaries in `tools/`.
2. **Phase 2 — Automated Testing:** Runs pytest suite and asserts 100% pass rate.
3. **Phase 3 — PyInstaller Compilation:** Invokes `nasheed_studio.spec` to create an `onedir` distribution in `dist/Nasheed Studio/`.
4. **Phase 4 — Bundle Verification:** Checks presence of `Nasheed Studio.exe`, Qt platform plugins (`qwindows.dll`), multimedia plugins, and bundled FFmpeg.
5. **Phase 5 — Release Assembly:** Assembles `release_build/` containing `Application/`, `Source_Code/`, `Documentation/`, `Evidence/`, `Templates/`, and `Installation/`.
6. **Phase 6 — Checksum Generation:** Calculates SHA-256 hashes and outputs `MANIFEST.md`.
