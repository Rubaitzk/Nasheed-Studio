# Nasheed Studio — MVP starter

A Windows desktop application for composing playlist-style Nasheed videos and exporting MP4 using FFmpeg.

## Current MVP features

- Choose a background image and optional transparent logo.
- Add multiple audio tracks and read durations through FFprobe.
- Edit visible playlist titles by double-clicking a track.
- Reorder tracks with drag-and-drop or Move up / Move down.
- Select Cinematic, Minimal, and Two-column playlist layouts.
- Export 1080p, 1440p, or 4K UHD MP4 (H.264 video / AAC audio).
- Save and reopen project settings as JSON.
- Generate a time-synchronized active-row outline and cursor overlay.

## Requirements

- Windows 10/11 (recommended for the target deliverable)
- Python 3.11 or newer
- FFmpeg and FFprobe available on `PATH`, or place `ffmpeg.exe` and `ffprobe.exe` in a `tools/` folder at the project root.

## Setup on Windows

Open PowerShell in this folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Install FFmpeg from https://ffmpeg.org/download.html or a trusted Windows build, then confirm:

```powershell
ffmpeg -version
ffprobe -version
```

Run the app:

```powershell
python app.py
```

## Demo workflow

1. Choose a background image and optional logo.
2. Add at least three audio tracks.
3. Double-click a track to edit the displayed title.
4. Arrange the order.
5. Select a template and export resolution.
6. Choose an MP4 output path and click **Render MP4**.

## Important implementation notes

- The provided screenshots are visual references, not suitable as clean backgrounds because their text/logo is already baked in. Use a separate background image and logo for a clean composition.
- The render pipeline creates one base composition plus transparent active-row overlays, then uses FFmpeg to enable each overlay during the corresponding audio interval. Audio tracks are concatenated in playlist order.
- The UI preview is a lightweight composition preview. It currently shows the first track highlighted; it is not a full real-time playback preview.
- This is an MVP starter and needs validation against the client's exact assets and visual references before being represented as a finished deliverable.
- On Windows, verify FFmpeg's `overlay` and `concat` filters are present in the selected FFmpeg build.

## Suggested next steps

1. Test with three short audio clips and a separate background/logo.
2. Compare the rendered frame layout to the client's reference screenshots.
3. Refine template-specific positions, font sizes, and row spacing.
4. Add a proper playback scrubber / real-time preview if required.
5. Test long playlists and export duration/synchronization.
6. Package a Windows build with PyInstaller and bundled FFmpeg binaries after functional testing.
