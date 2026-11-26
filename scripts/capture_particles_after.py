import sys
import os
import time
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize, QPoint, QPointF
from PySide6.QtGui import QFontDatabase, QImage, QColor, QPainter, QPixmap

from src.ui.main_window import MainWindow
from src.ui.widgets.particle_canvas import ParticleOverlayWidget
from src.services.particle_service import (
    PARTICLE_STYLES,
    STYLE_WIND_STREAKS,
    generate_particle_loop_video,
    create_wind_streak_particles,
    wind_streak_state,
)
from src.services.render_service import build_render_command


def zoom_nearest(img_pil: Image.Image, factor: int = 4) -> Image.Image:
    w, h = img_pil.size
    return img_pil.resize((w * factor, h * factor), Image.Resampling.NEAREST)


def make_comparison_image(before_img: Image.Image, after_img: Image.Image, title: str) -> Image.Image:
    """Create a side-by-side comparison image labeled 'BEFORE (Aliased)' vs 'AFTER (Anti-Aliased)'."""
    w1, h1 = before_img.size
    w2, h2 = after_img.size
    h = max(h1, h2)
    header_h = 36
    total_w = w1 + w2 + 20
    total_h = h + header_h

    comp = Image.new("RGBA", (total_w, total_h), (20, 24, 32, 255))
    draw = ImageDraw.Draw(comp)
    
    # Title & labels
    draw.text((10, 8), f"{title} -- BEFORE (Aliased)", fill=(248, 113, 113, 255))
    draw.text((w1 + 20, 8), f"{title} -- AFTER (Anti-Aliased)", fill=(52, 211, 153, 255))

    comp.paste(before_img, (10, header_h))
    comp.paste(after_img, (w1 + 20, header_h))
    return comp


def main():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication(sys.argv)

    font_path = "C:/Windows/Fonts/segoeui.ttf"
    if os.path.exists(font_path):
        QFontDatabase.addApplicationFont(font_path)

    out_dir = ROOT_DIR / "tests" / "artifacts" / "particles_aa"
    out_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    print(f"Output directory: {out_dir}")
    print(f"FFmpeg binary: {ffmpeg_bin}")

    # 1. Performance benchmark: Preview frame times across styles (AFTER)
    print("\n--- Measuring Preview Frame Times (After Fix) ---")
    timing_after = {}
    overlay = ParticleOverlayWidget()
    overlay.resize(1280, 720)
    overlay.set_enabled(True)
    overlay.show()
    app.processEvents()

    for style in PARTICLE_STYLES:
        overlay.set_particle_style(style)
        overlay.set_particle_count(80)
        for _ in range(10):
            overlay._update_particles()
            app.processEvents()

        times = []
        for _ in range(60):
            t0 = time.perf_counter()
            overlay._update_particles()
            overlay.repaint()
            app.processEvents()
            t1 = time.perf_counter()
            times.append((t1 - t0) * 1000.0)
        avg_ms = float(np.mean(times))
        p95_ms = float(np.percentile(times, 95))
        timing_after[style] = (avg_ms, p95_ms)
        print(f"  Style '{style}': avg={avg_ms:.3f} ms, p95={p95_ms:.3f} ms")

    # 2. Render Path performance: Wind Streaks 5s render time (AFTER)
    print("\n--- Measuring Render Path Loop Generation Time (After Fix) ---")
    tmp_mov = out_dir / "after_wind_streaks_temp.mov"
    t_start = time.perf_counter()
    generate_particle_loop_video(
        output_path=str(tmp_mov),
        duration=5.0,
        fps=30,
        width=1280,
        height=720,
        style="Wind Streaks",
        quantity=80,
        speed=2,
        color="#FFFFFF",
        angle=225.0,
        ffmpeg_bin=ffmpeg_bin
    )
    t_end = time.perf_counter()
    render_time_s = t_end - t_start
    per_frame_ms = (render_time_s / 150.0) * 1000.0
    print(f"  Rendered 150 frames in {render_time_s:.2f}s ({per_frame_ms:.2f} ms/frame)")
    if tmp_mov.exists():
        tmp_mov.unlink()

    # 3. Capture Preview frames at 1x and 2x devicePixelRatio
    print("\n--- Capturing Preview After Crops ---")
    win = MainWindow()
    win.show()
    win.resize(1280, 720)
    app.processEvents()

    sample_bg = str((ROOT_DIR / "tests/fixtures/images/sample_bg.png").resolve())
    sample_tone = str((ROOT_DIR / "tests/fixtures/audio/sample_tone.wav").resolve())
    if os.path.exists(sample_bg):
        win.background_path = sample_bg
    if os.path.exists(sample_tone):
        win.tracks = [
            {"path": sample_tone, "title": "01. Beautiful Nasheed Track - Artist Name", "duration": 180.0},
            {"path": sample_tone, "title": "02. Second Nasheed Track - Vocals Only", "duration": 200.0}
        ]
        win.collection_title.setText("BISMILLAH - NASHEED TITLE")
        win._committed_title = "BISMILLAH - NASHEED TITLE"
        win._refresh_tracks()

    win.particles_check.setChecked(True)
    win.particles_style_combo.setCurrentText("Wind Streaks")
    win.particles_count_spin.setValue(80)
    win.particles_speed_spin.setValue(2)
    win.particles_angle_spin.setValue(225.0)
    win._refresh_preview()
    app.processEvents()

    canvas = win.preview_frame
    part_overlay = win.particle_overlay
    part_overlay.show()
    app.processEvents()

    for _ in range(15):
        part_overlay._update_particles()
    app.processEvents()

    # 1x preview
    p_1x = canvas.grab()
    p_1x.save(str(out_dir / "after_preview_full_1x.png"))
    img_1x_pil = Image.open(str(out_dir / "after_preview_full_1x.png"))

    # 2x DPR preview
    w_px = canvas.width() * 2
    h_px = canvas.height() * 2
    dpr_img = QImage(w_px, h_px, QImage.Format.Format_ARGB32_Premultiplied)
    dpr_img.setDevicePixelRatio(2.0)
    dpr_img.fill(0)
    canvas.render(dpr_img, QPoint())
    dpr_img.save(str(out_dir / "after_preview_full_2x.png"))
    img_2x_pil = Image.open(str(out_dir / "after_preview_full_2x.png"))

    print("Extracting preview after crops...")
    particles = part_overlay._particles
    if particles:
        p0 = particles[0]
        cx0, cy0 = int(round(p0.x)), int(round(p0.y))
        box0 = (max(0, cx0 - 40), max(0, cy0 - 40), min(canvas.width(), cx0 + 40), min(canvas.height(), cy0 + 40))
        crop_1x = img_1x_pil.crop(box0)
        crop_1x.save(str(out_dir / "after_wind_streaks_preview_1x_crop.png"))
        after_prev_1x_zoom = zoom_nearest(crop_1x, 4)
        after_prev_1x_zoom.save(str(out_dir / "after_wind_streaks_preview_1x_zoom4x.png"))
        print("  Saved after_wind_streaks_preview_1x_zoom4x.png")

        box0_2x = (box0[0] * 2, box0[1] * 2, box0[2] * 2, box0[3] * 2)
        crop_2x = img_2x_pil.crop(box0_2x)
        crop_2x.save(str(out_dir / "after_wind_streaks_preview_2x_crop.png"))
        after_prev_2x_zoom = zoom_nearest(crop_2x, 4)
        after_prev_2x_zoom.save(str(out_dir / "after_wind_streaks_preview_2x_zoom4x.png"))
        print("  Saved after_wind_streaks_preview_2x_zoom4x.png")

        # Particle over text
        text_particles = [p for p in particles if 300 <= p.x <= 900 and 150 <= p.y <= 450]
        if text_particles:
            pt = text_particles[0]
            cxt, cyt = int(round(pt.x)), int(round(pt.y))
            boxt = (max(0, cxt - 40), max(0, cyt - 40), min(canvas.width(), cxt + 40), min(canvas.height(), cyt + 40))
            crop_t = img_1x_pil.crop(boxt)
            crop_t.save(str(out_dir / "after_wind_streaks_over_text_crop.png"))
            after_text_zoom = zoom_nearest(crop_t, 4)
            after_text_zoom.save(str(out_dir / "after_wind_streaks_over_text_zoom4x.png"))
            print("  Saved after_wind_streaks_over_text_zoom4x.png")

    # 4. Render a full 5s MP4 video with nasheed_render pipeline (AFTER)
    print("\n--- Rendering 5s MP4 Export Video (After Fix) ---")
    project = {
        "title": "Particle AA Test",
        "collection_title": "NASHEED STUDIO AA TEST",
        "background": sample_bg,
        "background_path": sample_bg,
        "tracks": [
            {"path": sample_tone, "title": "Track 01", "duration": 5.0}
        ],
        "particles_enabled": True,
        "particles_style": "Wind Streaks",
        "particles_quantity": 80,
        "particles_speed": 2,
        "particles_size": 5,
        "particles_angle": 225.0,
        "particles_layer": "Above Text",
        "export_quality": "Ultra Detail · Master Quality (Recommended)",
        "resolution": "1280x720",
    }
    mp4_out = out_dir / "after_export_5s.mp4"
    with tempfile.TemporaryDirectory(prefix="nasheed_aa_after_") as tmp_dir:
        cmd, effective_out = build_render_command(project, Path(tmp_dir))
        cmd[-1] = str(mp4_out)
        print(f"Executing FFmpeg render command to {mp4_out}...")
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            print(f"Render failed: {res.stderr}")
        else:
            print(f"Rendered {mp4_out}")

    mp4_frame = out_dir / "after_mp4_frame_1s.png"
    if mp4_out.exists():
        cmd_ext = [ffmpeg_bin, "-y", "-ss", "00:00:01.000", "-i", str(mp4_out), "-vframes", "1", str(mp4_frame)]
        subprocess.run(cmd_ext, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Extracted {mp4_frame}")
        mp4_img = Image.open(str(mp4_frame))

        render_parts = create_wind_streak_particles(80, 1280, 720, angle_deg=225.0, speed_level=2, seed=42 + 80 + 2 + 225)
        rx, ry, ra, rr = wind_streak_state(render_parts[0], 1.0)
        rx_i, ry_i = int(round(rx)), int(round(ry))
        if 0 <= rx_i < 1280 and 0 <= ry_i < 720:
            mp4_box = (max(0, rx_i - 40), max(0, ry_i - 40), min(1280, rx_i + 40), min(720, ry_i + 40))
            crop_mp4 = mp4_img.crop(mp4_box)
            crop_mp4.save(str(out_dir / "after_wind_streaks_render_mp4_crop.png"))
            after_mp4_zoom = zoom_nearest(crop_mp4, 4)
            after_mp4_zoom.save(str(out_dir / "after_wind_streaks_render_mp4_zoom4x.png"))
            print("  Saved after_wind_streaks_render_mp4_zoom4x.png")

    # 5. Capture standalone render crops for EVERY particle style (AFTER)
    print("\n--- Capturing Render Path After for ALL Styles ---")
    for style_name in PARTICLE_STYLES:
        slug = style_name.lower().replace(" ", "_").replace("&", "and").replace("-", "_")
        mov_path = out_dir / f"after_style_{slug}.mov"
        generate_particle_loop_video(
            output_path=str(mov_path),
            duration=2.0,
            fps=30,
            width=640,
            height=360,
            style=style_name,
            quantity=50,
            speed=2,
            color="#38BDF8",
            angle=225.0,
            ffmpeg_bin=ffmpeg_bin
        )
        frame_path = out_dir / f"after_style_{slug}_frame.png"
        cmd_f = [ffmpeg_bin, "-y", "-ss", "00:00:00.500", "-i", str(mov_path), "-vframes", "1", str(frame_path)]
        subprocess.run(cmd_f, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        frm_img = Image.open(str(frame_path)).convert("RGBA")
        alpha = np.array(frm_img)[:, :, 3]
        nz = np.nonzero(alpha > 30)
        if len(nz[0]) > 0:
            py, px = nz[0][len(nz[0]) // 2], nz[1][len(nz[1]) // 2]
            crop_box = (max(0, px - 30), max(0, py - 30), min(frm_img.width, px + 30), min(frm_img.height, py + 30))
            crop_s = frm_img.crop(crop_box)
            crop_s.save(str(out_dir / f"after_{slug}_crop.png"))
            after_style_zoom = zoom_nearest(crop_s, 4)
            after_style_zoom.save(str(out_dir / f"after_{slug}_zoom4x.png"))
            print(f"  Saved after_{slug}_zoom4x.png")

            # Generate side-by-side comparison with before image
            before_zoom_path = out_dir / f"before_{slug}_zoom4x.png"
            if before_zoom_path.exists():
                before_img = Image.open(str(before_zoom_path))
                comp_img = make_comparison_image(before_img, after_style_zoom, f"Style: {style_name}")
                comp_img.save(str(out_dir / f"compare_{slug}.png"))
                print(f"  Saved compare_{slug}.png")

    # Generate Wind Streaks comparisons
    for name, title in [
        ("wind_streaks_render_mp4", "Wind Streaks (MP4 Render)"),
        ("wind_streaks_preview_1x", "Wind Streaks (Preview 1x)"),
        ("wind_streaks_preview_2x", "Wind Streaks (Preview 2x DPR)"),
        ("wind_streaks_over_text", "Wind Streaks (Over Text)"),
    ]:
        b_p = out_dir / f"before_{name}_zoom4x.png"
        a_p = out_dir / f"after_{name}_zoom4x.png"
        if b_p.exists() and a_p.exists():
            bi = Image.open(str(b_p))
            ai = Image.open(str(a_p))
            ci = make_comparison_image(bi, ai, title)
            ci.save(str(out_dir / f"compare_{name}.png"))
            print(f"Saved compare_{name}.png")

    win.closeEvent = lambda e: e.accept()
    win.close()
    print("\n[SUCCESS] After captures, comparisons, and timings complete.")

if __name__ == "__main__":
    main()
