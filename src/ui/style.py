"""
Central stylesheet and design tokens for Nasheed Studio.
Approved Palette:
- Deep charcoal canvas: #111317
- Dark graphite panels: #181B21
- Slightly lighter toolbars and section headers: #1E222A
- Input fields and controls: #242933
- Subtle borders: #2E3440
- Primary text: #F0F2F5
- Secondary text: #9CA3AF
- Muted text: #626976
- Blue accent: #6C9FE8 (sparingly: render CTA, active indicators, playhead, focus)
"""

# Named token dictionary
TOKENS = {
    "bg_app": "#111317",
    "bg_canvas": "#0B0C0E",
    "bg_panel": "#181B21",
    "bg_panel_alt": "#1E222A",
    "bg_card": "#20242C",
    "bg_input": "#242933",
    "bg_input_hover": "#2C3240",
    "border_hairline": "#2E3440",
    "border_input": "#2E3440",
    "border_hover": "#3E4554",
    "border_focus": "#4A5364",
    "accent": "#6C9FE8",
    "accent_hover": "#82AEED",
    "accent_pressed": "#5A8DD4",
    "accent_text": "#0E141E",
    "accent_light": "#1E2633",
    "text_main": "#F0F2F5",
    "text_muted": "#9CA3AF",
    "text_subtle": "#626976",
    "text_disabled": "#4F5563",
    "warn_bg": "#2A251A",
    "warn_border": "#635021",
    "warn_text": "#F2BA49",
    "cancel_bg": "#3D2224",
    "cancel_border": "#683034",
    "cancel_text": "#F0D0D0",
}

# Central Application Stylesheet
STYLE = """
/* ---- Root Application Window ---- */
QMainWindow, QWidget#central_root {
    background: #111317;
    color: #F0F2F5;
    font-family: 'Segoe UI Variable', 'Segoe UI', -apple-system, sans-serif;
    font-size: 10pt;
    font-weight: 400;
}

/* ---- Generic Labels & Section Badges ---- */
QLabel {
    color: #F0F2F5;
    font-family: 'Segoe UI Variable', 'Segoe UI', -apple-system, sans-serif;
}
QLabel#app_title {
    font-size: 13pt;
    font-weight: 600;
    color: #F0F2F5;
    letter-spacing: 0.5px;
}
QLabel#app_subtitle {
    font-size: 8.5pt;
    font-weight: 500;
    color: #9CA3AF;
    letter-spacing: 1.2px;
}
QLabel#project_name {
    font-size: 10pt;
    font-weight: 500;
    color: #D0D5DD;
    padding: 0 4px;
}
QLabel#section {
    color: #9CA3AF;
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}
QLabel#muted {
    color: #9CA3AF;
    font-size: 9pt;
}
QLabel#subtle {
    color: #626976;
    font-size: 8pt;
}
QLabel#unsaved_pill {
    background: #332617;
    color: #F2BA49;
    border: 1px solid #635021;
    border-radius: 9px;
    padding: 1px 7px;
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 0.3px;
}
QLabel#saved_pill {
    background: #1C222E;
    color: #6C9FE8;
    border: 1px solid #2B3A52;
    border-radius: 9px;
    padding: 1px 7px;
    font-size: 8pt;
    font-weight: 600;
}
QLabel#warning {
    color: #F2BA49;
    font-size: 8pt;
    font-weight: 500;
    padding: 6px 10px;
    background: #2A251A;
    border: 1px solid #635021;
    border-radius: 4px;
}

/* ---- Panes & Dividers ---- */
QFrame#top_bar {
    background: #181B21;
    border-bottom: 1px solid #2E3440;
    padding: 3px 6px;
}
QFrame#playlist_pane, QFrame#preview_pane, QFrame#inspector_pane {
    background: #181B21;
    border: 1px solid #2E3440;
    border-radius: 6px;
}
QFrame#export_bar {
    background: #1E222A;
    border-top: 1px solid #2E3440;
    border-bottom: 1px solid #2E3440;
    padding: 6px 12px;
}
QFrame#status_bar {
    background: #111317;
    padding: 2px 8px;
}
QFrame#hairline_h {
    background: #2E3440;
    max-height: 1px;
    min-height: 1px;
    border: none;
}
QSplitter::handle {
    background: #181B21;
    width: 4px;
}
QSplitter::handle:hover {
    background: #6C9FE8;
}

/* ---- Input Controls (Uniform 26-28px height, 4px radius) ---- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #242933;
    color: #F0F2F5;
    border: 1px solid #2E3440;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
    selection-background-color: #6C9FE8;
    selection-color: #0E141E;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #3E4554;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #6C9FE8;
    background: #282E3B;
}
QSpinBox, QDoubleSpinBox {
    padding-left: 6px;
    padding-right: 20px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #2E3440;
    border-bottom: 1px solid #2E3440;
    background: #2A303D;
    border-top-right-radius: 3px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
    background: #343C4C;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid #2E3440;
    background: #2A303D;
    border-bottom-right-radius: 3px;
}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: #343C4C;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    width: 0;
    height: 0;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-bottom: 4px solid #9CA3AF;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid #9CA3AF;
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
    border-top: 5px solid #9CA3AF;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background: #1E222A;
    color: #F0F2F5;
    border: 1px solid #2E3440;
    selection-background-color: #2A3446;
    selection-color: #FFFFFF;
    outline: none;
    padding: 4px;
}

/* ---- Buttons & ToolButtons ---- */
QPushButton, QToolButton {
    background: #242933;
    color: #F0F2F5;
    border: 1px solid #2E3440;
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 22px;
    font-weight: 500;
}
QPushButton:hover, QToolButton:hover {
    background: #2C3240;
    border-color: #3E4554;
    color: #FFFFFF;
}
QPushButton:pressed, QToolButton:pressed {
    background: #1F232D;
}
QPushButton:disabled, QToolButton:disabled {
    background: #1B1E25;
    color: #4F5563;
    border-color: #252932;
}
QPushButton:focus, QToolButton:focus {
    border-color: #6C9FE8;
}

/* Primary filled button: Blue accent (Render MP4) */
QPushButton#primary, QToolButton#primary {
    background: #6C9FE8;
    color: #0E141E;
    border: 1px solid #82AEED;
    font-weight: 600;
}
QPushButton#primary:hover, QToolButton#primary:hover {
    background: #82AEED;
    border-color: #98BEF2;
    color: #0E141E;
}
QPushButton#primary:pressed, QToolButton#primary:pressed {
    background: #5A8DD4;
}
QPushButton#primary:disabled, QToolButton#primary:disabled {
    background: #232B38;
    color: #4D5C73;
    border-color: #293444;
}

/* Cancel / Destructive button */
QPushButton#cancel {
    background: #3D2224;
    color: #F0D0D0;
    border: 1px solid #683034;
    font-weight: 500;
}
QPushButton#cancel:hover {
    background: #4D2A2D;
    border-color: #803B40;
}
QPushButton#cancel:disabled {
    background: #241A1B;
    color: #5C4344;
    border-color: #332324;
}

/* Quiet / Ghost button */
QPushButton#quiet, QToolButton#quiet {
    background: transparent;
    border: 1px solid transparent;
    color: #9CA3AF;
}
QPushButton#quiet:hover, QToolButton#quiet:hover {
    background: #242933;
    border-color: #2E3440;
    color: #F0F2F5;
}

/* Tab button / Segmented toggle */
QToolButton#tab_button {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px;
    color: #9CA3AF;
}
QToolButton#tab_button:hover {
    background: #242933;
    color: #F0F2F5;
}
QToolButton#tab_button:checked {
    background: #242F40;
    border: 1px solid #6C9FE8;
    color: #F0F2F5;
}

/* ---- Playlist QListWidget (Clean Flat Rows) ---- */
QListWidget {
    background: #181B21;
    color: #F0F2F5;
    border: 1px solid #2E3440;
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: #253042;
    selection-color: #FFFFFF;
}
QListWidget::item {
    padding: 7px 8px;
    border: 1px solid #242933;
    border-left: 3px solid transparent;
    color: #F0F2F5;
    background: #1E222A;
    border-radius: 4px;
    margin-bottom: 3px;
    outline: none;
}
QListWidget::item:hover {
    color: #FFFFFF;
    background: #242A36;
    border: 1px solid #333B4A;
    border-left: 3px solid transparent;
    outline: none;
}
QListWidget::item:selected {
    background: #253042;
    color: #FFFFFF;
    border: 1px solid #38455C;
    border-left: 3px solid #6C9FE8;
    outline: none;
}
QListWidget::item:selected:active {
    background: #253042;
    color: #FFFFFF;
    border: 1px solid #38455C;
    border-left: 3px solid #6C9FE8;
    outline: none;
}
QListWidget::item:selected:!active {
    background: #222938;
    color: #E2E8F0;
    border: 1px solid #303B4E;
    border-left: 3px solid #6C9FE8;
    outline: none;
}
QListWidget::item:focus {
    background: #253042;
    color: #FFFFFF;
    border: 1px solid #38455C;
    border-left: 3px solid #6C9FE8;
    outline: none;
}
QListWidget::item:disabled {
    color: #626976;
    background: #181B21;
    border: 1px solid #242933;
    outline: none;
}

/* ---- Inspector QTabWidget ---- */
QTabWidget::pane {
    border: none;
    background: transparent;
}
QTabBar::tab {
    background: #181B21;
    color: #9CA3AF;
    border: 1px solid #2E3440;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 7px;
    margin-right: 2px;
    font-size: 8pt;
    font-weight: 500;
}
QTabBar::tab:hover {
    background: #20252E;
    color: #F0F2F5;
}
QTabBar::tab:selected {
    background: #1E222A;
    color: #F0F2F5;
    border-color: #2E3440;
    border-bottom: 2px solid #6C9FE8;
}

/* ---- Inspector Collapsible Section Headers (CapCut / Premiere style) ---- */
QPushButton#twirl_header {
    background: #181B21;
    color: #F0F2F5;
    border: 1px solid #282E3A;
    border-radius: 4px;
    text-align: left;
    padding: 5px 8px;
    font-size: 8.5pt;
    font-weight: 600;
    letter-spacing: 0.3px;
}
QPushButton#twirl_header:hover {
    background: #20252E;
    border-color: #384252;
    color: #FFFFFF;
}
QPushButton#twirl_header:checked {
    background: #1C2028;
    border-color: #2E3440;
    color: #F0F2F5;
}

QLabel#prop_label {
    color: #9CA3AF;
    font-size: 8.5pt;
    font-weight: 500;
}

QLabel#asset_path {
    background: #181B21;
    border: 1px solid #2E3440;
    border-radius: 4px;
    padding: 3px 6px;
    color: #9CA3AF;
    font-size: 8pt;
}

/* ---- Preview Frame ---- */
QFrame#preview {
    background: #0B0C0E;
    border: 1px solid #2E3440;
    border-radius: 6px;
}

/* ---- Progress Bar & Scrubber Slider ---- */
QProgressBar {
    border: 1px solid #2E3440;
    border-radius: 4px;
    background: #181B21;
    text-align: center;
    color: #F0F2F5;
    font-size: 8pt;
    height: 18px;
}
QProgressBar::chunk {
    background: #6C9FE8;
    border-radius: 3px;
}

QSlider::groove:horizontal {
    border: 1px solid #2E3440;
    height: 4px;
    background: #242933;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #6C9FE8;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #F0F2F5;
    width: 12px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 6px;
}
QSlider::handle:horizontal:disabled {
    background: #4F5563;
}

/* ---- CheckBox ---- */
QCheckBox {
    color: #F0F2F5;
    spacing: 8px;
    font-weight: 400;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #2E3440;
    background: #242933;
}
QCheckBox::indicator:hover {
    border-color: #3E4554;
}
QCheckBox::indicator:checked {
    background: #253042;
    border-color: #6C9FE8;
}

/* ---- ScrollArea & Menus ---- */
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    border: none;
    background: #14161B;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #2E3440;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #6C9FE8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: none;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QMenuBar {
    background: #181B21;
    color: #F0F2F5;
    border-bottom: 1px solid #2E3440;
}
QMenuBar::item:selected {
    background: #242933;
}
QMenu {
    background: #1E222A;
    color: #F0F2F5;
    border: 1px solid #2E3440;
    border-radius: 4px;
    padding: 4px 0;
}
QMenu::item {
    padding: 6px 20px;
}
QMenu::item:selected {
    background: #2A3446;
    color: #FFFFFF;
}
QMenu::separator {
    height: 1px;
    background: #2E3440;
    margin: 4px 8px;
}
"""
