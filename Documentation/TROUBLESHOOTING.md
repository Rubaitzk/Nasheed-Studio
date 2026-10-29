# Nasheed Studio — Troubleshooting & Diagnostics Guide

## 1. Application Startup Issues

### Symptom: Double-clicking `Nasheed Studio.exe` does not launch or shows an error dialog.

**Potential Causes & Solutions:**
1. **Running directly from an un-extracted archive:**
   - Ensure you extracted the entire delivery archive (`final_deliverable.zip` or `Nasheed_Studio_Complete_Project_v1.0.zip`) using **Right-Click → Extract All…** before launching. Running executable files from inside Windows Compressed Folders without extraction prevents required DLLs from loading.
2. **Missing Visual C++ Runtime:**
   - If Windows displays a missing DLL alert (e.g., `MSVCP140.dll` or `VCRUNTIME140.dll`), install the official [Microsoft Visual C++ Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe).
3. **Inspect Console Diagnostics:**
   - If the application closes silently, launch it from Command Prompt to inspect startup output:
     ```cmd
     cd "C:\Path\To\final_deliverable\Application\Nasheed Studio"
     "Nasheed Studio.exe"
     ```

---

## 2. Process Lifecycle & System CPU Diagnostics

### Symptom: Suspected background CPU usage or leftover processes after closing the application.

**Architecture & Protections:**
- Nasheed Studio incorporates a dedicated `ProcessManager` (`src/services/process_manager.py`) with Windows `CREATE_NO_WINDOW` enforcement.
- All child subprocesses (`ffmpeg.exe`, `ffprobe.exe`) are tracked in an active registry and encapsulated within a Win32 Job Object configured with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
- When you close Nasheed Studio, Windows automatically terminates the entire process tree.

**Verification Steps in Windows Task Manager:**
1. Press `Ctrl + Shift + Esc` to open **Task Manager**.
2. Click the **Details** tab.
3. Verify that no instances of `Nasheed Studio.exe`, `ffmpeg.exe`, or `ffprobe.exe` remain running.
4. If you see unrelated `conhost.exe` (Console Window Host) processes consuming CPU, check their **Command line** column (Right-click column headers → Select columns → Check "Command line"). Nasheed Studio runs completely without console windows; background `conhost.exe` processes typically belong to IDE terminal wrappers, background update services, or Windows terminal sessions.

---

## 3. Video Quality vs. File Size Considerations

### Symptom: "The rendered MP4 file is ~850 MB for a 10-minute video."

**Explanation:**
- By default, Nasheed Studio renders in **Ultra Detail · Master Quality** (unconstrained CRF 18 with 320 kbps AAC stereo audio).
- For complex looping video backgrounds featuring dark gradients, starry skies, particles, smoke, or film grain, standard aggressive video compression causes severe macroblocking, color banding, and pixel smearing.
- At CRF 18, FFmpeg encodes at approximately **12.0 to 14.0 Mbps total bitrate**, producing visually lossless, YouTube-master-quality video (~85–90 MB per minute of 1080p footage).
- This file size is completely normal and optimal for high-fidelity content creation.

**Selecting a Smaller File Size:**
If you require smaller files for fast sharing or limited bandwidth, you can adjust the export settings:
- **Ultra Detail · Master Quality (Default):** CRF 18, 320 kbps audio → ~850 MB for 10 min. (Maximum fidelity, zero banding).
- **High Quality · Balanced:** CRF 22, 192 kbps audio → ~400–450 MB for 10 min. (Balanced size and quality).
- **Web / Fast:** CRF 26, 128 kbps audio → ~200–250 MB for 10 min. (Compact preview/social media size).

---

## 4. Export & Rendering Diagnostics

### Symptom: Export fails immediately upon clicking "Render MP4".

**Checklist:**
1. **Audio Track Accessibility:** Confirm that the audio files added to the playlist have not been moved, deleted, or renamed on your disk.
2. **Background Selected:** Ensure a valid background image or video is loaded in the Inspector.
3. **Destination Write Permissions:** Ensure your chosen output path is not in a write-protected directory (e.g., `C:\Windows\` or root `C:\`). Save to your Desktop, Videos folder, or Documents.
4. **Log Inspection:** Check the latest log file generated in your workspace:
   `C:\Users\<YourUsername>\NasheedStudio\logs\`

### Symptom: Export stalls or the output video is shorter than the playlist.

**Checklist:**
1. **Disk Space:** Check that your target drive has at least 2 GB of free disk space for staging temporary render files.
2. **Corrupted Audio Header:** Certain non-standard MP3s have damaged Xing/VBR headers that report inaccurate durations. Re-encode the audio file to standard WAV or MP3 using Audacity or an audio converter.

---

## 5. Background Video & Looping Issues

### Symptom: Video background does not loop or appears static.

**Checklist:**
1. **Video Container:** Ensure the video file is a valid `.mp4` or `.mov` with an H.264 video stream.
2. **Resolution Matching:** If importing extreme high-resolution video clips (e.g., 8K), rendering will require additional RAM. 1080p or 4K background video clips are optimal.
3. **Bundled FFmpeg:** Ensure the `tools/` folder inside `Application/Nasheed Studio/` contains `ffmpeg.exe` and `ffprobe.exe`.

---

## 6. Fonts and Typography

### Symptom: A newly installed Windows font does not appear in the font dropdown.

**Solution:**
1. Install the font in Windows (Right-click `.ttf` / `.otf` file → **Install for all users**).
2. In Nasheed Studio, go to the **Inspector → Text** tab and click **Refresh Fonts**.
3. If using custom font files directly, use the custom font file picker button to load the font file directly into the project.

---

## 7. Workspace Reset

If you ever wish to reset application preferences and template caches to factory defaults:
1. Close Nasheed Studio.
2. Navigate to `C:\Users\<YourUsername>\` and rename or delete the `NasheedStudio` folder.
3. Relaunch Nasheed Studio. A clean workspace will be generated automatically.
