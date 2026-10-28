# Nasheed Studio - Reusable User Templates Library

The `user_templates/` directory provides pre-configured, production-ready design templates inspired by high-performing YouTube nasheed collections. These templates define the complete visual identity, typography, layout geometry, indicators, and animations while fully preserving your custom audio tracks and playlist content.

---

## 1. Active Curated Templates

### `01_gym_nasheeds_monochrome_lion.json`
- **Target Aesthetic**: Reference 1 - High-contrast black and white Chiaroscuro Lion.
- **Visual Design**:
  - **Background**: `assets/lion_clean_bg.png` (Pitch-black background with monochrome lion on the left).
  - **Typography**: Century Gothic (91px Bold title, 61px Regular tracklist).
  - **Active Track Indicator**: Custom white lion paw cursor asset (`assets/paw_cursor.png`, 50px).
  - **Layout**: Right-aligned single-column playlist (`x_offset: -110`, `row_spacing: 1.39`).
  - **Watermark & Logo**: Top-Left NCN logo (`assets/ncn_logo.png`) and Bottom-Right website watermark `www.nocopyrightnasheeds.com`.

### `04_sad_nasheeds_glass_highlight.json`
- **Target Aesthetic**: Reference 4 - Sad Nasheeds Collection with modern Glassmorphism.
- **Visual Design**:
  - **Background**: `assets/refer4_sad_nasheeds_clean_bg.png` (Deep teal and navy smooth vignette).
  - **Typography**: Glass-like semi-translucent Cinzel serif title (95% opacity, 0.5px softening) with clean white Montserrat tracklist (`#FFFFFF`, 85% opacity, 0.5px softening).
  - **Active Track Indicator**: Crisp 6px electric cyan (`#00C8F8`) rectangular outline highlight with crisp 90-degree square corners, transparent interior (zero inner shading), and tight text wrapping.
  - **Branding**: "Slave of Allah" crescent & mosque logo (`assets/slave_of_allah_crescent_logo.png`).
  - **Intro**: 3.0s Smooth zoom-in.

---

## 2. Loading and Applying Templates

You can apply any template seamlessly through the GUI:
1. In the top toolbar, click **Templates** (or navigate to `File > Apply Template...`).
2. Select **Template: [Name]** directly from the **User Templates Library** dropdown section, or choose **Open Template File...** and pick any `.json` file from `user_templates/`.
3. When applied:
   - Your audio tracks, track order, and durations are **100% preserved**.
   - Background, layout, typography, indicators, colors, opacity, and logo settings immediately update.
   - The interactive preview refreshes instantly to show your content in the selected template's style.

---

## 3. Supported Settings & Customizability

Every template JSON is completely modular and customizable:
- `template_name`: Display name shown in menus and dialogs.
- `description`: Informative tooltip summarizing the aesthetic.
- `collection_title`: Recommended title text (can be edited at any time).
- `background`: Portable relative path to background image or MP4 video.
- `title_font_family`, `title_font_style`, `title_font_size`, `title_position`, `title_color`: Complete title typography controls.
- `title_opacity`, `title_softening`: Glassmorphic opacity and Gaussian edge softening.
- `track_font_family`, `track_font_style`, `track_font_size`, `track_color`, `track_opacity`, `track_softening`: Tracklist styling.
- `playlist_position`, `playlist_columns`, `playlist_row_spacing`, `playlist_col_spacing`, `playlist_x_offset`, `playlist_y_offset`: Playlist geometry.
- `indicator_mode`: Indicator mode (`"both"`, `"cursor_only"`, `"highlight_only"`, `"neither"`).
- `cursor_y_offset`: Independent vertical offset fine-tuning for cursor (-50 to +50 px).
- `highlight_y_offset`: Independent vertical offset fine-tuning for highlight (-50 to +50 px).
- `highlight_style`: Indicator style (`"Pill"`, `"Outline"`, `"Accent Bar"`, `"Underline"`).
- `highlight_color`: Indicator RGB color.
- `highlight_outline_width`: Outline thickness in pixels (1px to 16px).
- `highlight_corner_radius`: Corner curvature (`0` for sharp geometric rectangle, `>0` for rounded pill).
- `highlight_target`: `"row"` (full row width) or `"text"` (tightly wraps around track title).
- `cursor_path`, `cursor_size`: Path to custom PNG or SVG cursor icon and rendered dimension.

---

## 4. Portability & Best Practices

- All asset paths are relative to the project root (`assets/...`), ensuring templates work across different machines without broken file references.
- Audio files are stored separately as project content, keeping templates lightweight and reusable across entirely different nasheed collections.
