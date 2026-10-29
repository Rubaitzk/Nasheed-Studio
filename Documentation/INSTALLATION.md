# Nasheed Studio — Installation & Quick Start Guide

## System Requirements

- **Operating System:** Windows 10 (version 1903 or later) or Windows 11 (64-bit)
- **Processor:** x64-compatible dual-core processor (quad-core or higher recommended for 4K rendering)
- **Memory (RAM):** 4 GB minimum (8 GB or more recommended)
- **Graphics:** Direct3D 11-compatible GPU (for hardware-accelerated preview rendering)
- **Storage:** ~700 MB free space for application binaries + space for projects and video exports
- **External Dependencies:** **None required.** Python 3.10 and FFmpeg 8.1 are pre-bundled.

---

## Package Structure

The delivery archive contains the complete master project structure:

```
final_deliverable/
├── Application/              # Standalone Windows application (ready to run)
│   └── Nasheed Studio/
│       ├── Nasheed Studio.exe# Main executable
│       ├── _internal/        # Bundled Python runtime and Qt libraries
│       └── tools/            # Static FFmpeg and FFprobe binaries
├── Source_Code/              # Full, clean Python source code
├── Documentation/            # Complete user and developer manuals
├── Evidence/                 # Real-world rendering test outputs and audit logs
├── Templates/                # Production design templates (JSON)
├── Scripts/                  # Automated verification and build helpers
└── MANIFEST.md               # SHA-256 integrity checksums
```

---

## Quick Start (3 Steps)

### Step 1: Extract the Delivery Archive
1. Download the master delivery zip file (`final_deliverable.zip` or `Nasheed_Studio_Complete_Project_v1.0.zip`).
2. Right-click the `.zip` file and select **Extract All…**.
3. Choose a folder on your computer (e.g., `C:\Nasheed Studio\` or your Desktop).

> [!IMPORTANT]
> Always extract the zip before running. Do not run `Nasheed Studio.exe` directly from inside Windows Compressed Folders.

### Step 2: Launch the Executable
1. Open the extracted folder.
2. Navigate into **`Application\Nasheed Studio\`**.
3. Double-click **`Nasheed Studio.exe`**.

### Step 3: Start Creating
- The application will initialize and create your personal workspace at:
  `C:\Users\<YourUsername>\NasheedStudio\`
- Drag and drop your audio tracks into the playlist pane, select a background image or video, customize your typography, and click **Render MP4**!

---

## Portability & Uninstallation

- **100% Portable:** Nasheed Studio writes no registry keys and requires no administrative privileges. You can run it from any folder, external SSD, or USB flash drive.
- **Uninstallation:** Simply delete the extracted folder. To also remove saved user projects and export logs, delete the `C:\Users\<YourUsername>\NasheedStudio\` folder.
