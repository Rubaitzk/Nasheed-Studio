# Nasheed Studio — Manual Acceptance Test Guide

**Purpose:** Allows the developer to independently verify the release candidate before the final client package is assembled.  
**Audience:** Developer / QA tester — no Python knowledge required.  
**Time estimate:** ~60–90 minutes for the full suite.

---

## Before You Start

### Environment requirement

> [!IMPORTANT]
> Run these tests on a machine that does **not** have Python installed.  
> If you are using your development machine, you must either use Windows Sandbox, a clean VM, or ensure the system Python and virtual-env are truly absent from `PATH`.  
> Verify: open Command Prompt and type `python --version` — it must say "not recognized" or "not found."

### Test setup

1. Copy or extract the master project ZIP (`final_deliverable.zip` or `Nasheed_Studio_Complete_Project_v1.0.zip`) to a test directory (e.g., `C:\TestNasheed\`).
2. Open the extracted folder and navigate to `Application\Nasheed Studio\` containing `Nasheed Studio.exe`.
3. Prepare these test assets beforehand (small files are fine for initial smoke tests):
   - One or more MP3 or WAV audio files (3–30 seconds each for quick tests)
   - One background image (JPEG or PNG, any size)
   - One MP4 video clip (5–30 seconds, any resolution) for the video background test
   - One PNG or SVG logo file
   - One PNG or SVG cursor image
   - One short MP3/WAV for the track-change sound effect

---

## Test 1 — Application Launch

**Steps:**
1. Double-click `Nasheed Studio.exe`.
2. Wait up to 10 seconds for the window to appear.

**Pass criteria:**
- The main window opens without errors.
- The window shows: top toolbar (New / Open / Save / Templates), playlist pane on the left, preview canvas in the center, inspector on the right, export bar at the bottom.
- No error dialog appears on startup.

**Fail indicators:**
- Window does not appear within 15 seconds.
- An error dialog mentioning "python", "dll", "module not found", or similar.
- A blank black window that does not respond.

---

## Test 2 — Create a New Project

**Steps:**
1. Click **New** in the top toolbar.
2. Observe the status bar (bottom-right) — it should show "Unsaved".

**Pass criteria:**
- The workspace is cleared; playlist is empty.
- Top bar shows an untitled project name and "Unsaved" pill.

---

## Test 3 — Add Audio Tracks

**Steps:**
1. Click the **+** (Add Track) button in the playlist pane.
2. Browse and select 2–4 audio files.
3. Observe the track list.

**Pass criteria:**
- Each track appears in the list with its filename as the title and a duration shown (e.g., "3:24").
- The status bar bottom shows total track count and cumulative duration.
- No error about "ffprobe" or duration.

**Fail indicators:**
- Duration shows "0:00" or "Unknown".
- An error dialog mentioning ffprobe or file not found.

---

## Test 4 — Rename a Track

**Steps:**
1. Double-click on a track name in the list.
2. Type a new name and press Enter.

**Pass criteria:**
- The track name updates in the list.
- The preview canvas updates to show the new name.

---

## Test 5 — Reorder Tracks

**Steps:**
1. Click and drag a track to a different position in the list.

**Pass criteria:**
- The track moves to the new position.
- The preview canvas updates to reflect the new order.

---

## Test 6 — Set Collection Title

**Steps:**
1. Type a title in the **Collection Title** field above the playlist.
2. Click **Apply Title**.

**Pass criteria:**
- The title appears in the preview canvas at the top.

---

## Test 7 — Select a Background Image

**Steps:**
1. In the Inspector panel → **Layout & Assets** tab, click **Browse…** next to Background.
2. Select a JPEG or PNG image.

**Pass criteria:**
- The preview canvas updates to show the image as background.
- No error dialog.

---

## Test 8 — Select an MP4 Video Background

**Steps:**
1. In the Inspector → **Layout & Assets** tab, click **Browse…** next to Background.
2. Select an MP4 file.

**Pass criteria:**
- The preview canvas shows a still frame from the video (first frame).
- A notice or indicator confirms it is a video background (tooltip or status message).
- No error dialog about ffprobe or video decoding.

**Fail indicators:**
- Error dialog mentioning "ffprobe not found" or "video stream".
- The preview stays blank.

---

## Test 9 — Add a Logo

**Steps:**
1. In the Inspector → **Layout & Assets** tab, click **Browse…** next to Logo.
2. Select a PNG image.
3. Try different positions from the **Logo Corner** dropdown (Top-Left, Top-Right, Bottom-Left, Bottom-Right).

**Pass criteria:**
- The logo appears in the selected corner of the preview canvas.
- Changing the corner moves it accordingly.

---

## Test 10 — Font Settings

**Steps:**
1. Go to the Inspector → **Text** tab.
2. Change the **Title Font** family (e.g., select "Arial" or "Montserrat").
3. Change the **Title Font Size** (e.g., set to 56).
4. Change the **Track Font** family to something different.
5. Change the **Track Font Size** (e.g., set to 28).

**Pass criteria:**
- The preview updates with each change.
- Title and track text use visibly different fonts and sizes if set differently.
- No "font not found" error.

---

## Test 11 — Cursor and Highlight Mode

**Steps:**
1. Go to the Inspector → **Indicator & Watermark** tab.
2. Try each **Indicator Mode**: Cursor + Highlight, Cursor Only, Highlight Only, Neither.
3. For **Custom Cursor**: click Browse and select a PNG or SVG file. Adjust the Size slider.
4. Try each **Highlight Style**: Pill, Accent Bar, Outline, Underline.
5. Click the **Highlight Color** swatch and pick a bright color.

**Pass criteria:**
- The preview reflects each mode change (cursor visible / hidden, highlight visible / hidden).
- Custom cursor appears resized in the preview.
- Highlight style and color update in the preview.

---

## Test 12 — Website Watermark

**Steps:**
1. In the Inspector → **Indicator & Watermark** tab, enable **Show Website**.
2. Type a URL or text (e.g., "www.nasheedstudio.com").
3. Try different positions (Top-Right, Bottom-Left, etc.).
4. Adjust the **Font Size** and **Opacity** sliders.

**Pass criteria:**
- The watermark text appears on the preview at the chosen position.
- Opacity slider affects transparency in the preview.

---

## Test 13 — Intro Settings

**Steps:**
1. Go to the Inspector → **Intro & Sound** tab.
2. Enable **Intro Enabled**.
3. Set duration to 3 seconds.
4. Try each animation: Fade in / out, Zoom in, Slide.
5. Click **Intro Preview** (if the button is visible in the preview toggle).

**Pass criteria:**
- Intro settings are accepted without errors.
- If a preview mode exists for intro, the preview card updates.

---

## Test 14 — Track-Change Sound Effect

**Steps:**
1. In the Inspector → **Intro & Sound** tab, enable **Track Change SFX**.
2. Click **Browse…** and select an MP3 or WAV file.
3. Adjust the **Volume** slider.

**Pass criteria:**
- The file is accepted without error.
- Volume slider moves without crashing.

---

## Test 15 — Save and Reopen Project

**Steps:**
1. With a project configured (tracks, background, title, fonts), press **Ctrl+S**.
2. Save to a folder on the Desktop.
3. Click **New** to clear the project.
4. Click **Open** (or Ctrl+O) and navigate to the saved file.

**Pass criteria:**
- The project saves without error (a `.json` file is created).
- After reopening, all tracks, title, font settings, background path, and logo path are restored.
- The preview matches the saved state.

**Fail indicators:**
- Error on save about "permission denied" or "unexpected error".
- Settings not restored after reopening.
- Application crashes.

---

## Test 16 — Apply a Template

**Steps:**
1. Create a basic project with at least 3 tracks and a title.
2. Click the **Templates** button in the top toolbar.
3. Select one of the available templates (e.g., "GYM Nasheeds", "Sad Nasheeds").
4. Click Apply.

**Pass criteria:**
- The template is applied: fonts, colors, layout, and highlight settings update.
- Track names and collection title are preserved.
- Preview updates to match the template style.

---

## Test 17 — Short Export (1080p)

> [!IMPORTANT]
> Do this test with 2–3 short audio clips (< 30 seconds each) first.
> Only move to longer exports after confirming this works.

**Steps:**
1. Set up a project: 2–3 short MP3s, a background image, a collection title.
2. In the Export bar at the bottom, set **Output Path** (click Browse and save to Desktop).
3. Set **Resolution** to **1080p · Full HD**.
4. Click **Render MP4**.
5. Watch the progress bar.
6. After completion, open the exported MP4 in Windows Media Player or VLC.

**Pass criteria:**
- Progress bar moves and shows percentage.
- Export completes without error dialog.
- Output file exists at the chosen path.
- The video plays in a media player.
- Each track is shown highlighted in sequence; the playlist advances with the audio.
- Audio is audible and synchronized with the visual track progression.
- Video is 1920×1080 (right-click the file → Properties → Details to check).

**Fail indicators:**
- Export dialog shows "FFmpeg error" or similar.
- Output file is 0 bytes or does not exist.
- Video plays but audio is absent.
- Only one track is shown (no progression).

---

## Test 18 — Export with MP4 Video Background (1080p)

**Steps:**
1. Change the background to an MP4 video file.
2. Export to 1080p as in Test 17.
3. Play the output in a media player.

**Pass criteria:**
- The video background loops or fills the full duration.
- Text overlay (title, tracks, highlight) appears on top of the moving video.
- Audio from the tracks plays; video background audio is muted.

---

## Test 19 — Export with Intro and SFX (1080p)

**Steps:**
1. Enable the Intro (3 seconds, Fade in / out).
2. Enable Track Change SFX with a valid sound file.
3. Export 2–3 short tracks at 1080p.
4. Play the output.

**Pass criteria:**
- A 3-second intro card appears at the start of the video.
- The sound effect plays at each track transition (audible click/chime).

---

## Test 20 — Export at 1440p

**Steps:**
1. Change Resolution to **1440p · QHD**.
2. Export the same short project.
3. Check output dimensions (right-click → Properties → Details).

**Pass criteria:**
- Export completes without error.
- Output video is 2560×1440.

---

## Test 21 — Export at 4K

> [!NOTE]
> This export is slower and the file will be larger. Use 2 very short clips (< 15 s each).

**Steps:**
1. Change Resolution to **4K UHD**.
2. Export.

**Pass criteria:**
- Export completes.
- Output is 3840×2160.
- No crash or out-of-memory error.

---

## Test 22 — Progress and Error Reporting

**Steps:**
1. Start an export.
2. Click **Cancel Export** before it completes.

**Pass criteria:**
- Export stops cleanly without crashing.
- No partial or corrupt output file is left at the output path.
- The application remains usable afterward.

**Error report capture (if export fails):**
1. Note the exact error message from the dialog.
2. Locate the log file: `C:\Users\<YourName>\NasheedStudio\logs\` and attach it.

---

## Test 23 — Close and Reopen

**Steps:**
1. With an unsaved project open, close the application.
2. Confirm any "unsaved changes" dialog.
3. Relaunch the application.

**Pass criteria:**
- The application closes cleanly.
- On relaunch, the application starts fresh (or optionally restores the last session, depending on implementation).
- No startup crash.

---

## Test 24 — Quality Preset Verification (Ultra Detail vs Balanced)

**Steps:**
1. Configure a 1080p project with an MP4 video background.
2. Render using the default **Ultra Detail · Master Quality** preset.
3. Open the output file in a media player and inspect visual fidelity (look for stars, smoke particles, film grain, and crisp track typography).
4. Probe the file bitrate using FFprobe:
   ```cmd
   tools\ffprobe.exe -v error -show_entries format=bit_rate -of default=noprint_wrappers=1 output.mp4
   ```

**Pass criteria:**
- The video displays sharp, pristine visual quality with zero macroblocking on dark gradients or starry backgrounds.
- Bitrate is approximately 11.0 to 14.0 Mbps.
- Audio bitrate is 320 kbps AAC stereo.

---

## Test 25 — Process Lifecycle & Zombie Process Verification

**Steps:**
1. Open Windows Task Manager (`Ctrl + Shift + Esc`) and switch to the **Details** tab.
2. In Nasheed Studio, start a 1080p render.
3. Observe `ffmpeg.exe` running without any black command prompt windows appearing.
4. Let the export finish (or click **Cancel Export** halfway).
5. Close Nasheed Studio.
6. In Task Manager Details, observe process status.

**Pass criteria:**
- No instances of `Nasheed Studio.exe`, `ffmpeg.exe`, or `ffprobe.exe` remain running.
- No zombie `conhost.exe` processes spawned by the application remain.
- System CPU usage returns to normal idle baseline.

---

## Test Result Summary Template

Copy and fill this in after testing:

```
Nasheed Studio Release Candidate — Acceptance Test Results
Date:
Windows version:
Python present: YES / NO
Application version / build date:

Test 1  — Launch:                    PASS / FAIL
Test 2  — New project:               PASS / FAIL
Test 3  — Add audio tracks:          PASS / FAIL
Test 4  — Rename track:              PASS / FAIL
Test 5  — Reorder tracks:            PASS / FAIL
Test 6  — Collection title:          PASS / FAIL
Test 7  — Background image:          PASS / FAIL
Test 8  — MP4 video background:      PASS / FAIL
Test 9  — Logo:                      PASS / FAIL
Test 10 — Font settings:             PASS / FAIL
Test 11 — Cursor and highlight:      PASS / FAIL
Test 12 — Website watermark:         PASS / FAIL
Test 13 — Intro settings:            PASS / FAIL
Test 14 — Track-change SFX:          PASS / FAIL
Test 15 — Save and reopen:           PASS / FAIL
Test 16 — Apply template:            PASS / FAIL
Test 17 — Short export 1080p:        PASS / FAIL
Test 18 — Video background export:   PASS / FAIL
Test 19 — Intro + SFX export:        PASS / FAIL
Test 20 — Export 1440p:              PASS / FAIL
Test 21 — Export 4K:                 PASS / FAIL
Test 22 — Progress and cancel:       PASS / FAIL
Test 23 — Close and reopen:          PASS / FAIL
Test 24 — Quality preset verify:     PASS / FAIL
Test 25 — Process lifecycle cleanup: PASS / FAIL

Failures / notes:
[describe any failures here]

Attachments:
- Screenshots: [list]
- Export logs: [path]
- Sample exported MP4: [path]
```

---

## What to Do with Results

- **All tests pass**: Proceed to final client delivery. Add screenshots and the sample export to `release_build/Evidence/`.
- **Minor failures (cosmetic, non-blocking)**: Document in the manifest. Deliver with a note to the client.
- **Blocking failures** (crash, export produces no output, ffmpeg not found): Report immediately. Do not deliver until resolved.
