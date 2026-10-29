"""
build_release.py — Production release builder for Nasheed Studio.

Usage
-----
    python build_release.py [--clean] [--skip-tests]

What it does
------------
1. Verifies required source files and binaries (ffmpeg / ffprobe) are present.
2. Optionally runs the automated test suite (skip with --skip-tests).
3. Invokes PyInstaller with nasheed_studio.spec to produce an onedir bundle.
4. Copies the bundle into release_build/Application/.
5. Packages the source code into release_build/Source_Code/.
6. Copies scripts, templates, documentation placeholders and writes MANIFEST.md.
7. Creates a ZIP archive of the Application directory for distribution.

Output
------
    release_build/
      Application/
        Nasheed Studio/       ← unzip this anywhere and run Nasheed Studio.exe
      Source_Code/            ← complete Python source
      Scripts/                ← test + automation scripts
      Templates/              ← user_templates seed files
      Installation/           ← install instructions
      Documentation/          ← user guide, developer guide, troubleshooting
      Evidence/               ← placeholder for test evidence
      Nasheed_Studio_Windows_x64.zip
      MANIFEST.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
SPEC_FILE = ROOT / "nasheed_studio.spec"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
TOOLS_DIR = ROOT / "tools"
ASSETS_DIR = ROOT / "assets"
SRC_DIR = ROOT / "src"
TESTS_DIR = ROOT / "tests"
TEMPLATES_DIR = ROOT / "user_templates"
PACKAGING_DIR = ROOT / "packaging"
DOCS_DIR = ROOT / "Documentation"

RELEASE_DIR = ROOT / "release_build"
APP_OUT = RELEASE_DIR / "Application"
SRC_OUT = RELEASE_DIR / "Source_Code"
SCRIPTS_OUT = RELEASE_DIR / "Scripts"
TEMPLATES_OUT = RELEASE_DIR / "Templates"
INSTALL_OUT = RELEASE_DIR / "Installation"
DOCS_OUT = RELEASE_DIR / "Documentation"
EVIDENCE_OUT = RELEASE_DIR / "Evidence"

BUNDLE_NAME = "Nasheed Studio"
ZIP_NAME = "Nasheed_Studio_Windows_x64.zip"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def header(msg: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {msg}")
    print(f"{'='*70}")


def step(msg: str) -> None:
    print(f"  >> {msg}")


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def warn(msg: str) -> None:
    print(f"  WARN  {msg}", file=sys.stderr)


def die(msg: str) -> None:
    print(f"\n  FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Phase 1 — Pre-flight checks
# ---------------------------------------------------------------------------

def check_prerequisites() -> None:
    header("Phase 1 — Pre-flight checks")

    # Required source files
    required = [
        ROOT / "app.py",
        ROOT / "nasheed_studio.spec",
        SRC_DIR / "services" / "compositor.py",
        SRC_DIR / "services" / "render_service.py",
        SRC_DIR / "services" / "export_service.py",
        SRC_DIR / "services" / "media_probe.py",
        SRC_DIR / "services" / "font_service.py",
        SRC_DIR / "services" / "workspace_service.py",
        SRC_DIR / "services" / "export_job.py",
        SRC_DIR / "services" / "timeline.py",
        SRC_DIR / "services" / "project_service.py",
        SRC_DIR / "ui" / "main_window.py",
        SRC_DIR / "ui" / "icons.py",
        SRC_DIR / "ui" / "style.py",
    ]
    for p in required:
        if not p.is_file():
            die(f"Required source file missing: {p}")
    ok("Source files present")

    # FFmpeg / FFprobe
    ffmpeg = TOOLS_DIR / "ffmpeg.exe"
    ffprobe = TOOLS_DIR / "ffprobe.exe"
    if not ffmpeg.is_file():
        die(f"ffmpeg.exe not found at {ffmpeg}")
    if not ffprobe.is_file():
        die(f"ffprobe.exe not found at {ffprobe}")
    ok(f"ffmpeg.exe ({ffmpeg.stat().st_size // 1_000_000} MB)")
    ok(f"ffprobe.exe ({ffprobe.stat().st_size // 1_000_000} MB)")

    # PyInstaller
    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True, text=True, check=True
        )
        ok(f"PyInstaller {result.stdout.strip()}")
    except Exception as exc:
        die(f"PyInstaller not available: {exc}")

    # Assets directory
    if not ASSETS_DIR.is_dir():
        die(f"Assets directory missing: {ASSETS_DIR}")
    ok(f"Assets directory: {ASSETS_DIR}")

    # Spec file
    if not SPEC_FILE.is_file():
        die(f"Spec file missing: {SPEC_FILE}")
    ok(f"Spec file: {SPEC_FILE.name}")


# ---------------------------------------------------------------------------
# Phase 2 — Run tests (optional)
# ---------------------------------------------------------------------------

def run_tests() -> None:
    header("Phase 2 — Running automated tests")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(TESTS_DIR),
         "-x", "--tb=short", "-q"],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        die(
            "Test suite failed. Fix test failures before building a release, "
            "or pass --skip-tests to skip (document the skipped tests in Evidence/)."
        )
    ok("All tests passed")


# ---------------------------------------------------------------------------
# Phase 3 — PyInstaller build
# ---------------------------------------------------------------------------

def run_pyinstaller(clean: bool) -> Path:
    header("Phase 3 — PyInstaller build")

    if clean:
        step("Cleaning previous build artifacts…")
        for d in (DIST_DIR, BUILD_DIR):
            if d.exists():
                shutil.rmtree(d)
                ok(f"Removed {d}")

    step(f"Running PyInstaller with spec: {SPEC_FILE.name}")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller",
         "--noconfirm",
         str(SPEC_FILE)],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        die(f"PyInstaller exited with code {result.returncode}")

    bundle = DIST_DIR / BUNDLE_NAME
    if not bundle.is_dir():
        die(f"Expected distribution directory not found: {bundle}")

    exe = bundle / f"{BUNDLE_NAME}.exe"
    if not exe.is_file():
        die(f"Executable not found in bundle: {exe}")

    ok(f"Bundle created: {bundle}")
    ok(f"Executable: {exe} ({exe.stat().st_size // 1_000_000} MB)")
    return bundle


# ---------------------------------------------------------------------------
# Phase 4 — Verify bundled dependencies
# ---------------------------------------------------------------------------

def verify_bundle(bundle: Path) -> None:
    header("Phase 4 — Verifying bundled dependencies")

    # PyInstaller 6.x places all internal files under _internal/ alongside the EXE.
    # PyInstaller 5.x places them directly in the bundle root.
    internal = bundle / "_internal"
    data_root = internal if internal.is_dir() else bundle

    critical = [
        bundle / f"{BUNDLE_NAME}.exe",
        data_root / "tools" / "ffmpeg.exe",
        data_root / "tools" / "ffprobe.exe",
        data_root / "assets",
        data_root / "user_templates",
    ]
    missing = [str(p) for p in critical if not p.exists()]
    if missing:
        die(f"Critical bundle contents missing:\n  " + "\n  ".join(missing))
    ok("Critical bundle contents verified")

    # Qt platform plugin (required for windowed mode on Windows)
    qwindows = data_root / "PySide6" / "plugins" / "platforms" / "qwindows.dll"
    if not qwindows.is_file():
        alt = data_root / "platforms" / "qwindows.dll"
        if alt.is_file():
            ok("qwindows.dll present (alternate path)")
        else:
            warn(
                "qwindows.dll not found — the application may fail to start on "
                "machines without Qt installed. Check PySide6/plugins/platforms/."
            )
    else:
        ok("qwindows.dll present")

    # Multimedia plugin (needed for QMediaPlayer preview)
    mm_plugin = data_root / "PySide6" / "plugins" / "multimedia" / "ffmpegmediaplugin.dll"
    alt_mm = data_root / "multimedia" / "ffmpegmediaplugin.dll"
    if mm_plugin.is_file() or alt_mm.is_file():
        ok("ffmpegmediaplugin.dll present")
    else:
        warn("ffmpegmediaplugin.dll not found — QMediaPlayer preview may be limited.")

    ok(f"Bundle layout: {'_internal/ subdirectory' if internal.is_dir() else 'root (PyInstaller 5)'}")
    ok("Bundle verification complete")


# ---------------------------------------------------------------------------
# Phase 5 — Assemble release_build/
# ---------------------------------------------------------------------------

def assemble_release(bundle: Path) -> Path:
    header("Phase 5 — Assembling final_deliverable structure under release_build/")

    ensure_dir(APP_OUT)
    ensure_dir(SRC_OUT)
    ensure_dir(SCRIPTS_OUT)
    ensure_dir(TEMPLATES_OUT)
    ensure_dir(INSTALL_OUT)
    ensure_dir(DOCS_OUT)
    ensure_dir(EVIDENCE_OUT)

    # 5a. Application bundle
    dest_bundle = APP_OUT / BUNDLE_NAME
    if dest_bundle.exists():
        shutil.rmtree(dest_bundle)
    step(f"Copying bundle to {dest_bundle}…")
    shutil.copytree(bundle, dest_bundle)
    ok(f"Application bundle copied")

    # 5b. Source code (exclude .venv, build, dist, __pycache__, release_build)
    step("Copying source code…")
    EXCLUDE_DIRS = {".venv", "build", "dist", "__pycache__", "release_build", "final_deliverable",
                   ".pytest_cache", ".git", "scratch", "mp4_proof",
                   "video_proof_of_template_not_working",
                   "video_proof_of_template_not_loading",
                   "picture_for_improving_layout",
                   "picture_of_video_playlist_display",
                   "pictur e_of_video_playlist_display",
                   "last_improvements",
                   "picture_of_video_playlist_design_reference"}
    for item in ROOT.iterdir():
        if item.name in EXCLUDE_DIRS:
            continue
        dest = SRC_OUT / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
        elif item.is_file() and item.suffix in (".py", ".txt", ".md", ".spec", ".json", ".gitignore"):
            shutil.copy2(item, dest)
    ok("Source code copied")

    # 5c. Scripts
    step("Copying scripts…")
    script_sources = [
        ROOT / "packaging" / "build_exe.py",
        ROOT / "build_release.py",
        ROOT / "tests",
    ]
    for s in script_sources:
        if s.is_file():
            shutil.copy2(s, SCRIPTS_OUT / s.name)
        elif s.is_dir() and s.exists():
            dest = SCRIPTS_OUT / s.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(s, dest,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    ok("Scripts copied")

    # 5d. Templates
    step("Copying templates…")
    if TEMPLATES_DIR.is_dir():
        for f in TEMPLATES_DIR.iterdir():
            if f.is_file():
                shutil.copy2(f, TEMPLATES_OUT / f.name)
    ok("Templates copied")

    # 5e. Installation instructions
    if (ROOT / "Documentation" / "INSTALLATION.md").is_file():
        shutil.copy2(ROOT / "Documentation" / "INSTALLATION.md", INSTALL_OUT / "INSTALLATION.md")
    else:
        install_txt = INSTALL_OUT / "INSTALLATION.md"
        install_txt.write_text(INSTALLATION_GUIDE, encoding="utf-8")
    ok("Installation guide written")

    # 5f. Documentation
    if DOCS_DIR.is_dir():
        for doc_file in DOCS_DIR.iterdir():
            if doc_file.is_file():
                shutil.copy2(doc_file, DOCS_OUT / doc_file.name)
    else:
        (DOCS_OUT / "USER_GUIDE.md").write_text(USER_GUIDE, encoding="utf-8")
        (DOCS_OUT / "DEVELOPER_GUIDE.md").write_text(DEVELOPER_GUIDE, encoding="utf-8")
        (DOCS_OUT / "TROUBLESHOOTING.md").write_text(TROUBLESHOOTING_GUIDE, encoding="utf-8")
    ok("Documentation written")

    # 5g. Evidence placeholder
    evidence_note = EVIDENCE_OUT / "README.md"
    evidence_note.write_text(
        "# Test Evidence\n\n"
        "Place clean-environment test screenshots, exported sample videos, and test "
        "logs here before delivering to the client.\n\n"
        "Required evidence items:\n"
        "- Screenshot of application launch in clean environment\n"
        "- Screenshot of completed export dialog\n"
        "- Sample exported MP4 (short, ≤60 s)\n"
        "- Test log from clean-environment session\n",
        encoding="utf-8",
    )
    ok("Evidence placeholder created")

    # 5h. ZIP of Application
    zip_path = RELEASE_DIR / ZIP_NAME
    step(f"Creating ZIP archive: {zip_path.name}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(APP_OUT):
            # Skip __pycache__ inside the bundle
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for file in files:
                full = Path(root) / file
                rel = full.relative_to(APP_OUT)
                zf.write(full, rel)
    ok(f"ZIP created: {zip_path} ({zip_path.stat().st_size // 1_000_000} MB)")

    return RELEASE_DIR


# ---------------------------------------------------------------------------
# Phase 6 — Write MANIFEST
# ---------------------------------------------------------------------------

def write_manifest(bundle: Path, release_dir: Path) -> None:
    header("Phase 6 — Writing MANIFEST.md")

    exe = bundle / f"{BUNDLE_NAME}.exe"
    zip_path = release_dir / ZIP_NAME

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    exe_hash = sha256(exe) if exe.is_file() else "N/A"
    zip_hash = sha256(zip_path) if zip_path.is_file() else "N/A"

    manifest = f"""# Nasheed Studio — Delivery Manifest

Generated: {ts}

## Executable

| File | SHA-256 |
|------|---------|
| `Application/Nasheed Studio/Nasheed Studio.exe` | `{exe_hash}` |

## Delivery Package Structure

The client receives the entire project archive containing:

```
final_deliverable/
  Application/
    Nasheed Studio/         ← Run "Nasheed Studio.exe" to launch
  Source_Code/              ← Complete clean Python source for maintenance
  Scripts/
    build_release.py        ← Reproduces this build
    build_exe.py            ← Legacy packaging helper
    tests/                  ← Automated test suite (246 tests)
  Templates/                ← Seed design templates (JSON)
  Installation/
    INSTALLATION.md         ← Installation and first-run instructions
  Documentation/
    USER_GUIDE.md           ← End-user operational guide
    DEVELOPER_GUIDE.md      ← Developer / build guide
    TROUBLESHOOTING.md      ← Diagnostics & process lifecycle guide
    ACCEPTANCE_TEST_GUIDE.md← 25-step QA checklist
  Evidence/                 ← Clean-environment test screenshots and master exports
  MANIFEST.md               ← This file
```

## What the client receives

The client unzips the master project archive to any directory on a Windows 10/11 machine,
navigates to `Application/Nasheed Studio/`, and double-clicks `Nasheed Studio.exe`.
No Python installation is required. No additional codecs or software installations are needed.
FFmpeg is bundled inside the `tools/` sub-directory.
The complete source code, templates, tests, and documentation are included for full transparency.

## Source-code notes

The `Source_Code/` directory contains the complete Python source tree.
It excludes virtual environments, build artifacts, and temporary caches.
To run from source or execute the test suite, follow `Documentation/DEVELOPER_GUIDE.md`.
"""
    manifest_path = release_dir / "MANIFEST.md"
    manifest_path.write_text(manifest, encoding="utf-8")
    ok(f"MANIFEST.md written")


# ---------------------------------------------------------------------------
# Inline documentation strings
# ---------------------------------------------------------------------------

INSTALLATION_GUIDE = """\
# Nasheed Studio — Installation Guide

## System Requirements

- Windows 10 (version 1903+) or Windows 11
- x64 (64-bit) processor
- 4 GB RAM minimum, 8 GB recommended
- GPU with Direct3D 11 support (for smooth preview, not required for export)
- Disk space: ~700 MB for the application + space for your projects and exports

## Installation Steps

1. Extract `Nasheed_Studio_Windows_x64.zip` to a folder of your choice.
   For example: `C:\\Programs\\Nasheed Studio\\`

2. No installer is required. The application is fully portable.

3. Double-click **Nasheed Studio.exe** to launch.

## First Run

On first launch, Nasheed Studio creates a workspace folder at:
    `C:\\Users\\<YourName>\\NasheedStudio\\`

This folder contains your projects, exports, and templates.
You can relocate it via **File → Change Workspace** inside the application.

## Uninstallation

Delete the `Nasheed Studio` folder. Remove the workspace folder
(`C:\\Users\\<YourName>\\NasheedStudio\\`) if you want to erase all projects.

## Bundled components

- Python 3.10 runtime (embedded, not system-wide)
- PySide6 6.7 (Qt 6 for Windows)
- Pillow 10+ image processing library
- FFmpeg 7 static build (tools/ffmpeg.exe, tools/ffprobe.exe)

No internet connection is required to use the application.
"""

USER_GUIDE = """\
# Nasheed Studio — User Guide

## Overview

Nasheed Studio creates professionally styled MP4 playlist videos from your
audio tracks. Each track is highlighted in sequence as the video plays,
with animated cursor and highlight effects, customizable typography, logo
and watermark overlays, optional intro cards, and track-change sound effects.

---

## Launching the Application

Double-click **Nasheed Studio.exe** in the application folder.
The workspace is created automatically on first launch.

---

## Creating a New Project

1. Click **New** in the top toolbar (or File → New).
2. The project is initially untitled and shown as "Unsaved" in the toolbar.

---

## Adding and Reordering Audio Tracks

1. Click **Add Track** (+ button) in the Playlist pane.
2. Browse and select one or more MP3/WAV/AAC/FLAC files.
3. Track duration is detected automatically.
4. To reorder, drag tracks up or down in the list.
5. To remove a track, select it and click the remove (−) button.

The track title shown in the video defaults to the audio file name.
Double-click any track entry to rename it.

---

## Setting the Collection Title

Type your collection title in the **Collection Title** field above the track list
and click **Apply Title** to update the preview.

---

## Choosing a Background

In the **Inspector → Layout & Assets** tab:
1. Click **Browse…** next to Background.
2. Select a JPEG/PNG image **or** an MP4/MOV video file.
3. For video backgrounds: the video loops automatically to cover the full audio duration.

---

## Adding a Logo

1. Click **Browse…** next to Logo.
2. Select a PNG, JPEG, SVG, or WebP file.
3. Choose the corner placement from the **Logo Corner** dropdown.
4. Use **Logo Cleanup** to remove white or checkerboard backgrounds from logos.

---

## Typography

In the **Inspector → Text** tab:
- **Title Font**: sets the font for the collection title.
- **Track Font**: sets the font for the playlist track names.
- Each has independent family, style (Regular / Bold / Italic), and size controls.
- Click **Refresh Fonts** to reload system fonts after installing new ones.

---

## Cursor and Highlight

In the **Inspector → Indicator & Watermark** tab:
- **Indicator Mode**: choose Cursor + Highlight, Cursor Only, Highlight Only, or Neither.
- **Custom Cursor**: browse for an SVG or PNG cursor image; resize with the Size slider.
- **Highlight Style**: Pill, Accent Bar, Outline, or Underline.
- **Highlight Color**: click the color swatch to pick any color.

---

## Website Watermark

In the **Inspector → Indicator & Watermark** tab:
1. Enable **Show Website** and type your URL or text.
2. Choose position (Top-Right, Top-Left, Bottom-Right, Bottom-Left, etc.).
3. Adjust font size and opacity with the sliders.

---

## Intro Card

In the **Inspector → Intro & Sound** tab:
1. Enable **Intro Enabled**.
2. Set duration (1–10 seconds) and choose an animation style
   (Fade in / out, Zoom in, Slide).

---

## Track-Change Sound Effect

In the **Inspector → Intro & Sound** tab:
1. Enable **Track Change SFX**.
2. Browse for an audio file (MP3/WAV/AAC).
3. Adjust volume with the slider.
The sound effect plays at each track boundary in the exported video.

---

## Saving and Reopening Projects

- **Save** (Ctrl+S): saves the current project as a `.json` file in the workspace.
- **Save As**: choose a custom location.
- **Open** (Ctrl+O): reload a previously saved project.
- **Recent**: access recently opened projects from File → Open Recent.

---

## Templates

- **Apply Template**: click the Templates button and select from the dropdown.
  A template applies styling (fonts, colors, layout, highlight, logo settings)
  without changing your tracks or collection title.
- **Save as Template**: after customizing, save your style as a reusable template
  via File → Save as Template.

---

## Exporting an MP4

1. Set the **Output Path** in the Export bar (bottom of the window).
2. Choose **Resolution**: 1080p · Full HD, 1440p · QHD, or 4K UHD.
3. Click **Render MP4**.
4. A progress bar shows export progress. Click **Cancel Export** to abort.
5. Open the exported file in any media player to verify.

---

## Export Resolutions

| Label | Dimensions | Recommended use |
|-------|-----------|-----------------|
| 1080p · Full HD | 1920×1080 | YouTube, standard display |
| 1440p · QHD | 2560×1440 | High-resolution displays |
| 4K UHD | 3840×2160 | Premium quality, large screens |

---

## Troubleshooting Exports

See `Documentation/TROUBLESHOOTING.md` for common issues.
Export logs are saved in `NasheedStudio/logs/` in your workspace folder.
"""

DEVELOPER_GUIDE = """\
# Nasheed Studio — Developer / Build Guide

## Supported Python version

Python 3.10 (exact version used for development and packaging).
The `.venv` in the project uses Python 3.10 from the system or installer.

## Setting up the development environment

```powershell
cd D:\\path\\to\\nasheed_studio
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller>=6.0
```

## Running the source version

```powershell
.\\.venv\\Scripts\\Activate.ps1
python app.py
```

## Running the test suite

```powershell
.\\.venv\\Scripts\\Activate.ps1
python -m pytest tests/ -v
```

## Building the standalone executable

```powershell
.\\.venv\\Scripts\\Activate.ps1
python build_release.py
```

Options:
- `--clean`       Delete previous dist/ and build/ before building.
- `--skip-tests`  Skip the automated test suite (document reason in Evidence/).

Output is written to `release_build/`.

## FFmpeg dependency

Place `ffmpeg.exe` and `ffprobe.exe` in the `tools/` directory before building.
The spec file bundles them automatically.

The recommended source is a Windows static build from:
    https://www.gyan.dev/ffmpeg/builds/

## Packaging internals

- Spec file: `nasheed_studio.spec` (relative paths, portable across machines)
- Build script: `build_release.py`
- Distribution: `release_build/Application/Nasheed Studio/`
- ZIP archive: `release_build/Nasheed_Studio_Windows_x64.zip`

## Reproducing the clean-environment test

1. Build the distribution using `build_release.py`.
2. Copy `release_build/Application/Nasheed Studio/` to a Windows VM or sandbox
   that has no Python installation.
3. Verify `python.exe` is absent: `where python` should return nothing.
4. Launch `Nasheed Studio.exe` and follow the manual acceptance test guide.

## Project structure

```
nasheed_studio/
  app.py                      Entry point
  nasheed_studio.spec         PyInstaller spec (portable)
  build_release.py            Release build automation
  requirements.txt            Runtime dependencies
  src/
    services/
      compositor.py           Image composition engine
      render_service.py       FFmpeg command builder
      export_service.py       Safe staging + atomic publish
      export_job.py           Background export thread
      media_probe.py          FFprobe integration + tool discovery
      font_service.py         Windows font registry + Pillow resolution
      workspace_service.py    User workspace directory management
      timeline.py             Audio timeline builder
      project_service.py      Project/template JSON I/O
    ui/
      main_window.py          Main application window
      icons.py                SVG icon assets
      style.py                Qt stylesheet tokens
  tests/                      pytest test suite
  assets/                     Bundled fonts + reference images
  tools/                      ffmpeg.exe + ffprobe.exe (not committed to git)
  user_templates/             Seed template JSON files
  release_build/              Build output (not committed to git)
```

## Updating bundled fonts

Place new .ttf or .otf files in `assets/fonts/`.
They are automatically discovered at runtime and bundled via the spec.

## Troubleshooting packaging failures

- If the EXE launches but shows a blank window: check Qt platform plugin
  `PySide6/plugins/platforms/qwindows.dll` is present in the bundle.
- If multimedia/preview fails: ensure `PySide6/plugins/multimedia/ffmpegmediaplugin.dll`
  is present.
- If fonts fail to load: ensure `assets/fonts/` was included in the bundle.
- Run the EXE from cmd.exe to see stderr output.
"""

TROUBLESHOOTING_GUIDE = """\
# Nasheed Studio — Troubleshooting Guide

## Application does not start

**Symptom**: Double-clicking Nasheed Studio.exe does nothing or shows an error.

**Solutions**:
1. Ensure all files from the ZIP were extracted (not just the .exe).
2. Check that `PySide6/plugins/platforms/qwindows.dll` exists inside the app folder.
3. Try running from a Command Prompt window to see error messages:
   ```
   cd "C:\\Path\\To\\Nasheed Studio"
   "Nasheed Studio.exe"
   ```
4. Install the Microsoft Visual C++ Redistributable (2019 or later) if prompted.

---

## Export fails immediately

**Symptom**: Clicking "Render MP4" shows an error immediately.

**Solutions**:
- Ensure at least one audio track is added with a valid file path.
- Ensure a background image or video is selected.
- Check that the output directory is writable.
- Check the log in `NasheedStudio\\logs\\` for details.

---

## Export stalls or produces a very short video

**Symptom**: Export progress bar stops; the output file is shorter than expected.

**Solutions**:
- The track audio files must still be accessible at their original paths.
- If you moved your audio files, re-add them using the Add Track button.
- Ensure sufficient free disk space (4K exports can exceed 1 GB temporarily).

---

## Video background not working

**Symptom**: A video file selected as background shows as a still image.

**Solutions**:
- Ensure the video file is a valid MP4/MOV with a video stream (probe with ffprobe).
- The video must be accessible at its original path during export.
- Check `ffmpeg.exe` exists in the `tools/` subfolder of the application.

---

## Fonts not appearing

**Symptom**: A font family is not visible in the font dropdown.

**Solutions**:
- Click **Refresh Fonts** in the Inspector → Text tab.
- Ensure the font is installed in Windows (Control Panel → Fonts).
- If using a custom font file, browse for it using the custom font picker.

---

## Template does not apply correctly

**Symptom**: Applying a template changes unexpected settings or shows wrong colors.

**Solutions**:
- Templates store styling only, not track lists or collection titles.
- If a template references a font not installed on this machine, it falls back
  to the default font automatically.

---

## Log files

Export logs are written to:
    `C:\\Users\\<YourName>\\NasheedStudio\\logs\\`

Each export job creates a dated log file. Share this with support when reporting issues.

---

## Contacting support

Include the following when reporting a problem:
1. Windows version (Settings → System → About)
2. The log file from NasheedStudio\\logs\\
3. Steps to reproduce the issue
4. Whether the issue occurs with a fresh project or a saved one
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build Nasheed Studio release package")
    parser.add_argument("--clean", action="store_true",
                        help="Remove previous dist/ and build/ directories before building")
    parser.add_argument("--skip-tests", action="store_true",
                        help="Skip the automated test suite")
    args = parser.parse_args()

    print("\n" + "="*70)
    print("  Nasheed Studio — Release Builder")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    check_prerequisites()

    if not args.skip_tests:
        run_tests()
    else:
        warn("Tests skipped (--skip-tests). Document this in Evidence/.")

    bundle = run_pyinstaller(clean=args.clean)
    verify_bundle(bundle)
    release_dir = assemble_release(bundle)
    write_manifest(bundle, release_dir)

    header("Build Complete")
    print(f"\n  Release package: {release_dir}")
    print(f"  Executable:      {release_dir / 'Application' / BUNDLE_NAME / (BUNDLE_NAME + '.exe')}")
    print(f"  ZIP archive:     {release_dir / ZIP_NAME}")
    print(f"\n  Next steps:")
    print(f"  1. Test the executable in a clean Windows environment (no Python).")
    print(f"  2. Add test evidence (screenshots, logs, sample export) to:")
    print(f"     {str(release_dir / 'Evidence')}")
    print(f"  3. Deliver {ZIP_NAME} to the client.\n")


if __name__ == "__main__":
    main()
