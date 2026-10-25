"""Standalone Windows Executable Build Script for Nasheed Studio.

Packages the application using PyInstaller with bundled FFmpeg, FFprobe,
and all required media and styling resources into a portable distribution.
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
TOOLS_DIR = ROOT_DIR / "tools"
ASSETS_DIR = ROOT_DIR / "assets"


def build_standalone():
    print(f"=== Building Nasheed Studio Standalone Windows Package ===")
    print(f"Root Directory: {ROOT_DIR}")

    # Ensure tools exist
    ffmpeg_exe = TOOLS_DIR / "ffmpeg.exe"
    ffprobe_exe = TOOLS_DIR / "ffprobe.exe"
    if not ffmpeg_exe.is_file() or not ffprobe_exe.is_file():
        raise FileNotFoundError(
            f"Required binaries ffmpeg.exe and ffprobe.exe must be present in {TOOLS_DIR}"
        )

    # PyInstaller command arguments
    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "Nasheed Studio",
        "--add-data", f"{TOOLS_DIR};tools",
        "--add-data", f"{ASSETS_DIR};assets",
        "--hidden-import", "PySide6.QtSvg",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageDraw",
        "--hidden-import", "PIL.ImageFont",
        "--hidden-import", "PIL.ImageOps",
        "--hidden-import", "PIL.ImageFilter",
        str(ROOT_DIR / "app.py"),
    ]

    print("Running PyInstaller...")
    res = subprocess.run(pyinstaller_cmd, cwd=str(ROOT_DIR))
    if res.returncode != 0:
        raise RuntimeError(f"PyInstaller build failed with exit code {res.returncode}")

    target_app_dir = DIST_DIR / "Nasheed Studio"
    print(f"Build complete at: {target_app_dir}")

    # Ensure tools directory is also directly adjacent in the distribution folder
    dist_tools_dir = target_app_dir / "tools"
    dist_tools_dir.mkdir(parents=True, exist_ok=True)
    if not (dist_tools_dir / "ffmpeg.exe").exists():
        shutil.copy2(ffmpeg_exe, dist_tools_dir / "ffmpeg.exe")
    if not (dist_tools_dir / "ffprobe.exe").exists():
        shutil.copy2(ffprobe_exe, dist_tools_dir / "ffprobe.exe")

    # Copy Launch Guide into distribution folder
    guide_src = ROOT_DIR / "packaging" / "DISTRIBUTION_README.txt"
    if guide_src.is_file():
        shutil.copy2(guide_src, target_app_dir / "README.txt")

    # Create portable ZIP distribution
    zip_path = DIST_DIR / "Nasheed_Studio_Windows_x64.zip"
    print(f"Creating portable zip archive: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(target_app_dir):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(DIST_DIR)
                zf.write(full_path, rel_path)

    print(f"=== Standalone Windows Distribution Ready: {zip_path} ===")
    return target_app_dir, zip_path


if __name__ == "__main__":
    build_standalone()
