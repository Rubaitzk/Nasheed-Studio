"""
Central stylesheet and design tokens for Nasheed Studio.

Design Tokens:
- Dark green-tinted neutrals:
    BG_APP: #111512
    BG_PANEL: #171c18
    BG_CARD: #1d231f
    BG_INPUT: #202722
    BORDER_HAIRLINE: #29322b
    BORDER_INPUT: #344037
    BORDER_HOVER: #445448
- Accent (single green accent):
    ACCENT: #3d8b58
    ACCENT_HOVER: #48a167
    ACCENT_TEXT: #0d1a11
    ACCENT_LIGHT: #c0e4c9
- Neutrals / Typography:
    TEXT_MAIN: #edf2ee
    TEXT_MUTED: #95a399
    TEXT_SUBTLE: #66756b
    TEXT_DISABLED: #4f5b53
- States:
    WARN_BG: #2a251a
    WARN_BORDER: #635021
    WARN_TEXT: #f2ba49
    CANCEL_BG: #4a2424
    CANCEL_BORDER: #7a3535
    CANCEL_TEXT: #f0d0d0
"""

# Named token dictionary
TOKENS = {
    "bg_app": "#111512",
    "bg_panel": "#171c18",
    "bg_card": "#1d231f",
    "bg_input": "#202722",
    "border_hairline": "#29322b",
    "border_input": "#344037",
    "border_hover": "#445448",
    "accent": "#3d8b58",
    "accent_hover": "#48a167",
    "accent_text": "#0d1a11",
    "accent_light": "#c0e4c9",
    "text_main": "#edf2ee",
    "text_muted": "#95a399",
    "text_subtle": "#66756b",
    "text_disabled": "#4f5b53",
    "warn_bg": "#2a251a",
    "warn_border": "#635021",
    "warn_text": "#f2ba49",
    "cancel_bg": "#4a2424",
    "cancel_border": "#7a3535",
    "cancel_text": "#f0d0d0",
}

# Central Application Stylesheet
STYLE = """
/* ---- Root Application Window ---- */
QMainWindow, QWidget#central_root {
    background: #111512;
    color: #edf2ee;
    font-family: 'Segoe UI Variable', 'Segoe UI', -apple-system, sans-serif;
    font-size: 10pt;
    font-weight: 400;
}

/* ---- Generic Labels & Section Badges ---- */
QLabel {
    color: #edf2ee;
    font-family: 'Segoe UI Variable', 'Segoe UI', -apple-system, sans-serif;
}
QLabel#app_title {
    font-size: 13pt;
    font-weight: 600;
    color: #f4f7f4;
    letter-spacing: 0.5px;
}
QLabel#app_subtitle {
    font-size: 8pt;
    font-weight: 500;
    color: #95a399;
    letter-spacing: 1.2px;
}
QLabel#project_name {
    font-size: 10pt;
    font-weight: 500;
    color: #c8d3cb;
    padding: 0 4px;
}
QLabel#section {
    color: #95a399;
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}
QLabel#muted {
    color: #95a399;
    font-size: 9pt;
}
QLabel#subtle {
    color: #66756b;
    font-size: 8.5pt;
}
QLabel#unsaved_pill {
    background: #332617;
    color: #f2ba49;
    border: 1px solid #635021;
    border-radius: 9px;
    padding: 1px 7px;
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 0.3px;
}
QLabel#saved_pill {
    background: #17261d;
    color: #62b582;
    border: 1px solid #284c35;
    border-radius: 9px;
    padding: 1px 7px;
    font-size: 8pt;
    font-weight: 600;
}
QLabel#warning {
    color: #f2ba49;
    font-size: 8.5pt;
    font-weight: 500;
    padding: 6px 10px;
    background: #2a251a;
    border: 1px solid #635021;
    border-radius: 6px;
}

/* ---- Panes & Dividers ---- */
QFrame#top_bar {
    background: #161c18;
    border-bottom: 1px solid #29322b;
    padding: 2px;
}
QFrame#playlist_pane, QFrame#preview_pane, QFrame#inspector_pane {
    background: #171c18;
    border: 1px solid #29322b;
    border-radius: 6px;
}
QFrame#export_bar {
    background: #161c18;
    border-top: 1px solid #29322b;
    border-bottom: 1px solid #29322b;
    padding: 6px 12px;
}
QFrame#status_bar {
    background: #111512;
    padding: 2px 8px;
}
QFrame#hairline_h {
    background: #29322b;
    max-height: 1px;
    min-height: 1px;
    border: none;
}
QSplitter::handle {
    background: #1c221e;
    width: 4px;
}
QSplitter::handle:hover {
    background: #3d8b58;
}

/* ---- Input Controls (Uniform 28-30px height, 6px radius) ---- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #202722;
    color: #edf2ee;
    border: 1px solid #344037;
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 22px;
    selection-background-color: #3d8b58;
    selection-color: #edf2ee;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #445448;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #3d8b58;
    background: #232c26;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: none;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #95a399;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background: #1d231f;
    color: #edf2ee;
    border: 1px solid #344037;
    selection-background-color: #2e5c3e;
    selection-color: #e8f5ec;
    outline: none;
    padding: 4px;
}

/* ---- Buttons & ToolButtons ---- */
QPushButton, QToolButton {
    background: #222a24;
    color: #edf2ee;
    border: 1px solid #364239;
    border-radius: 6px;
    padding: 4px 10px;
    min-height: 22px;
    font-weight: 500;
}
QPushButton:hover, QToolButton:hover {
    background: #2a352d;
    border-color: #46554b;
    color: #ffffff;
}
QPushButton:pressed, QToolButton:pressed {
    background: #1c231e;
}
QPushButton:disabled, QToolButton:disabled {
    background: #181e1a;
    color: #4f5b53;
    border-color: #242c26;
}
QPushButton:focus, QToolButton:focus {
    border-color: #3d8b58;
}

/* Primary filled button (single green accent: Save, Render MP4) */
QPushButton#primary, QToolButton#primary {
    background: #3d8b58;
    color: #ffffff;
    border: 1px solid #48a167;
    font-weight: 600;
}
QPushButton#primary:hover, QToolButton#primary:hover {
    background: #48a167;
    border-color: #55b778;
}
QPushButton#primary:pressed, QToolButton#primary:pressed {
    background: #2f7248;
}
QPushButton#primary:disabled, QToolButton#primary:disabled {
    background: #26382c;
    color: #566f5e;
    border-color: #2b3d31;
}

/* Cancel / Destructive button */
QPushButton#cancel {
    background: #4a2424;
    color: #f0d0d0;
    border: 1px solid #7a3535;
    font-weight: 500;
}
QPushButton#cancel:hover {
    background: #5e2e2e;
    border-color: #923f3f;
}
QPushButton#cancel:disabled {
    background: #2b1d1d;
    color: #634747;
    border-color: #3d2727;
}

/* Quiet / Ghost button */
QPushButton#quiet, QToolButton#quiet {
    background: transparent;
    border: 1px solid transparent;
    color: #95a399;
}
QPushButton#quiet:hover, QToolButton#quiet:hover {
    background: #222a24;
    border-color: #364239;
    color: #edf2ee;
}

/* Tab button / Segmented toggle */
QToolButton#tab_button {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 6px;
    color: #95a399;
}
QToolButton#tab_button:hover {
    background: #222a24;
    color: #edf2ee;
}
QToolButton#tab_button:checked {
    background: #263329;
    border: 1px solid #3d8b58;
    color: #edf2ee;
}

/* ---- Bug B requirement & WCAG AA contrast for QListWidget ---- */
QListWidget {
    background: #1b211d;
    color: #edf2ee;
    border: 1px solid #2e3831;
    border-radius: 6px;
    padding: 3px;
    outline: none;
    selection-background-color: #2e5c3e;
    selection-color: #e8f5ec;
}
QListWidget::item {
    padding: 7px 8px;
    border-bottom: 1px solid #252e27;
    border-top: none;
    border-left: none;
    border-right: none;
    color: #edf2ee;
    background: #1b211d;
    border-radius: 4px;
    margin-bottom: 2px;
    outline: none;
}
QListWidget::item:hover {
    background: #253029;
    color: #edf2ee;
    padding: 7px 8px;
    border-bottom: 1px solid #252e27;
    border-top: none;
    border-left: none;
    border-right: none;
    border-radius: 4px;
    margin-bottom: 2px;
    outline: none;
}
QListWidget::item:selected {
    background: #2e5c3e;
    color: #e8f5ec;
    padding: 7px 8px;
    border-bottom: 1px solid #252e27;
    border-top: none;
    border-left: none;
    border-right: none;
    border-radius: 4px;
    margin-bottom: 2px;
    outline: none;
}
QListWidget::item:selected:active {
    background: #2e5c3e;
    color: #e8f5ec;
    padding: 7px 8px;
    border-bottom: 1px solid #252e27;
    border-top: none;
    border-left: none;
    border-right: none;
    border-radius: 4px;
    margin-bottom: 2px;
    outline: none;
}
QListWidget::item:selected:!active {
    background: #264a35;
    color: #ddeee3;
    padding: 7px 8px;
    border-bottom: 1px solid #252e27;
    border-top: none;
    border-left: none;
    border-right: none;
    border-radius: 4px;
    margin-bottom: 2px;
    outline: none;
}
QListWidget::item:focus {
    background: #2e5c3e;
    color: #e8f5ec;
    padding: 7px 8px;
    border-bottom: 1px solid #252e27;
    border-top: none;
    border-left: none;
    border-right: none;
    border-radius: 4px;
    margin-bottom: 2px;
    outline: none;
}
QListWidget::item:disabled {
    color: #8da194;
    background: #1a1f1c;
    padding: 7px 8px;
    border-bottom: 1px solid #252e27;
    border-top: none;
    border-left: none;
    border-right: none;
    border-radius: 4px;
    margin-bottom: 2px;
    outline: none;
}

/* ---- Inspector QTabWidget ---- */
QTabWidget::pane {
    border: none;
    background: transparent;
}
QTabBar::tab {
    background: #1c231f;
    color: #95a399;
    border: 1px solid #2c362f;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 12px;
    margin-right: 3px;
    font-size: 8.5pt;
    font-weight: 500;
}
QTabBar::tab:hover {
    background: #242c26;
    color: #edf2ee;
}
QTabBar::tab:selected {
    background: #171c18;
    color: #edf2ee;
    border-color: #344037;
    border-bottom: 2px solid #3d8b58;
}

/* ---- Preview Frame ---- */
QFrame#preview {
    background: #0d100e;
    border: 1px solid #29322b;
    border-radius: 6px;
}

/* ---- Progress Bar & Scrubber Slider ---- */
QProgressBar {
    border: 1px solid #344037;
    border-radius: 5px;
    background: #1c221e;
    text-align: center;
    color: #edf2ee;
    font-size: 8.5pt;
    height: 18px;
}
QProgressBar::chunk {
    background: #3d8b58;
    border-radius: 4px;
}

QSlider::groove:horizontal {
    border: 1px solid #2e3831;
    height: 4px;
    background: #1b211d;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #3d8b58;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #80c497;
    width: 12px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 6px;
}
QSlider::handle:horizontal:disabled {
    background: #3a483e;
}

/* ---- CheckBox ---- */
QCheckBox {
    color: #edf2ee;
    spacing: 8px;
    font-weight: 400;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #344037;
    background: #202722;
}
QCheckBox::indicator:hover {
    border-color: #445448;
}
QCheckBox::indicator:checked {
    background: #2e5c3e;
    border-color: #3d8b58;
}

/* ---- ScrollArea & Menus ---- */
QScrollArea {
    border: none;
    background: transparent;
}
QMenuBar {
    background: #161c18;
    color: #edf2ee;
    border-bottom: 1px solid #232a24;
}
QMenuBar::item:selected {
    background: #242c26;
}
QMenu {
    background: #1a201c;
    color: #edf2ee;
    border: 1px solid #344037;
    border-radius: 6px;
    padding: 4px 0;
}
QMenu::item {
    padding: 6px 20px;
}
QMenu::item:selected {
    background: #27342b;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #2c362f;
    margin: 4px 8px;
}
"""
