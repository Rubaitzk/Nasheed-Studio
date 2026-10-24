# Nasheed Collection Video Automation — Agent Context & Project Brief

> **Read this file in full before inspecting or changing the project. It is the source of truth for scope, deliverables, constraints, and working rules. Keep it in the project root.**

---

## 1. Project summary

A **standalone Windows desktop application** that automates creating "nasheed collection" videos: the user imports a background image, a logo, and multiple audio tracks, arranges and titles them, customizes a playlist overlay with a cursor and/or highlight that follows the currently playing track, and exports a finished **MP4** in 1080p, 1440p (QHD), or 4K UHD.

- A **demo already exists** and was shown to the buyer. Work now continues from that demo toward the full delivery.
- **Commercial terms:** 12-day delivery, two revisions (each revision = one consolidated set of adjustments to the delivered build, within agreed scope).
- **Current phase:** stabilize the demo, then implement the complete feature set, then polish, package, and hand over.

---

## 2. Scope status: EVERYTHING IN THIS BRIEF IS APPROVED

Every original requirement, every later buyer addition, and every previously unresolved implementation item listed here is **approved and must be implemented**. Do **not** classify any of them as optional, out of scope, or "awaiting buyer approval", and do not ask for approval again for them.

If a genuine technical limitation arises, **report it and recommend a practical solution**. Never silently omit a requirement.

Avoid adding unrelated features outside this brief.

---

## 3. Requirements

### A. Original requirements (from the buyer's PDF)

**Project inputs**
- A1. Select a background image.
- A2. Import and position a logo.
- A3. Import multiple audio tracks.
- A4. Editable playlist title per track.
- A5. Separate main collection title.

**Playlist and synchronization**
- A6. Reorder tracks into the desired playback sequence.
- A7. Playlist layout customizable to resemble the buyer's reference examples.
- A8. Track transitions synchronized with **actual audio durations** and track order.

**Cursor and highlight**
- A9. Animated cursor indicates the currently playing track and advances when it ends.
- A10. Moving colored background highlight as an alternative to a cursor.
- A11. Independent cursor and highlight switches: cursor only, highlight only, both, or neither.

**Typography**
- A12. Read available fonts from the Windows font list; allow refreshing the list.
- A13. Separate font selectors and styles for the collection title and the track names.

**Sound and intro**
- A14. Optional track-change sound effect with volume control.
- A15. Optional customizable opening intro using the background, logo, collection title, and simple animation.

**Templates and export**
- A16. Save and reuse templates for repeated collections.
- A17. Export MP4 at 1080p, 1440p (QHD), and 4K UHD.

**Deliverables**
- A18. Standalone Windows application (no separate Python installation required).
- A19. Complete Python source code.
- A20. Install script, test script, and task-automation script.
- A21. Setup instructions.

### B. Later buyer additions (approved — implement)

- **B1. Replaceable, resizable cursor.** The buyer uploads their own cursor in **SVG or PNG** and can resize it. Not merely a built-in cursor with a size slider.
- **B2. Adjustable size for ALL on-video text.** Collection title, track names, website address, and any intro text.
- **B3. Website address in the corners.** Optional text placed in any upper/lower, left/right corner. Placement must account for the logo position so they never overlap (e.g. logo in one corner → website can use another). Provide clear placement controls.
- **B4. Standalone packaging confirmed.** The Windows app runs without the buyer installing Python.

### C. Previously open items — now decided and approved

| Item | Decision |
|---|---|
| Cursor/highlight styling | Custom cursor upload + resize; highlight color and opacity controls. |
| Sound effect file | Buyer selects their own sound file; adjustable volume; can be disabled. |
| Intro options | Enable/disable, adjustable duration, customizable background/logo/collection title, basic animation. |
| Supported file types | Audio: MP3, WAV. Images: JPG, JPEG, PNG. Cursors: SVG, PNG. Validate files before export. |
| Output frame rate | Default 30 FPS unless testing shows a specific need. |
| Long collections | Handle 30–60+ minute collections; show export progress; report failures; clean up after interrupted jobs. |
| Composition preview | Basic preview of assets, titles, playlist, cursor/highlight, and website placement before export. Do **not** claim real-time video playback unless it is implemented and tested. |
| Project save/load | Save and reopen a full editable project: track order, asset references, styling, intro/export settings. **Separate from templates.** |
| Revisions | Two, as agreed. |

---

## 4. Known bugs in the demo (fix FIRST)

### Bug A — Long filenames distort the layout *(fix first)*
Importing a logo or background with a long filename stretches the left panel and squeezes the other two panels.

**Fix direction:** constrained/proportional three-panel layout with minimum widths; filenames must not drive panel width; truncate with ellipsis; full name in tooltip/details; scroll inside the asset section instead of expanding the layout.
**Acceptance:** several assets with very long names; all three panels remain usable at the supported window size.

### Bug B — Selected audio becomes black with invisible text *(fix first)*
Selecting an audio item turns the row black; text cannot be read.

**Fix direction:** inspect selected/focused/hover/disabled styles, stylesheets, palettes, delegates; define explicit foreground/background for every state; keep the selection indicator visible.
**Acceptance:** filename, duration, and controls readable with sufficient contrast, with both mouse and keyboard selection.

### Bug C — Export keeps running after the app closes *(CRITICAL)*
After Export is clicked, processing continues even if the app or launching script is closed.

**Fix direction:**
- The app explicitly **owns** each export job and its FFmpeg/FFprobe subprocesses; no detached background work.
- Retain process handles/PIDs.
- On cancel, app shutdown, or failure: terminate the **whole process tree**. On Windows use a **Job Object** (or an equally robust strategy). Killing the Python parent does not necessarily kill children.
- Add a Cancel control; confirm when closing during export.
- Clean up temp files; the UI always reaches a terminal state (completed / failed / cancelled); prevent duplicate exports; never leave the UI stuck "busy".

**Acceptance:** start export → close app → verify in Task Manager that owned FFmpeg processes stop. Repeat for cancellation and an induced failure. **No orphaned process.**

---

## 5. UI policy

- **Now (Phase 1):** structural usability fixes only — stable three-panel layout/resizing, filename truncation and scrolling, readable selection colors, sensible placement of import/track-order/export controls, progress display, cancellation, clear errors.
- **Later (Phase 4):** visual polish — consistent typography/spacing/alignment, logical grouping (inputs / playlist / appearance / export), clear separation of asset selection from appearance settings, clean desktop look.
- **Do not redesign or rewrite the UI from scratch.** Improve incrementally and preserve the working workflow.

---

## 6. Architecture guidance

Keep the existing stack unless inspection reveals a concrete blocker. Planned stack: **Python, PySide6, FFmpeg/FFprobe, image utilities, JSON projects/templates, PyInstaller.** Verify what is actually present; do not assume.

```
PySide6 UI  → Inputs · Playlist · Styling · Preview · Export progress
     ↓
Application/project layer → Validation · Project/template persistence · Track timing · Settings
     ↓
Media layer (FFprobe, durations, asset prep)   |   Render layer (FFmpeg, overlays, intro, MP4)
     ↓
Windows packaging → Standalone build · Scripts · Docs · Tests
```

**Three rules**
1. **Track timing is the source of truth.** Each track's start/end derives from actual audio duration and the chosen order. Cursor and highlight use the same timeline.
2. **Project configuration is the source of truth for appearance.** Cursor asset/size, fonts, text sizes, logo position, website position, highlight settings, sound, intro, and export settings live together.
3. **Export jobs have explicit ownership and lifecycle.** The UI starts, monitors, cancels, and cleans up. Closing the app must never leave a rendering process behind.

Keep rendering logic **separate from UI event handlers** so the exporter is testable headlessly.

---

## 7. Implementation phases

| # | Phase | Contents | Exit gate |
|---|---|---|---|
| 0 | Audit (read-only) | Map architecture, root-cause the 3 bugs, requirement coverage matrix, test/packaging status, ordered plan | Audit reviewed |
| 1 | Foundation | Fix Bugs A/B/C, owned subprocesses, cancel/shutdown/cleanup, regression tests | Demo stable |
| 2 | Core workflow | Background/logo import, multi-track with titles + reorder, collection title, playlist layout, duration-based timeline, SVG/PNG cursor + size, independent cursor/highlight modes | Correct synchronization |
| 3 | Customization | Separate title/track fonts, all text sizes, logo + website corner placement, highlight color/opacity, transition sound + volume, intro | Settings affect rendered video |
| 4 | Workflow & UI | Composition preview, project save/load, templates, UI polish, validation of paths/missing files/unsupported inputs | Repeatable editing workflow |
| 5 | Delivery | 1080p/1440p/4K validation, timing/overlay/intro tests, long collections, standalone build, install/test/task scripts, source + docs, final acceptance on packaged app | Clean Windows install |

**Suggested 12-day schedule:** days 1–2 audit/bugs; 3–5 playlist/sync/cursor; 6–7 typography/website/sound/intro; 8–9 projects/templates/preview/UI; 10–11 render tests/resolutions/long tests/packaging; 12 final regression, docs, delivery check. If the demo is substantially incomplete, cut cosmetic work before compromising export reliability or core features.

---

## 8. Acceptance tests (minimum before delivery)

**UI and assets**
- Long background/logo filenames do not resize the three panels.
- Selected audio stays readable in all interaction states.
- Tracks can be added, removed, renamed, reordered.
- Missing/unsupported assets give actionable errors.

**Video correctness**
- Transitions follow actual audio durations and selected order.
- Cursor-only, highlight-only, both, and neither all work.
- Uploaded SVG and PNG cursors render correctly and resize as configured.
- Text, logo, and website respect chosen positions without unintended overlap.
- Sound effect and intro settings affect the final video as configured.

**Export lifecycle**
- Progress and failures reported accurately.
- Cancellation stops the process tree and cleans up temp resources.
- Closing during export follows the defined cancel/exit behavior.
- No orphaned FFmpeg process after shutdown or failure.
- 1080p, 1440p, 4K MP4 outputs validated.

**Persistence and delivery**
- Saved projects reopen with settings and track order intact.
- Templates are reusable independently of projects.
- Long collections tested (30–60+ minutes where practical).
- Packaged app runs on Windows without a separate Python install.
- Install, test, task-automation scripts and complete source included.

---

## 9. Rules for the coding agent

1. **Inspect before changing.** Decide whether to modify or replace a component only after reading the existing implementation. Use actual file paths and function/class names.
2. **A UI control is not a feature.** A setting counts as implemented only if it reaches the FFmpeg render pipeline. Trace and verify it.
3. **Prefer small, testable changes** over rewrites. Preserve the architecture unless a concrete blocker is shown.
4. **Never claim a test passed unless you ran it and saw the result.** Distinguish *failed* from *untested*.
5. **Be honest about limits.** Report technical limitations with a practical recommended solution.
6. **No unrelated features.** Do not expand beyond this brief.
7. **Safety:** no destructive commands; do not install/upgrade dependencies or change system settings without saying so first; do not start long exports that could leave processes running unless the lifecycle fix is in place and verified.
8. **Work in phases.** Do only the task given in the current prompt; stop at its exit gate.

### Required report after every task
- Files changed (paths).
- What was implemented and how it was verified.
- Tests run and their actual results; tests not run and why.
- Known limitations or blockers.
- Remaining tasks / what the next phase should be.

---

## 10. Deliverables checklist

- [ ] Standalone Windows application (PyInstaller or equivalent), tested without Python installed
- [ ] Complete Python source code
- [ ] Install script
- [ ] Test script
- [ ] Task-automation script
- [ ] Setup/usage instructions and handover documentation
- [ ] MP4 export validated at 1080p, 1440p, 4K UHD
- [ ] All acceptance tests in section 8 passed
