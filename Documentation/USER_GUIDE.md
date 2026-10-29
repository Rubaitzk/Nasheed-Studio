# Nasheed Studio — User Guide

## 1. Overview & Delivery Package

**Nasheed Studio** is a professional Windows desktop application built to automate the creation of high-definition Nasheed playlist videos with synchronized track indicators, multi-column layouts, customizable branding, and high-resolution MP4 export.

You have received the complete master project archive (`final_deliverable/`), which includes:
- **`Application/`**: The compiled, standalone Windows x64 application ready for immediate use without installing Python or FFmpeg.
- **`Source_Code/`**: The complete, clean Python source code for ongoing development, customization, and maintenance.
- **`Documentation/`**: Comprehensive guides (`USER_GUIDE.md`, `DEVELOPER_GUIDE.md`, `TROUBLESHOOTING.md`, `INSTALLATION.md`, `ACCEPTANCE_TEST_GUIDE.md`).
- **`Evidence/`**: Real-world rendering test outputs, audit logs, and frame-accurate verification captures.
- **`Templates/`**: Ready-to-use aesthetic design templates (JSON).
- **`Scripts/`**: Verification scripts and test suite runners.
- **`MANIFEST.md`**: SHA-256 integrity checksums for all distribution files.

---

## 2. Launching the Application

1. Open the **`Application\Nasheed Studio\`** directory.
2. Double-click **`Nasheed Studio.exe`**.
3. The application will start in under 5 seconds.
4. On first launch, Nasheed Studio automatically creates a dedicated local workspace folder at:
   `C:\Users\<YourUsername>\NasheedStudio\`

> [!NOTE]
> The standalone application bundles its own isolated Python runtime, PySide6 Qt libraries, and static FFmpeg 8.1 binaries. You do **not** need Python or any third-party codecs installed on your machine.

---

## 3. Project Management

- **Create a New Project:** Click **New** in the top toolbar or press `Ctrl+N`.
- **Save Project:** Click **Save** in the top toolbar or press `Ctrl+S`. Projects are saved as human-readable `.json` files in your workspace (`NasheedStudio/projects/`) or a folder of your choice.
- **Open Project:** Click **Open** or press `Ctrl+O` to load an existing `.json` project. All audio tracks, layout settings, typography, and background paths will be restored.
- **Recent Projects:** Quickly switch between recent files via **File → Open Recent**.

---

## 4. Managing Audio Tracks

1. Click the **+** (**Add Track**) button in the left Playlist pane.
2. Select one or more audio files (`.mp3`, `.wav`, `.aac`, `.flac`, `.m4a`).
3. Nasheed Studio automatically probes each audio file using bundled FFprobe and displays exact track durations.
4. **Rename Track:** Double-click any track in the playlist to rename its display title without modifying the original audio file.
5. **Reorder Tracks:** Click and drag any track up or down to adjust playback and visual sequence.
6. **Remove Track:** Select a track and click the **−** (**Remove Track**) button.

---

## 5. Setting Backgrounds (Images & Looping Video)

In the **Inspector → Layout & Assets** tab:
1. Click **Browse…** next to **Background**.
2. **Still Image Backgrounds:** Select any `.png`, `.jpg`, `.jpeg`, or `.webp` file. The image will be centered and scaled cleanly to 16:9.
3. **Looping MP4 Video Backgrounds:** Select any `.mp4` or `.mov` video file.
   - The rendering engine automatically loops the video background seamlessly to match the total duration of your playlist.
   - Audio from the background video is automatically muted so only your playlist audio tracks play.

---

## 6. Layout & Multi-Column Settings

In the **Inspector → Layout & Assets** tab:
- **Columns:** Choose between **1 Column** and **2 Columns**.
- **Column Spacing:** Adjust the horizontal gap between column 1 and column 2.
- **Playlist Width & Position:** Fine-tune the total width, vertical offset, and horizontal position of the playlist block on screen.
- **Live Preview:** Changes update instantly on the interactive 16:9 preview canvas.

---

## 7. Typography & Font Styling

In the **Inspector → Text** tab:
- **Collection Title:**
  - Type your playlist title in the **Collection Title** box (e.g., *"Heartfelt Nasheeds Collection"*).
  - Select font family, font size, color swatch, and font style (Regular, Bold, Italic).
- **Playlist Tracks:**
  - Select font family, size, color swatch, and font style independently for the track entries.
- **Bundled Fonts:** Ships with modern typography including Montserrat, Oswald, Bebas Neue, and Cinzel.
- **System Fonts:** Automatically enumerates all fonts installed on your Windows system. Click **Refresh Fonts** to reload after installing new system fonts.

---

## 8. Active Track Indicators & Custom Cursors

In the **Inspector → Indicator & Watermark** tab:
- **Indicator Mode:**
  - **Cursor + Highlight:** Displays both the pointer and the background highlight box.
  - **Highlight Only:** Displays only the background highlight box.
  - **Cursor Only:** Displays only the pointer cursor.
  - **Neither:** Clean text display with no active track indicator.
- **Highlight Styles:**
  - **Pill:** Modern rounded pill highlight.
  - **Rectangle:** Solid rectangular highlight box with adjustable padding.
  - **Outline:** Crisp border bounding box.
  - **Glass:** Frosted, translucent backdrop accent.
  - Full control over highlight color swatch, opacity slider, and margin padding.
- **Custom Animated Cursors:**
  - Choose between built-in pointer icons or browse for custom `.svg` or `.png` icons.
  - Adjust cursor size with the slider. The cursor vertical alignment is automatically normalized to font cap-height.

---

## 9. Brand Logo & Website Watermark

In the **Inspector → Indicator & Watermark** tab:
- **Brand Logo:**
  - Click **Browse…** to import your channel logo (`.png`, `.jpg`, `.svg`, `.webp`).
  - Select corner position: **Top-Left**, **Top-Right**, **Bottom-Left**, or **Bottom-Right**.
  - Adjust the **Scale** and **Opacity** sliders.
  - Use **Logo Cleanup** to automatically remove white or checkerboard backgrounds from logos.
- **Website Watermark:**
  - Enable **Show Website** and enter your channel URL or social handle.
  - Choose placement corner with automatic non-overlapping safety margins.
  - Adjust font size and opacity.

---

## 10. Intro Sequence & Track Transition SFX

In the **Inspector → Intro & Sound** tab:
- **Intro Sequence:**
  - Enable **Intro Enabled**.
  - Set duration (1 to 10 seconds).
  - Choose animation style: **Fade in / out**, **Zoom in**, or **Slide**.
  - Displays your collection title and subtitle with smooth transitions before the playlist starts.
- **Track Transition Sound Effect:**
  - Enable **Track Change SFX**.
  - Browse for an audio file (`.mp3` or `.wav`).
  - Adjust the volume slider. The sound effect plays cleanly at each track boundary.

---

## 11. Templates & Presets

- **Apply Built-in Templates:** Click the **Templates** button in the top toolbar to choose from curated channel aesthetics (e.g., *Monochrome Lion*, *Two-Column Warrior*, *Battlefield Knight*, *Glass Highlight*).
- **Save Custom Template:** Once you design a layout you love, select **File → Save as Template**. Give it a descriptive name to reuse it across future video projects.

---

## 12. Exporting MP4 & Encoding Quality Modes

### Export Configuration
1. In the bottom Export bar, click **Browse** next to **Output Path** and choose where to save your `.mp4` video.
2. Select **Resolution**:
   - **1080p · Full HD (1920×1080):** Recommended standard for YouTube and video platforms.
   - **1440p · QHD (2560×1440):** High-definition 2K display format.
   - **4K UHD (3840×2160):** Ultra-high definition mastering format.

### Quality Presets Explained

| Quality Preset | Video Encoding | Audio Encoding | Bitrate Range | Approximate Size (10 min video) | Best Used For |
|---|---|---|---|---|---|
| **Ultra Detail · Master Quality (Recommended)** | **CRF 18** (unconstrained, no bitrate choke) | **320 kbps** AAC Stereo | **~12.0 – 14.0 Mbps** | **~850 – 900 MB** | **Maximum visual fidelity**, preserving subtle particle effects, dark starry skies, film grain, and fine textures on looping video backgrounds with zero macroblocking. |
| **High Quality · Balanced** | CRF 22 (maxrate capped) | 192 kbps AAC Stereo | ~5.5 – 6.5 Mbps | ~400 – 450 MB | Standard YouTube uploads where balanced file size and fast upload speeds are preferred. |
| **Web / Fast** | CRF 26 (tighter caps) | 128 kbps AAC Stereo | ~2.5 – 3.5 Mbps | ~200 – 250 MB | Quick preview drafts, lightweight social media sharing, or constrained storage. |

### Rendering Workflow
3. Click **Render MP4**.
4. The progress bar displays real-time percentage progress and estimated time.
5. **Safe Cancellation:** If you need to stop rendering, click **Cancel Export**. The process manager will safely terminate the background render and remove the temporary `.part.mp4` staging file without leaving corrupted files.
6. When complete, a notification dialog will confirm the export, and the video will be ready for viewing or uploading.

---

## 13. Process Safety & Resource Management

Nasheed Studio features an enterprise-grade process management system:
- All child FFmpeg and FFprobe tasks run completely silently without pop-up command windows (`CREATE_NO_WINDOW`).
- Rendering processes are bound to Windows Win32 Job Objects. Closing the application or canceling an export guarantees 100% clean process termination with zero leftover `ffmpeg.exe`, `ffprobe.exe`, or `conhost.exe` background tasks.
