"""
Central stylesheet and design tokens for Nasheed Studio.
Original Green Palette:
- Primary accent: #3D8B58
- Window background: #161C18
- Panel and card background: #1B211D
- Button and field fill: #222A24
- Neutral borders and dividers: #2C362E
- Outlined accent button border: #294231
- Canvas frame border: #121615
- Logo/music-note icon and active outlines use primary green #3D8B58.
"""

try:
    from src.ui import resources_rc  # noqa: F401 - registers :/icons/... resources
except ImportError:
    pass

# Named token dictionary - Single source of truth for all theme colors
TOKENS = {
    # Core Accent & Variants
    "accent": "#3D8B58",
    "accent_hover": "#48A167",         # ~+8% lightness
    "accent_pressed": "#2F7248",       # ~-10% lightness
    "accent_disabled": "#26382C",      # ~40% opacity on dark panel
    "accent_disabled_text": "#566F5E",
    "accent_text": "#FFFFFF",          # High contrast text on #3D8B58
    "accent_light": "#C0E4C9",
    "accent_tint": "#1E2A22",

    # Surfaces & Backgrounds
    "bg_window": "#161C18",            # Window background
    "bg_app": "#161C18",               # Alias for root window
    "bg_canvas": "#121615",            # Canvas frame border / background
    "bg_panel": "#1B211D",             # Panel and card background
    "bg_panel_alt": "#1E2621",         # Slightly offset toolbar/card background
    "bg_card": "#1B211D",              # Card background
    "bg_field": "#222A24",             # Button and field fill
    "bg_input": "#222A24",             # Alias for field fill
    "bg_input_hover": "#2A352D",
    "bg_input_pressed": "#1C231E",
    "bg_input_disabled": "#181E1A",

    # Borders & Dividers
    "border": "#2C362E",               # Neutral borders and dividers
    "border_hairline": "#2C362E",      # Hairline border alias
    "border_input": "#2C362E",         # Input border
    "border_hover": "#3B4A3E",         # Hover border
    "border_focus": "#3D8B58",         # Focus border uses primary green
    "border_accent": "#294231",        # Outlined accent button border (New, Open)
    "border_canvas": "#121615",        # Canvas frame border

    # Selection & Highlights
    "selection_bg": "#233328",         # Selected row background in flat list
    "selection_border": "#2E4736",
    "selection_active_border": "#3D8B58",
    "item_hover_bg": "#253029",
    "item_hover_border": "#36473B",

    # Typography / Neutrals
    "text_main": "#F0F4F1",            # Primary light text
    "text_muted": "#95A399",           # Secondary text
    "text_subtle": "#66756B",          # Muted text
    "text_disabled": "#4F5B53",        # Disabled text

    # States & Alerts
    "warn_bg": "#2A251A",
    "warn_border": "#635021",
    "warn_text": "#F2BA49",
    "cancel_bg": "#3D2224",
    "cancel_border": "#683034",
    "cancel_text": "#F0D0D0",
    "saved_pill_bg": "#17261D",
    "saved_pill_border": "#284C35",
    "saved_pill_text": "#62B582",
}

# Add uppercase key aliases into TOKENS dictionary for robustness
for _k, _v in list(TOKENS.items()):
    TOKENS[_k.upper()] = _v

# Uppercase named constants for direct imports
ACCENT = TOKENS["accent"]
ACCENT_HOVER = TOKENS["accent_hover"]
ACCENT_PRESSED = TOKENS["accent_pressed"]
ACCENT_DISABLED = TOKENS["accent_disabled"]
ACCENT_DISABLED_TEXT = TOKENS["accent_disabled_text"]
ACCENT_TEXT = TOKENS["accent_text"]
ACCENT_LIGHT = TOKENS["accent_light"]
BG_WINDOW = TOKENS["bg_window"]
BG_APP = TOKENS["bg_app"]
BG_PANEL = TOKENS["bg_panel"]
BG_PANEL_ALT = TOKENS["bg_panel_alt"]
BG_CARD = TOKENS["bg_card"]
BG_FIELD = TOKENS["bg_field"]
BG_INPUT = TOKENS["bg_input"]
BG_CANVAS = TOKENS["bg_canvas"]
BORDER = TOKENS["border"]
BORDER_HAIRLINE = TOKENS["border_hairline"]
BORDER_INPUT = TOKENS["border_input"]
BORDER_HOVER = TOKENS["border_hover"]
BORDER_FOCUS = TOKENS["border_focus"]
BORDER_ACCENT = TOKENS["border_accent"]
BORDER_CANVAS = TOKENS["border_canvas"]
TEXT_MAIN = TOKENS["text_main"]
TEXT_MUTED = TOKENS["text_muted"]
TEXT_SUBTLE = TOKENS["text_subtle"]
TEXT_DISABLED = TOKENS["text_disabled"]


def _build_style(t: dict) -> str:
    """Build central application stylesheet interpolated from theme tokens."""
    return f"""
/* ---- Root Application Window ---- */
QMainWindow, QWidget#central_root {{
    background: {t['bg_window']};
    color: {t['text_main']};
    font-family: 'Segoe UI Variable', 'Segoe UI', -apple-system, sans-serif;
    font-size: 10pt;
    font-weight: 400;
}}

/* ---- Dialogs & Message Boxes ---- */
QDialog, QMessageBox {{
    background: {t['bg_panel']};
    color: {t['text_main']};
}}
QDialog QLabel, QMessageBox QLabel {{
    color: {t['text_main']};
}}

/* ---- Generic Labels & Section Badges ---- */
QLabel {{
    color: {t['text_main']};
    font-family: 'Segoe UI Variable', 'Segoe UI', -apple-system, sans-serif;
}}
QLabel#app_title {{
    font-size: 13pt;
    font-weight: 600;
    color: {t['text_main']};
    letter-spacing: 0.5px;
}}
QLabel#app_subtitle {{
    font-size: 8.5pt;
    font-weight: 500;
    color: {t['text_muted']};
    letter-spacing: 1.2px;
}}
QLabel#project_name {{
    font-size: 10pt;
    font-weight: 500;
    color: #C8D3CB;
    padding: 0 4px;
}}
QLabel#section {{
    color: {t['text_muted']};
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}}
QLabel#muted {{
    color: {t['text_muted']};
    font-size: 9pt;
}}
QLabel#subtle {{
    color: {t['text_subtle']};
    font-size: 8pt;
}}
QLabel#unsaved_pill {{
    background: {t['warn_bg']};
    color: {t['warn_text']};
    border: 1px solid {t['warn_border']};
    border-radius: 9px;
    padding: 1px 7px;
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 0.3px;
}}
QLabel#saved_pill {{
    background: {t['saved_pill_bg']};
    color: {t['saved_pill_text']};
    border: 1px solid {t['saved_pill_border']};
    border-radius: 9px;
    padding: 1px 7px;
    font-size: 8pt;
    font-weight: 600;
}}
QLabel#warning {{
    color: {t['warn_text']};
    font-size: 8pt;
    font-weight: 500;
    padding: 6px 10px;
    background: {t['warn_bg']};
    border: 1px solid {t['warn_border']};
    border-radius: 4px;
}}

/* ---- Panes & Dividers ---- */
QFrame#top_bar {{
    background: {t['bg_panel']};
    border-bottom: 1px solid {t['border_hairline']};
    padding: 3px 6px;
}}
QFrame#playlist_pane, QFrame#preview_pane, QFrame#inspector_pane {{
    background: {t['bg_panel']};
    border: 1px solid {t['border_hairline']};
    border-radius: 6px;
}}
QFrame#export_bar {{
    background: {t['bg_panel_alt']};
    border-top: 1px solid {t['border_hairline']};
    border-bottom: 1px solid {t['border_hairline']};
    padding: 6px 12px;
}}
QFrame#status_bar {{
    background: {t['bg_window']};
    padding: 2px 8px;
}}
QFrame#hairline_h {{
    background: {t['border_hairline']};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
QFrame#hairline_v {{
    background: {t['border_hairline']};
    max-width: 1px;
    min-width: 1px;
    border: none;
}}
QSplitter::handle {{
    background: {t['bg_window']};
    border: none;
}}

/* ---- Input Controls (Uniform 26-28px height, 4px radius) ---- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {t['bg_field']};
    color: {t['text_main']};
    border: 1px solid {t['border_input']};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
    selection-background-color: {t['accent']};
    selection-color: {t['accent_text']};
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {t['border_hover']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {t['border_focus']};
    background: #232C26;
}}

/* ---- QLineEdit Clear Button Vertical Centering ---- */
QLineEdit QToolButton {{
    background: transparent;
    border: none;
    border-radius: 0px;
    padding: 0px;
    margin: 0px;
    min-height: 0px;
    min-width: 0px;
}}
QLineEdit QToolButton:hover, QLineEdit QToolButton:pressed {{
    background: transparent;
    border: none;
}}
QSpinBox, QDoubleSpinBox {{
    padding-left: 6px;
    padding-right: 22px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    height: 12px;
    border-left: 1px solid {t['border_input']};
    border-bottom: 1px solid {t['border_input']};
    background: #273229;
    border-top-right-radius: 3px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background: #334236;
}}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed {{
    background: {t['bg_input_pressed']};
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    height: 12px;
    border-left: 1px solid {t['border_input']};
    background: #273229;
    border-bottom-right-radius: 3px;
}}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: #334236;
}}
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{
    background: {t['bg_input_pressed']};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url(:/icons/chevron_up.svg);
    width: 10px;
    height: 10px;
}}
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {{
    image: url(:/icons/chevron_up_hover.svg);
}}
QSpinBox::up-arrow:pressed, QDoubleSpinBox::up-arrow:pressed {{
    image: url(:/icons/chevron_up_pressed.svg);
}}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled,
QSpinBox::up-arrow:off, QDoubleSpinBox::up-arrow:off {{
    image: url(:/icons/chevron_up_disabled.svg);
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url(:/icons/chevron_down.svg);
    width: 10px;
    height: 10px;
}}
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {{
    image: url(:/icons/chevron_down_hover.svg);
}}
QSpinBox::down-arrow:pressed, QDoubleSpinBox::down-arrow:pressed {{
    image: url(:/icons/chevron_down_pressed.svg);
}}
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled,
QSpinBox::down-arrow:off, QDoubleSpinBox::down-arrow:off {{
    image: url(:/icons/chevron_down_disabled.svg);
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left: none;
}}
QComboBox::drop-down:hover {{
    background: transparent;
}}
QComboBox::down-arrow {{
    image: url(:/icons/chevron_down.svg);
    width: 10px;
    height: 10px;
    margin-right: 6px;
}}
QComboBox::down-arrow:hover {{
    image: url(:/icons/chevron_down_hover.svg);
}}
QComboBox::down-arrow:pressed {{
    image: url(:/icons/chevron_down_pressed.svg);
}}
QComboBox::down-arrow:disabled {{
    image: url(:/icons/chevron_down_disabled.svg);
}}
QComboBox QAbstractItemView {{
    background: {t['bg_panel_alt']};
    color: {t['text_main']};
    border: 1px solid {t['border_hairline']};
    selection-background-color: #27342B;
    selection-color: #FFFFFF;
    outline: none;
    padding: 4px;
}}

/* ---- Buttons & ToolButtons ---- */
QPushButton, QToolButton {{
    background: {t['bg_field']};
    color: {t['text_main']};
    border: 1px solid {t['border_hairline']};
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 22px;
    font-weight: 500;
}}
QPushButton:hover, QToolButton:hover {{
    background: {t['bg_input_hover']};
    border-color: {t['border_hover']};
    color: #FFFFFF;
}}
QPushButton:pressed, QToolButton:pressed {{
    background: {t['bg_input_pressed']};
}}
QPushButton:disabled, QToolButton:disabled {{
    background: {t['bg_input_disabled']};
    color: {t['text_disabled']};
    border-color: #242C26;
}}
QPushButton:focus, QToolButton:focus {{
    border-color: {t['border_focus']};
}}

/* Primary filled button: Green accent (Save, Render MP4) */
QPushButton#primary, QToolButton#primary {{
    background: {t['accent']};
    color: {t['accent_text']};
    border: 1px solid {t['accent_hover']};
    font-weight: 600;
}}
QPushButton#primary:hover, QToolButton#primary:hover {{
    background: {t['accent_hover']};
    border-color: #55B778;
    color: #FFFFFF;
}}
QPushButton#primary:pressed, QToolButton#primary:pressed {{
    background: {t['accent_pressed']};
    color: #FFFFFF;
}}
QPushButton#primary:disabled, QToolButton#primary:disabled {{
    background: {t['accent_disabled']};
    color: {t['accent_disabled_text']};
    border-color: #2B3D31;
}}

/* Outlined accent button: (New, Open, Choose) */
QPushButton#outlined_accent, QToolButton#outlined_accent,
QPushButton#accent_outline, QToolButton#accent_outline {{
    background: {t['bg_field']};
    color: {t['text_main']};
    border: 1px solid {t['border_accent']};
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 22px;
    font-weight: 500;
}}
QPushButton#outlined_accent:hover, QToolButton#outlined_accent:hover,
QPushButton#accent_outline:hover, QToolButton#accent_outline:hover {{
    background: {t['bg_input_hover']};
    border-color: {t['accent']};
    color: #FFFFFF;
}}
QPushButton#outlined_accent:pressed, QToolButton#outlined_accent:pressed,
QPushButton#accent_outline:pressed, QToolButton#accent_outline:pressed {{
    background: {t['bg_input_pressed']};
    border-color: {t['border_accent']};
}}

/* Cancel / Destructive button */
QPushButton#cancel {{
    background: {t['cancel_bg']};
    color: {t['cancel_text']};
    border: 1px solid {t['cancel_border']};
    font-weight: 500;
}}
QPushButton#cancel:hover {{
    background: #4D2A2D;
    border-color: #803B40;
}}
QPushButton#cancel:disabled {{
    background: #241A1B;
    color: #5C4344;
    border-color: #332324;
}}

/* Quiet / Ghost button */
QPushButton#quiet, QToolButton#quiet {{
    background: transparent;
    border: 1px solid transparent;
    color: {t['text_muted']};
}}
QPushButton#quiet:hover, QToolButton#quiet:hover {{
    background: {t['bg_field']};
    border-color: {t['border_hairline']};
    color: {t['text_main']};
}}

/* Tab button / Segmented toggle */
QToolButton#tab_button {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px;
    color: {t['text_muted']};
}}
QToolButton#tab_button:hover {{
    background: {t['bg_field']};
    color: {t['text_main']};
}}
QToolButton#tab_button:checked {{
    background: {t['selection_bg']};
    border: 1px solid {t['accent']};
    color: #FFFFFF;
}}

/* ---- Playlist QListWidget (Clean Flat Rows) ---- */
QListWidget {{
    background: {t['bg_panel']};
    color: {t['text_main']};
    border: 1px solid {t['border_hairline']};
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: {t['selection_bg']};
    selection-color: #FFFFFF;
}}
QListWidget::item {{
    padding: 7px 8px;
    border: 1px solid {t['bg_field']};
    border-left: 3px solid transparent;
    color: {t['text_main']};
    background: {t['bg_panel_alt']};
    border-radius: 4px;
    margin-bottom: 3px;
    outline: none;
}}
QListWidget::item:hover {{
    color: #FFFFFF;
    background: {t['item_hover_bg']};
    border: 1px solid {t['item_hover_border']};
    border-left: 3px solid transparent;
    outline: none;
}}
QListWidget::item:selected {{
    background: {t['selection_bg']};
    color: #FFFFFF;
    border: 1px solid {t['selection_border']};
    border-left: 3px solid {t['accent']};
    outline: none;
}}
QListWidget::item:selected:active {{
    background: {t['selection_bg']};
    color: #FFFFFF;
    border: 1px solid {t['selection_border']};
    border-left: 3px solid {t['accent']};
    outline: none;
}}
QListWidget::item:selected:!active {{
    background: #1F2E24;
    color: #E2E8F0;
    border: 1px solid {t['selection_border']};
    border-left: 3px solid {t['accent']};
    outline: none;
}}
QListWidget::item:focus {{
    background: {t['selection_bg']};
    color: #FFFFFF;
    border: 1px solid {t['selection_border']};
    border-left: 3px solid {t['accent']};
    outline: none;
}}
QListWidget::item:disabled {{
    color: {t['text_subtle']};
    background: {t['bg_panel']};
    border: 1px solid {t['bg_field']};
    outline: none;
}}

/* ---- Inspector QTabWidget ---- */
QTabWidget::pane {{
    border: none;
    background: transparent;
}}
QTabBar::tab {{
    background: {t['bg_panel']};
    color: {t['text_muted']};
    border: 1px solid {t['border_hairline']};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 3px;
    margin-right: 1px;
    font-size: 8pt;
    font-weight: 500;
}}
QTabBar::tab:hover {{
    background: #242C26;
    color: {t['text_main']};
}}
QTabBar::tab:selected {{
    background: {t['bg_panel_alt']};
    color: {t['text_main']};
    border-color: {t['border_hairline']};
    border-bottom: 2px solid {t['accent']};
}}
QTabBar QToolButton {{
    background: {t['bg_panel']};
    color: {t['text_muted']};
    border: 1px solid {t['border_hairline']};
    border-radius: 3px;
    padding: 0px;
    margin: 0px;
    min-height: 0px;
    min-width: 14px;
    max-width: 16px;
}}
QTabBar QToolButton:hover {{
    background: {t['bg_field']};
    color: {t['text_main']};
}}

/* ---- Inspector Collapsible Section Headers ---- */
QPushButton#twirl_header {{
    background: {t['bg_panel']};
    color: {t['text_main']};
    border: 1px solid {t['border_hairline']};
    border-radius: 4px;
    text-align: left;
    padding: 5px 8px;
    font-size: 8.5pt;
    font-weight: 600;
    letter-spacing: 0.3px;
}}
QPushButton#twirl_header:hover {{
    background: #242C26;
    border-color: {t['border_hover']};
    color: #FFFFFF;
}}
QPushButton#twirl_header:checked {{
    background: #1E2520;
    border-color: {t['border_hairline']};
    color: {t['text_main']};
}}

QLabel#prop_label {{
    color: {t['text_muted']};
    font-size: 8.5pt;
    font-weight: 500;
}}

QLabel#asset_path {{
    background: {t['bg_panel']};
    border: 1px solid {t['border_hairline']};
    border-radius: 4px;
    padding: 3px 6px;
    color: {t['text_muted']};
    font-size: 8pt;
}}

/* ---- Preview Frame ---- */
QFrame#preview {{
    background: {t['bg_canvas']};
    border: 1px solid {t['border_canvas']};
    border-radius: 6px;
}}

/* ---- Progress Bar & Scrubber Slider ---- */
QProgressBar {{
    border: 1px solid {t['border_hairline']};
    border-radius: 4px;
    background: {t['bg_panel']};
    text-align: center;
    color: {t['text_main']};
    font-size: 8pt;
    height: 18px;
}}
QProgressBar::chunk {{
    background: {t['accent']};
    border-radius: 3px;
}}

QSlider::groove:horizontal {{
    border: 1px solid {t['border_hairline']};
    height: 4px;
    background: {t['bg_field']};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {t['accent']};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {t['accent']};
    width: 12px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 6px;
}}
QSlider::handle:horizontal:disabled {{
    background: {t['text_disabled']};
}}

/* ---- CheckBox & RadioButton ---- */
QCheckBox, QRadioButton {{
    color: {t['text_main']};
    spacing: 8px;
    font-weight: 400;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid {t['border_hairline']};
    background: {t['bg_field']};
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {t['border_hover']};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {t['selection_bg']};
    border-color: {t['accent']};
}}

/* ---- ScrollArea & Menus ---- */
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    border: none;
    background: {t['bg_canvas']};
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {t['border_hairline']};
    min-height: 24px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t['accent']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
    border: none;
}}
QScrollBar::up-arrow:vertical {{
    image: url(:/icons/chevron_up.svg);
    width: 8px;
    height: 8px;
}}
QScrollBar::down-arrow:vertical {{
    image: url(:/icons/chevron_down.svg);
    width: 8px;
    height: 8px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QMenuBar {{
    background: {t['bg_panel']};
    color: {t['text_main']};
    border-bottom: 1px solid {t['border_hairline']};
}}
QMenuBar::item:selected {{
    background: {t['bg_field']};
}}
QMenu {{
    background: {t['bg_panel_alt']};
    color: {t['text_main']};
    border: 1px solid {t['border_hairline']};
    border-radius: 4px;
    padding: 4px 0;
}}
QMenu::item {{
    padding: 6px 20px;
}}
QMenu::item:selected {{
    background: #27342B;
    color: #FFFFFF;
}}
QMenu::separator {{
    height: 1px;
    background: {t['border_hairline']};
    margin: 4px 8px;
}}
"""

STYLE = _build_style(TOKENS)
