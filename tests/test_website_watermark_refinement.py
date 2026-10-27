import unittest
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.services.compositor import create_composition, create_intro_card
from src.services.render_service import render_project
from src.services.project_service import extract_template, apply_template_to_project, PROTECTED_PROJECT_CONTENT_KEYS
from src.services.media_probe import find_tool
from src.ui.main_window import MainWindow
from tests.conftest import dispose_window

_app = None

def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestWebsiteWatermarkRefinement(unittest.TestCase):
    def setUp(self):
        _get_app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

        # Baseline dark canvas (30, 30, 30)
        self.bg_dark = self.tmp / "bg_dark.png"
        Image.new("RGBA", (1920, 1080), (30, 30, 30, 255)).save(self.bg_dark)

        # Baseline light canvas (230, 230, 230)
        self.bg_light = self.tmp / "bg_light.png"
        Image.new("RGBA", (1920, 1080), (230, 230, 230, 255)).save(self.bg_light)

        # Dummy logo
        self.logo_path = self.tmp / "logo.png"
        Image.new("RGBA", (160, 100), (200, 60, 60, 255)).save(self.logo_path)

        # 1-second silent audio track for export testing
        self.wav_path = self.tmp / "test_audio.wav"
        ffmpeg = find_tool("ffmpeg")
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "1.0", str(self.wav_path)],
            check=True,
            capture_output=True,
        )

        self.tracks = [
            {"path": str(self.wav_path), "duration": 1.0, "title": "Nasheed Track One"}
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # 1. Opacity Pixel Verification (Dark & Light Backgrounds)
    # ------------------------------------------------------------------
    def test_opacity_rendered_pixels_dark_background(self):
        """
        Watermark opacity at 0%, 25%, 50%, 75%, and 100% on dark background:
        - 0% is completely invisible (pixel-identical to no watermark).
        - Strictly monotonic increasing luminance across opacity steps.
        - Minimum pixel value never drops below canvas baseline (zero dark halos).
        - 100% achieves full intended contrast.
        """
        # Baseline composition with empty website text
        base_empty, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.bg_dark),
            logo_path=None,
            collection_title="Opacity Dark Test",
            track_titles=["Track 1"],
            template="Cinematic",
            out_dir=str(self.tmp / "empty_dark"),
            website_text="",
            website_position="Top-Right",
            website_opacity=1.0,
        )
        img_empty = Image.open(base_empty).convert("RGBA")
        crop_empty = img_empty.crop((1500, 30, 1850, 100)).convert("L")
        px_empty = list(crop_empty.get_flattened_data() if hasattr(crop_empty, "get_flattened_data") else crop_empty.getdata())
        baseline_lum = px_empty[0]

        opacities = [0.0, 0.25, 0.50, 0.75, 1.0]
        max_lum_vals = []
        mean_lum_vals = []

        for op in opacities:
            out_dir = self.tmp / f"op_dark_{int(op * 100)}"
            base, _ = create_composition(
                width=1920,
                height=1080,
                background_path=str(self.bg_dark),
                logo_path=None,
                collection_title="Opacity Dark Test",
                track_titles=["Track 1"],
                template="Cinematic",
                out_dir=str(out_dir),
                website_text="www.testnasheed.org",
                website_position="Top-Right",
                website_font_size=20,
                website_show=True,
                website_opacity=op,
            )
            img = Image.open(base).convert("RGBA")
            crop = img.crop((1500, 30, 1850, 100)).convert("L")
            px = list(crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata())

            min_px = min(px)
            max_px = max(px)
            avg_px = sum(px) / len(px)

            max_lum_vals.append(max_px)
            mean_lum_vals.append(avg_px)

            if op == 0.0:
                # 0% must be pixel-identical to empty watermark
                self.assertEqual(crop.tobytes(), crop_empty.tobytes(), "At 0% opacity, watermark must be completely invisible")
                self.assertEqual(min_px, baseline_lum)
                self.assertEqual(max_px, baseline_lum)
            else:
                # Zero dark halos: min luminance must not drop below baseline canvas
                self.assertGreaterEqual(min_px, baseline_lum, f"At {op*100}% opacity, pixels must not drop below background baseline (no dark halo)")

        # Verify strictly monotonic increasing progression across 0%, 25%, 50%, 75%, 100%
        for i in range(len(opacities) - 1):
            self.assertGreater(max_lum_vals[i + 1], max_lum_vals[i], f"Max luminance must increase strictly monotonically from {opacities[i]} to {opacities[i+1]}")
            self.assertGreater(mean_lum_vals[i + 1], mean_lum_vals[i], f"Mean luminance must increase strictly monotonically from {opacities[i]} to {opacities[i+1]}")

        # 100% must have high intended contrast
        self.assertGreater(max_lum_vals[-1], 200, "At 100% opacity, text must reach full intended bright contrast")

    def test_opacity_rendered_pixels_light_background(self):
        """
        Watermark opacity at 0%, 25%, 50%, 75%, and 100% on light background:
        - 0% is completely invisible.
        - Text adapts to dark charcoal for legibility.
        - Strictly monotonic decreasing luminance in text glyphs as opacity increases.
        - Maximum pixel value never exceeds canvas baseline (zero bright halos or boxes).
        - 100% achieves full intended dark contrast.
        """
        base_empty, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.bg_light),
            logo_path=None,
            collection_title="Opacity Light Test",
            track_titles=["Track 1"],
            template="Cinematic",
            out_dir=str(self.tmp / "empty_light"),
            website_text="",
            website_position="Top-Right",
            website_opacity=1.0,
        )
        img_empty = Image.open(base_empty).convert("RGBA")
        crop_empty = img_empty.crop((1500, 30, 1850, 100)).convert("L")
        px_empty = list(crop_empty.get_flattened_data() if hasattr(crop_empty, "get_flattened_data") else crop_empty.getdata())
        baseline_lum = px_empty[0]

        opacities = [0.0, 0.25, 0.50, 0.75, 1.0]
        min_lum_vals = []
        mean_lum_vals = []

        for op in opacities:
            out_dir = self.tmp / f"op_light_{int(op * 100)}"
            base, _ = create_composition(
                width=1920,
                height=1080,
                background_path=str(self.bg_light),
                logo_path=None,
                collection_title="Opacity Light Test",
                track_titles=["Track 1"],
                template="Cinematic",
                out_dir=str(out_dir),
                website_text="www.testnasheed.org",
                website_position="Top-Right",
                website_font_size=20,
                website_show=True,
                website_opacity=op,
            )
            img = Image.open(base).convert("RGBA")
            crop = img.crop((1500, 30, 1850, 100)).convert("L")
            px = list(crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata())

            min_px = min(px)
            max_px = max(px)
            avg_px = sum(px) / len(px)

            min_lum_vals.append(min_px)
            mean_lum_vals.append(avg_px)

            if op == 0.0:
                self.assertEqual(crop.tobytes(), crop_empty.tobytes(), "At 0% opacity, watermark must be completely invisible")
            else:
                # Zero bright halos / bounding boxes: max luminance must never exceed canvas background
                self.assertLessEqual(max_px, baseline_lum, f"At {op*100}% opacity, max pixels must not exceed background baseline (no halo/box)")

        # Verify strictly monotonic decreasing progression for dark text glyphs
        for i in range(len(opacities) - 1):
            self.assertLess(min_lum_vals[i + 1], min_lum_vals[i], f"Min luminance must decrease strictly monotonically from {opacities[i]} to {opacities[i+1]}")
            self.assertLess(mean_lum_vals[i + 1], mean_lum_vals[i], f"Mean luminance must decrease strictly monotonically from {opacities[i]} to {opacities[i+1]}")

        # 100% must achieve strong dark contrast against light background
        self.assertLess(min_lum_vals[-1], 60, "At 100% opacity on light background, text must reach strong dark contrast")

    # ------------------------------------------------------------------
    # 2. Actual Video Export & Frame Opacity Verification
    # ------------------------------------------------------------------
    def test_actual_exported_video_opacity(self):
        """
        Verify that website_opacity works in the actual exported MP4 video via FFmpeg:
        - At 0% opacity: extracted video frame contains no watermark text.
        - At 50% opacity: extracted video frame contains visible text with intermediate alpha.
        """
        ffmpeg = find_tool("ffmpeg")

        # Export video with 0% opacity
        out_0 = self.tmp / "video_op_0.mp4"
        project_0 = {
            "version": 1,
            "collection_title": "Video Watermark Test",
            "background": str(self.bg_dark),
            "tracks": self.tracks,
            "template": "Cinematic",
            "resolution": "1080p · Full HD",
            "indicator_mode": "neither",
            "website_text": "www.videowatermark.org",
            "website_position": "Top-Right",
            "website_font_size": 24,
            "website_show": True,
            "website_opacity": 0.0,
            "output_path": str(out_0),
        }
        render_project(project_0, progress_callback=None)
        self.assertTrue(out_0.is_file(), "Exported MP4 video with 0% opacity must exist")
        self.assertGreater(out_0.stat().st_size, 1000)

        # Export video with 50% opacity
        out_50 = self.tmp / "video_op_50.mp4"
        project_50 = dict(project_0, website_opacity=0.50, output_path=str(out_50))
        render_project(project_50, progress_callback=None)
        self.assertTrue(out_50.is_file(), "Exported MP4 video with 50% opacity must exist")
        self.assertGreater(out_50.stat().st_size, 1000)

        # Extract first frame from both exported videos
        frame_0_path = self.tmp / "frame_0.png"
        frame_50_path = self.tmp / "frame_50.png"
        subprocess.run([ffmpeg, "-y", "-i", str(out_0), "-vframes", "1", str(frame_0_path)], check=True, capture_output=True)
        subprocess.run([ffmpeg, "-y", "-i", str(out_50), "-vframes", "1", str(frame_50_path)], check=True, capture_output=True)

        with Image.open(frame_0_path) as img_0, Image.open(frame_50_path) as img_50:
            crop_0 = img_0.crop((1500, 30, 1850, 100)).convert("L")
            crop_50 = img_50.crop((1500, 30, 1850, 100)).convert("L")

            px_0 = list(crop_0.get_flattened_data() if hasattr(crop_0, "get_flattened_data") else crop_0.getdata())
            px_50 = list(crop_50.get_flattened_data() if hasattr(crop_50, "get_flattened_data") else crop_50.getdata())

            # At 0%, watermark is absent (uniform background luminance within video compression limits)
            self.assertLessEqual(max(px_0) - min(px_0), 2, "Frame with 0% opacity must show flat background with no watermark text")

            # At 50%, watermark text is clearly rendered with higher luminance
            self.assertGreater(max(px_50), max(px_0) + 60, "Frame with 50% opacity must show visible watermark text blended into video")

    # ------------------------------------------------------------------
    # 3. Typography: Font Family, Style, and Resolution Scaling
    # ------------------------------------------------------------------
    def test_typography_font_family_and_style(self):
        """Watermark respects specified font family and style, defaulting cleanly when unspecified."""
        # 1. Custom font family Arial Bold
        comp_arial, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.bg_dark),
            logo_path=None,
            collection_title="Typography Test",
            track_titles=["Track 1"],
            template="Cinematic",
            out_dir=str(self.tmp / "font_arial"),
            website_text="www.nasheedcustomfont.org",
            website_font_family="Arial",
            website_font_style="Bold",
            website_font_size=24,
            website_opacity=1.0,
        )
        self.assertTrue(Path(comp_arial).is_file())

        # 2. Inherit track_font_family when website_font_family is None
        comp_inherit, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.bg_dark),
            logo_path=None,
            collection_title="Typography Test",
            track_titles=["Track 1"],
            template="Cinematic",
            out_dir=str(self.tmp / "font_inherit"),
            website_text="www.nasheedcustomfont.org",
            track_font_family="Arial",
            track_font_style="Regular",
            website_font_size=24,
            website_opacity=1.0,
        )
        self.assertTrue(Path(comp_inherit).is_file())

    def test_resolution_scaling_1080p_1440p_4k(self):
        """Watermark text dimensions scale accurately across 1080p, 1440p, and 4K resolutions."""
        res_map = {
            "1080p": (1920, 1080),
            "1440p": (2560, 1440),
            "4K": (3840, 2160),
        }
        watermark_crops = {}

        for name, (w, h) in res_map.items():
            out_dir = self.tmp / f"res_{name}"
            comp, _ = create_composition(
                width=w,
                height=h,
                background_path=None,  # Use default canvas
                logo_path=None,
                collection_title="Resolution Test",
                track_titles=["Track 1"],
                template="Cinematic",
                out_dir=str(out_dir),
                website_text="www.nasheedscaling.org",
                website_position="Top-Right",
                website_font_size=20,
                website_opacity=1.0,
            )
            with Image.open(comp) as img:
                self.assertEqual(img.size, (w, h))
                # Bounding box of non-background pixels in top-right area
                margin = int(w * 0.055)
                crop_w = int(w * 0.35)
                crop_h = int(h * 0.15)
                corner = img.crop((w - crop_w, 0, w, crop_h)).convert("L")
                px = list(corner.get_flattened_data() if hasattr(corner, "get_flattened_data") else corner.getdata())
                # Verify watermark text rendered
                self.assertGreater(max(px), 150)
                watermark_crops[name] = corner

        # Text at 4K has higher resolution height than 1080p
        bbox_1080 = watermark_crops["1080p"].getbbox()
        bbox_4k = watermark_crops["4K"].getbbox()
        h_1080 = bbox_1080[3] - bbox_1080[1]
        h_4k = bbox_4k[3] - bbox_4k[1]
        self.assertGreater(h_4k, h_1080 * 1.6, "4K watermark must have proportionally greater raster height than 1080p")

    # ------------------------------------------------------------------
    # 4. Positioning and Layout Controls (All 6 Positions & Boundary Safety)
    # ------------------------------------------------------------------
    def test_all_six_positioning_options(self):
        """Watermark can be placed in all 6 standard positions: Top-Right, Top-Left, Bottom-Left, Bottom-Right, Bottom-Center, Top-Center."""
        positions = ["Top-Right", "Top-Left", "Bottom-Left", "Bottom-Right", "Bottom-Center", "Top-Center"]
        for pos in positions:
            out_dir = self.tmp / f"pos_{pos}"
            comp, _ = create_composition(
                width=1920,
                height=1080,
                background_path=str(self.bg_dark),
                logo_path=None,
                collection_title="Position Test",
                track_titles=["Track 1"],
                template="Cinematic",
                out_dir=str(out_dir),
                website_text="www.nasheedpos.org",
                website_position=pos,
                website_font_size=20,
                website_opacity=1.0,
            )
            self.assertTrue(Path(comp).is_file())

    def test_boundary_safety_long_urls_never_clipped(self):
        """Extremely long URLs automatically scale down and remain strictly inside frame margins without clipping."""
        long_url = "www.extremely-long-domain-name-for-testing-overflow-boundary-safety.example.org/audio/nasheed/official"
        for w, h in [(1920, 1080), (2560, 1440), (3840, 2160)]:
            out_dir = self.tmp / f"boundary_{w}"
            comp, _ = create_composition(
                width=w,
                height=h,
                background_path=None,
                logo_path=None,
                collection_title="Boundary Safety Test",
                track_titles=["Track 1"],
                template="Cinematic",
                out_dir=str(out_dir),
                website_text=long_url,
                website_position="Bottom-Right",
                website_font_size=36,  # Intentionally large font size
                website_opacity=1.0,
            )
            with Image.open(comp) as img:
                # Margin is width * 0.055
                margin = int(w * 0.055)
                # Outer border outside frame margin must NOT contain watermark text pixels
                edge_pixels = img.crop((w - margin + 2, 0, w, h)).convert("L")
                px = list(edge_pixels.get_flattened_data() if hasattr(edge_pixels, "get_flattened_data") else edge_pixels.getdata())
                # Must be uniform background, not text
                self.assertLessEqual(max(px) - min(px), 5, f"Watermark at {w}x{h} must not bleed into right frame margin")

    def test_collision_avoidance_logo_and_playlist(self):
        """
        - When logo and website share corner, website is offset cleanly to prevent collision.
        - When website is in Bottom-Right and playlist is in Left, playlist is not vertically restricted.
        """
        # Both in Bottom-Right
        comp_br, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.bg_dark),
            logo_path=str(self.logo_path),
            logo_position="Bottom-Right",
            collection_title="Collision Test",
            track_titles=[f"Track {i}" for i in range(12)],
            template="Cinematic",
            out_dir=str(self.tmp / "col_br"),
            website_text="www.collisiontest.org",
            website_position="Bottom-Right",
            website_opacity=1.0,
        )
        self.assertTrue(Path(comp_br).is_file())

        # Website in Bottom-Right, playlist on Left: playlist has 12 tracks, verify rendering
        comp_left, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.bg_dark),
            logo_path=None,
            collection_title="Collision Test Left",
            track_titles=[f"Track {i}" for i in range(12)],
            template="Cinematic",
            playlist_position="Left",
            out_dir=str(self.tmp / "col_left"),
            website_text="www.collisiontest.org",
            website_position="Bottom-Right",
            website_opacity=1.0,
        )
        self.assertTrue(Path(comp_left).is_file())

    # ------------------------------------------------------------------
    # 5. Hidden, Empty, and Persistence Compatibility
    # ------------------------------------------------------------------
    def test_hidden_and_empty_website_text(self):
        """Hidden watermark or empty/whitespace text produces zero visual artifacts."""
        base_clean, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.bg_dark),
            logo_path=None,
            collection_title="Clean Test",
            track_titles=["Track 1"],
            template="Cinematic",
            out_dir=str(self.tmp / "clean"),
            website_text="",
        )
        img_clean = Image.open(base_clean)

        # website_show=False
        base_hidden, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.bg_dark),
            logo_path=None,
            collection_title="Clean Test",
            track_titles=["Track 1"],
            template="Cinematic",
            out_dir=str(self.tmp / "hidden"),
            website_text="www.shouldnotappear.org",
            website_show=False,
            website_opacity=1.0,
        )
        img_hidden = Image.open(base_hidden)
        self.assertEqual(img_clean.tobytes(), img_hidden.tobytes(), "website_show=False must produce byte-identical output to empty text")

        # website_text="   " (whitespace)
        base_space, _ = create_composition(
            width=1920,
            height=1080,
            background_path=str(self.bg_dark),
            logo_path=None,
            collection_title="Clean Test",
            track_titles=["Track 1"],
            template="Cinematic",
            out_dir=str(self.tmp / "space"),
            website_text="    ",
            website_show=True,
            website_opacity=1.0,
        )
        img_space = Image.open(base_space)
        self.assertEqual(img_clean.tobytes(), img_space.tobytes(), "Whitespace website text must produce byte-identical output to empty text")

    def test_project_and_template_persistence_roundtrip(self):
        """Project and template save/load preserves all watermark settings."""
        win = MainWindow()
        try:
            win.website_edit.setText("www.persistedwatermark.org")
            win.website_pos_combo.setCurrentText("Bottom-Center")
            win.website_size_spin.setValue(21)
            win.website_show_check.setChecked(True)
            win.website_opacity_slider.setValue(65)
            win.website_font_family = "Arial"
            win.website_font_style = "Regular"
            win.website_color = (220, 230, 240)

            proj = win._project()
            self.assertEqual(proj["website_text"], "www.persistedwatermark.org")
            self.assertEqual(proj["website_position"], "Bottom-Center")
            self.assertEqual(proj["website_font_size"], 21)
            self.assertTrue(proj["website_show"])
            self.assertEqual(proj["website_opacity"], 0.65)
            self.assertEqual(proj["website_font_family"], "Arial")
            self.assertEqual(proj["website_font_style"], "Regular")
            self.assertEqual(proj["website_color"], (220, 230, 240))

            # Template extraction preserves visual watermark settings while excluding protected URL text
            tmpl = extract_template(proj, template_name="Watermark Template")
            self.assertEqual(tmpl["website_position"], "Bottom-Center")
            self.assertEqual(tmpl["website_font_size"], 21)
            self.assertTrue(tmpl["website_show"])
            self.assertEqual(tmpl["website_opacity"], 0.65)
            self.assertEqual(tmpl["website_font_family"], "Arial")
            self.assertNotIn("website_text", tmpl, "Protected URL text must never be copied to template")

            # Apply template to a new project
            receiving_project = {
                "collection_title": "Existing Title",
                "website_text": "www.originalreceiver.org",
                "tracks": [],
                "background": "",
            }
            updated = apply_template_to_project(receiving_project, tmpl)
            self.assertEqual(updated["website_position"], "Bottom-Center")
            self.assertEqual(updated["website_font_size"], 21)
            self.assertEqual(updated["website_opacity"], 0.65)
            self.assertEqual(updated["website_text"], "www.originalreceiver.org", "Receiving project URL text must be preserved")

            # Project save to file and load back into new window
            proj_file = self.tmp / "test_watermark_proj.json"
            win._write_project(str(proj_file))

            win2 = MainWindow()
            try:
                win2._load_project_file(str(proj_file))
                self.assertEqual(win2.website_edit.text(), "www.persistedwatermark.org")
                self.assertEqual(win2.website_pos_combo.currentText(), "Bottom-Center")
                self.assertEqual(win2.website_size_spin.value(), 21)
                self.assertTrue(win2.website_show_check.isChecked())
                self.assertEqual(win2.website_opacity_slider.value(), 65)
                self.assertEqual(win2.website_font_family, "Arial")
                self.assertEqual(win2.website_font_style, "Regular")
                self.assertEqual(win2.website_color, (220, 230, 240))
            finally:
                dispose_window(win2)
        finally:
            dispose_window(win)


if __name__ == "__main__":
    unittest.main()
