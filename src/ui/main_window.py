"""
Main application window.

Phase-1 changes
---------------
Bug C – Export lifecycle
    * RenderThread is replaced by ExportJob (owns FFmpeg via Windows Job Object).
    * A Cancel button terminates the whole process tree.
    * closeEvent asks for confirmation when an export is running and cancels
      before allowing the window to close.
    * Failed, cancelled and completed exports all reach a terminal UI state;
      the Render button re-enables after every terminal state.
    * Duplicate exports are blocked: the Render button is disabled while running.

Bug A – Long filenames distort the layout
    * background_label and logo_label have a fixed maximum width and show an
      ellipsis.  The full path is available as a tooltip.
    * The splitter has minimum sizes so no panel collapses.

Bug B – Selected audio item unreadable
    * QListWidget item selected/focused/hover/disabled states are defined
      explicitly in the stylesheet so the OS default (black-on-black) is
      never reached.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer, QSettings, QEvent
from PySide6.QtGui import QPixmap, QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QListWidget, QListWidgetItem, QLineEdit, QComboBox, QGroupBox,
    QFormLayout, QSplitter, QMessageBox, QProgressBar, QFrame, QAbstractItemView,
    QToolButton, QInputDialog, QSizePolicy, QSpinBox, QScrollArea, QCheckBox,
    QDoubleSpinBox, QSlider,
)
from PIL import Image

from src.services.media_probe import get_duration
from src.services.render_service import build_render_command, RESOLUTIONS
from src.services.export_job import ExportJob, STATE_RUNNING
from src.services.font_service import list_system_font_families, list_family_styles, refresh_fonts
from src.services.compositor import create_composition, create_intro_card, CORNER_POSITIONS


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

STYLE = """
QMainWindow, QWidget {
    background: #171b19;
    color: #e7ece8;
    font-family: 'Segoe UI', sans-serif;
    font-size: 10pt;
}
QLabel#muted  { color: #9ba69f; }
QLabel#heading { font-size: 15pt; font-weight: 650; color: #f4f6f4; }
QLabel#section { color: #c6d1c9; font-size: 9pt; font-weight: 700; letter-spacing: 1px; }
QGroupBox {
    border: 1px solid #343d37;
    border-radius: 9px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
    color: #dbe4dd;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QLineEdit, QComboBox {
    background: #202622;
    color: #edf2ee;
    border: 1px solid #3a453d;
    border-radius: 6px;
    padding: 7px;
    selection-background-color: #4a7a5c;
    selection-color: #edf2ee;
}
/* ---- Bug B fix: explicit states for all list-widget item combinations ---- */
QListWidget {
    background: #202622;
    color: #edf2ee;
    border: 1px solid #3a453d;
    border-radius: 6px;
    padding: 3px;
    outline: none;
}
QListWidget::item {
    padding: 8px 5px;
    border-bottom: 1px solid #303a33;
    color: #edf2ee;
    background: #202622;
}
QListWidget::item:hover {
    background: #253029;
    color: #edf2ee;
}
QListWidget::item:selected {
    background: #2e5c3e;
    color: #e8f5ec;
}
QListWidget::item:selected:active {
    background: #2e5c3e;
    color: #e8f5ec;
}
QListWidget::item:selected:!active {
    background: #264a35;
    color: #ddeee3;
}
QListWidget::item:focus {
    background: #2e5c3e;
    color: #e8f5ec;
}
QListWidget::item:disabled {
    color: #8da194;
    background: #1a1f1c;
}
/* ----------------------------------------------------------------- */
QPushButton, QToolButton {
    background: #29332c;
    color: #e9f0eb;
    border: 1px solid #3e4b42;
    border-radius: 6px;
    padding: 8px 10px;
}
QPushButton:hover, QToolButton:hover { background: #354239; }
QPushButton:disabled, QToolButton:disabled {
    background: #1e2420;
    color: #5c6e62;
    border: 1px solid #2d3630;
}
QPushButton#primary {
    background: #c0e4c9;
    color: #15261b;
    border: 0;
    font-weight: 700;
    padding: 11px 14px;
}
QPushButton#primary:hover  { background: #d2efd9; }
QPushButton#primary:disabled { background: #4a5e50; color: #8a9e90; }
QPushButton#cancel {
    background: #4a2424;
    color: #f0d0d0;
    border: 1px solid #7a3535;
    font-weight: 600;
    padding: 11px 14px;
}
QPushButton#cancel:hover { background: #5e2e2e; }
QPushButton#quiet { background: transparent; }
QFrame#preview { background: #0e110f; border: 1px solid #38423b; border-radius: 8px; }
QProgressBar {
    border: 1px solid #3a453d;
    border-radius: 5px;
    background: #202622;
    text-align: center;
    color: #edf2ee;
    height: 14px;
}
QProgressBar::chunk { background: #b9dfc3; border-radius: 4px; }
QSplitter::handle { background: #242c26; width: 5px; }
QScrollArea { border: none; background: transparent; }
QCheckBox { color: #dbe4dd; spacing: 8px; font-weight: 500; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; border: 1px solid #3a453d; background: #202622; }
QCheckBox::indicator:checked { background: #2e5c3e; border-color: #5c9c74; }
QLabel#warning {
    color: #f2ba49;
    font-size: 8.5pt;
    font-weight: 600;
    padding: 5px 8px;
    background: #2a251a;
    border: 1px solid #635021;
    border-radius: 4px;
}
QSlider::groove:horizontal { border: 1px solid #3a453d; height: 6px; background: #202622; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #4a7a5c; border-radius: 3px; }
QSlider::handle:horizontal { background: #b9dfc3; width: 14px; margin-top: -5px; margin-bottom: -5px; border-radius: 7px; }
"""


# ---------------------------------------------------------------------------
# Qt bridge: relay ExportJob callbacks (worker thread) → Qt signals (main thread)
# ---------------------------------------------------------------------------

class _ExportBridge(QObject):
    progress = Signal(str)
    done = Signal(str)
    failed = Signal(str)
    cancelled = Signal()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Nasheed Studio · Playlist Video Automation")
        self.resize(1440, 900)
        self.setMinimumSize(1120, 720)
        self.background_path = ""
        self.logo_path = ""
        self.cursor_path = ""
        self.sfx_path = ""
        self._previewing_intro = False
        self.tracks: list[dict] = []
        self.project_path = ""
        self._is_dirty = False
        self._last_saved_snapshot: Optional[dict] = None
        self._loading_project = False
        self._is_closing = False
        self._recent_menu = None
        self._committed_title = "Abu Ali Nasheeds Collection"
        self._title_timer = QTimer(self)
        self._title_timer.setSingleShot(True)
        self._title_timer.setInterval(1500)
        self._title_timer.timeout.connect(self._apply_title)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(300)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._job: Optional[ExportJob] = None
        self._bridge = _ExportBridge()
        self._bridge.progress.connect(self._on_progress)
        self._bridge.done.connect(self._render_complete)
        self._bridge.failed.connect(self._render_failed)
        self._bridge.cancelled.connect(self._render_cancelled)
        self._build_ui()
        self._refresh_preview()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        # -- Top bar --
        top = QHBoxLayout()
        brand = QVBoxLayout()
        title_lbl = QLabel("Nasheed Studio")
        title_lbl.setObjectName("heading")
        subtitle = QLabel("PLAYLIST VIDEO AUTOMATION")
        subtitle.setObjectName("muted")
        brand.addWidget(title_lbl)
        brand.addWidget(subtitle)
        top.addLayout(brand)
        top.addStretch(1)
        for label, fn in [("New project", self.new_project),
                           ("Open", self.open_project),
                           ("Save", self.save_project)]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            top.addWidget(b)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # -- Left panel: assets + playlist --
        left = QWidget()
        left.setMinimumWidth(260)
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 4, 0)
        left_l.setSpacing(10)

        assets = QGroupBox("PROJECT ASSETS")
        al = QVBoxLayout(assets)

        # Bug A fix: labels have a fixed max-width so they never stretch the panel.
        # The full path is shown in the tooltip.
        self.background_label = self._make_asset_label("No background selected")
        self.background_btn = QPushButton("Choose background image…")
        self.background_btn.clicked.connect(self.choose_background)

        self.logo_label = self._make_asset_label("No logo selected")
        self.logo_btn = QPushButton("Choose logo…")
        self.logo_btn.clicked.connect(self.choose_logo)

        self.logo_pos_combo = QComboBox()
        self.logo_pos_combo.addItems(["Bottom-Right", "Bottom-Left", "Top-Right", "Top-Left"])
        self.logo_pos_combo.currentTextChanged.connect(self._on_logo_pos_changed)
        logo_pos_row = QHBoxLayout()
        logo_pos_lbl = QLabel("Corner:")
        logo_pos_lbl.setObjectName("muted")
        logo_pos_row.addWidget(logo_pos_lbl)
        logo_pos_row.addWidget(self.logo_pos_combo, 1)

        al.addWidget(self.background_label)
        al.addWidget(self.background_btn)
        al.addSpacing(5)
        al.addWidget(self.logo_label)
        al.addWidget(self.logo_btn)
        al.addLayout(logo_pos_row)
        left_l.addWidget(assets)

        playlist_box = QGroupBox("PLAYLIST")
        pl = QVBoxLayout(playlist_box)
        title_form = QFormLayout()

        title_row = QHBoxLayout()
        self.collection_title = QLineEdit(self._committed_title)
        self.collection_title.textChanged.connect(self._on_title_draft_changed)
        self.collection_title.returnPressed.connect(self._apply_title)
        self.collection_title.installEventFilter(self)

        self.title_apply_btn = QPushButton("Apply")
        self.title_apply_btn.setEnabled(False)
        self.title_apply_btn.setToolTip("Apply title changes (Enter)")
        self.title_apply_btn.clicked.connect(self._apply_title)

        title_row.addWidget(self.collection_title, 1)
        title_row.addWidget(self.title_apply_btn)
        title_form.addRow("Collection title", title_row)
        pl.addLayout(title_form)

        self.track_list = QListWidget()
        self.track_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.track_list.model().rowsMoved.connect(self._on_rows_moved)
        self.track_list.itemDoubleClicked.connect(self.rename_track)
        pl.addWidget(self.track_list, 1)

        row = QHBoxLayout()
        add_btn = QPushButton("＋ Add audio")
        add_btn.clicked.connect(self.add_tracks)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_track)
        row.addWidget(add_btn, 1)
        row.addWidget(remove_btn)
        pl.addLayout(row)

        move = QHBoxLayout()
        up_btn = QPushButton("↑ Move up")
        up_btn.clicked.connect(lambda: self.move_track(-1))
        down_btn = QPushButton("↓ Move down")
        down_btn.clicked.connect(lambda: self.move_track(1))
        move.addWidget(up_btn)
        move.addWidget(down_btn)
        pl.addLayout(move)

        left_l.addWidget(playlist_box, 1)
        splitter.addWidget(left)

        # -- Center panel: preview --
        center = QWidget()
        center.setMinimumWidth(360)
        cl = QVBoxLayout(center)
        cl.setContentsMargins(4, 0, 4, 0)
        cl.setSpacing(10)

        heading_row = QHBoxLayout()
        preview_title = QLabel("VIDEO CANVAS")
        preview_title.setObjectName("section")
        heading_row.addWidget(preview_title)
        heading_row.addStretch()
        self.preview_badge = QLabel("PREVIEW · 16:9")
        self.preview_badge.setObjectName("muted")
        heading_row.addWidget(self.preview_badge)
        cl.addLayout(heading_row)

        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("preview")
        pv = QVBoxLayout(self.preview_frame)
        pv.setContentsMargins(8, 8, 8, 8)
        self.preview_image = QLabel(
            "Choose a background and add audio tracks to preview your composition."
        )
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setMinimumSize(420, 270)
        self.preview_image.setWordWrap(True)
        self.preview_image.setObjectName("muted")
        pv.addWidget(self.preview_image)
        cl.addWidget(self.preview_frame, 1)

        hint = QLabel(
            "Preview shows the selected template and active-track styling. "
            "The exported MP4 uses the calculated audio timeline."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        cl.addWidget(hint)
        splitter.addWidget(center)

        # -- Right panel: design + export (scrollable) --
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setMinimumWidth(280)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 8, 0)
        rl.setSpacing(10)
        right_scroll.setWidget(right)

        # 1. Video Design
        template_box = QGroupBox("VIDEO DESIGN")
        tf = QFormLayout(template_box)
        self.template_combo = QComboBox()
        self.template_combo.addItems(["Cinematic", "Minimal", "Two-column"])
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        tf.addRow("Layout template", self.template_combo)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(list(RESOLUTIONS.keys()))
        self.resolution_combo.currentTextChanged.connect(self._on_resolution_changed)
        tf.addRow("Export resolution", self.resolution_combo)
        self.fps_label = QLabel("30 fps · H.264 / AAC")
        self.fps_label.setObjectName("muted")
        tf.addRow("Encoding", self.fps_label)
        rl.addWidget(template_box)

        # 2. Typography
        typo_box = QGroupBox("TYPOGRAPHY & FONTS")
        tyf = QFormLayout(typo_box)

        self.title_font_combo = QComboBox()
        self.title_font_combo.currentTextChanged.connect(self._on_title_font_changed)
        self.title_style_combo = QComboBox()
        self.title_style_combo.currentTextChanged.connect(self._on_title_style_changed)
        self.title_size_spin = QSpinBox()
        self.title_size_spin.setRange(20, 90)
        self.title_size_spin.setValue(46)
        self.title_size_spin.setSuffix(" px")
        self.title_size_spin.valueChanged.connect(self._on_title_size_changed)

        title_font_row = QHBoxLayout()
        title_font_row.addWidget(self.title_font_combo, 2)
        title_font_row.addWidget(self.title_style_combo, 1)
        title_font_row.addWidget(self.title_size_spin, 1)
        tyf.addRow("Collection title", title_font_row)

        self.track_font_combo = QComboBox()
        self.track_font_combo.currentTextChanged.connect(self._on_track_font_changed)
        self.track_style_combo = QComboBox()
        self.track_style_combo.currentTextChanged.connect(self._on_track_style_changed)
        self.track_size_spin = QSpinBox()
        self.track_size_spin.setRange(12, 48)
        self.track_size_spin.setValue(22)
        self.track_size_spin.setSuffix(" px")
        self.track_size_spin.valueChanged.connect(self._on_track_size_changed)

        track_font_row = QHBoxLayout()
        track_font_row.addWidget(self.track_font_combo, 2)
        track_font_row.addWidget(self.track_style_combo, 1)
        track_font_row.addWidget(self.track_size_spin, 1)
        tyf.addRow("Playlist tracks", track_font_row)

        self.refresh_fonts_btn = QPushButton("🔄 Refresh system fonts")
        self.refresh_fonts_btn.setObjectName("quiet")
        self.refresh_fonts_btn.clicked.connect(lambda: self._refresh_system_fonts(initial=False))
        tyf.addRow("", self.refresh_fonts_btn)

        self._refresh_system_fonts(initial=True)
        rl.addWidget(typo_box)

        # 3. Website Watermark
        web_box = QGroupBox("WEBSITE WATERMARK")
        wf = QFormLayout(web_box)

        self.website_edit = QLineEdit()
        self.website_edit.setPlaceholderText("Optional: e.g. www.nasheedstudio.com")
        self.website_edit.textChanged.connect(self._on_website_text_changed)
        wf.addRow("Website address", self.website_edit)

        web_pos_row = QHBoxLayout()
        self.website_pos_combo = QComboBox()
        self.website_pos_combo.addItems(["Top-Right", "Top-Left", "Bottom-Left", "Bottom-Right"])
        self.website_pos_combo.currentTextChanged.connect(self._on_website_pos_changed)
        self.website_size_spin = QSpinBox()
        self.website_size_spin.setRange(10, 48)
        self.website_size_spin.setValue(18)
        self.website_size_spin.setSuffix(" px")
        self.website_size_spin.valueChanged.connect(self._on_website_size_changed)
        web_pos_row.addWidget(self.website_pos_combo, 2)
        web_pos_row.addWidget(self.website_size_spin, 1)
        wf.addRow("Corner & Size", web_pos_row)

        self.overlap_warning = QLabel("⚠️ Logo and website share the same corner. Position will adjust automatically.")
        self.overlap_warning.setObjectName("warning")
        self.overlap_warning.setWordWrap(True)
        self.overlap_warning.setVisible(False)
        wf.addRow(self.overlap_warning)
        rl.addWidget(web_box)

        # 4. Active Track Indicator
        indicator_box = QGroupBox("ACTIVE TRACK INDICATOR")
        inf = QFormLayout(indicator_box)

        self.indicator_combo = QComboBox()
        self.indicator_combo.addItems([
            "Both (Cursor & Highlight)",
            "Cursor only",
            "Highlight only",
            "Neither (Clean)"
        ])
        self.indicator_combo.currentTextChanged.connect(self._on_indicator_changed)
        inf.addRow("Mode", self.indicator_combo)

        self.cursor_label = self._make_asset_label("Default arrow cursor")
        cursor_btn_row = QHBoxLayout()
        self.cursor_btn = QPushButton("Upload cursor (SVG/PNG)…")
        self.cursor_btn.clicked.connect(self.choose_cursor)
        self.cursor_reset_btn = QPushButton("Reset")
        self.cursor_reset_btn.clicked.connect(self.reset_cursor)
        cursor_btn_row.addWidget(self.cursor_btn, 1)
        cursor_btn_row.addWidget(self.cursor_reset_btn)

        cursor_col = QVBoxLayout()
        cursor_col.addWidget(self.cursor_label)
        cursor_col.addLayout(cursor_btn_row)
        inf.addRow("Cursor asset", cursor_col)

        self.cursor_size_spin = QSpinBox()
        self.cursor_size_spin.setRange(16, 96)
        self.cursor_size_spin.setValue(32)
        self.cursor_size_spin.setSuffix(" px")
        self.cursor_size_spin.valueChanged.connect(self._on_cursor_size_changed)
        inf.addRow("Cursor size", self.cursor_size_spin)
        rl.addWidget(indicator_box)

        # 5. Intro Presentation
        intro_box = QGroupBox("INTRO PRESENTATION")
        intf = QFormLayout(intro_box)

        self.intro_check = QCheckBox("Enable intro sequence")
        self.intro_check.toggled.connect(self._on_intro_toggled)
        intf.addRow(self.intro_check)

        self.intro_dur_spin = QDoubleSpinBox()
        self.intro_dur_spin.setRange(1.0, 10.0)
        self.intro_dur_spin.setValue(3.0)
        self.intro_dur_spin.setSingleStep(0.5)
        self.intro_dur_spin.setSuffix(" s")
        self.intro_dur_spin.valueChanged.connect(self._on_intro_dur_changed)
        intf.addRow("Duration", self.intro_dur_spin)

        self.intro_anim_combo = QComboBox()
        self.intro_anim_combo.addItems(["Fade in / out", "Zoom in", "Slide"])
        self.intro_anim_combo.currentTextChanged.connect(self._on_intro_anim_changed)
        intf.addRow("Animation", self.intro_anim_combo)

        self.preview_intro_btn = QPushButton("👁 Preview Intro Card")
        self.preview_intro_btn.clicked.connect(self._toggle_intro_preview)
        intf.addRow("", self.preview_intro_btn)
        rl.addWidget(intro_box)

        # 6. Transition Sound Effect
        sfx_box = QGroupBox("TRANSITION SOUND EFFECT")
        sfxf = QFormLayout(sfx_box)

        self.sfx_check = QCheckBox("Enable track transition SFX")
        self.sfx_check.toggled.connect(self._on_sfx_toggled)
        sfxf.addRow(self.sfx_check)

        self.sfx_label = self._make_asset_label("No sound effect selected")
        sfx_btn_row = QHBoxLayout()
        self.sfx_btn = QPushButton("Choose SFX…")
        self.sfx_btn.clicked.connect(self.choose_sfx)
        self.sfx_reset_btn = QPushButton("Reset")
        self.sfx_reset_btn.clicked.connect(self.reset_sfx)
        sfx_btn_row.addWidget(self.sfx_btn, 1)
        sfx_btn_row.addWidget(self.sfx_reset_btn)

        sfx_col = QVBoxLayout()
        sfx_col.addWidget(self.sfx_label)
        sfx_col.addLayout(sfx_btn_row)
        sfxf.addRow("SFX file", sfx_col)

        sfx_vol_row = QHBoxLayout()
        self.sfx_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.sfx_vol_slider.setRange(0, 100)
        self.sfx_vol_slider.setValue(70)
        self.sfx_vol_slider.valueChanged.connect(self._on_sfx_vol_changed)
        self.sfx_vol_label = QLabel("70%")
        self.sfx_vol_label.setMinimumWidth(35)
        sfx_vol_row.addWidget(self.sfx_vol_slider, 1)
        sfx_vol_row.addWidget(self.sfx_vol_label)
        sfxf.addRow("Volume", sfx_vol_row)
        rl.addWidget(sfx_box)

        # 7. Export Destination
        output_box = QGroupBox("EXPORT DESTINATION")
        ol = QVBoxLayout(output_box)
        self.output_edit = QLineEdit(str(Path.home() / "Videos" / "nasheed_collection.mp4"))
        self.output_edit.setPlaceholderText("Choose output MP4 path")
        self.output_edit.textChanged.connect(self._mark_dirty)
        browse = QPushButton("Choose output file…")
        browse.clicked.connect(self.choose_output)
        ol.addWidget(self.output_edit)
        ol.addWidget(browse)
        rl.addWidget(output_box)

        # 8. Render
        render_box = QGroupBox("RENDER")
        rv = QVBoxLayout(render_box)
        self.render_summary = QLabel("0 tracks · Add audio files to begin")
        self.render_summary.setObjectName("muted")
        self.render_summary.setWordWrap(True)
        rv.addWidget(self.render_summary)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        rv.addWidget(self.progress)

        self.status_label = QLabel("Ready when you are.")
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        rv.addWidget(self.status_label)

        self.render_btn = QPushButton("Render MP4  →")
        self.render_btn.setObjectName("primary")
        self.render_btn.clicked.connect(self.render_video)
        rv.addWidget(self.render_btn)

        # Bug C: Cancel button
        self.cancel_btn = QPushButton("Cancel export")
        self.cancel_btn.setObjectName("cancel")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_export)
        rv.addWidget(self.cancel_btn)

        rl.addWidget(render_box)
        rl.addStretch(1)

        info = QLabel(
            "Projects save your asset paths, playlist order, template and export "
            "settings. Keep the source media in place when reopening a project."
        )
        info.setObjectName("muted")
        info.setWordWrap(True)
        rl.addWidget(info)

        splitter.addWidget(right_scroll)
        splitter.setSizes([310, 630, 340])
        layout.addWidget(splitter, 1)
        layout.addWidget(splitter, 1)

        self.setStyleSheet(STYLE)

        # Menus
        file_menu = self.menuBar().addMenu("Project")
        new_act = QAction("New project", self)
        new_act.triggered.connect(self.new_project)
        file_menu.addAction(new_act)

        open_act = QAction("Open project…", self)
        open_act.triggered.connect(self.open_project)
        file_menu.addAction(open_act)

        self._recent_menu = file_menu.addMenu("Open recent")
        self._rebuild_recent_menu()

        save_act = QAction("Save project", self)
        save_act.triggered.connect(self.save_project)
        file_menu.addAction(save_act)

        save_as_act = QAction("Save project as…", self)
        save_as_act.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_act)

        help_menu = self.menuBar().addMenu("Help")
        about = QAction("About Nasheed Studio", self)
        about.triggered.connect(lambda: QMessageBox.information(
            self, "About",
            "Nasheed Studio is a local desktop tool for generating "
            "playlist-style Nasheed videos with FFmpeg."
        ))
        help_menu.addAction(about)

    # ------------------------------------------------------------------
    # Bug A helper: constrained asset filename label
    # ------------------------------------------------------------------

    @staticmethod
    def _make_asset_label(text: str) -> QLabel:
        """A label that truncates long filenames with an ellipsis."""
        lbl = QLabel(text)
        lbl.setObjectName("muted")
        lbl.setMaximumWidth(280)
        lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lbl.setTextFormat(Qt.TextFormat.PlainText)
        return lbl

    def _set_asset_label(self, label: QLabel, path: str) -> None:
        """Set label text and tooltip; label elides long text with an ellipsis."""
        name = Path(path).name if path else ""
        label.setToolTip(path or "")
        label.setWordWrap(False)
        if not name:
            label.setText("No file selected")
            return
        fm = label.fontMetrics()
        max_w = label.maximumWidth()
        if max_w > 0:
            elided = fm.elidedText(name, Qt.TextElideMode.ElideMiddle, max_w - 10)
            label.setText(elided)
        else:
            label.setText(name)

    # ------------------------------------------------------------------
    # Project helper
    # ------------------------------------------------------------------

    def _mode_from_combo(self) -> str:
        text = self.indicator_combo.currentText()
        if "Cursor only" in text:
            return "cursor_only"
        if "Highlight only" in text:
            return "highlight_only"
        if "Neither" in text:
            return "neither"
        return "both"

    def _set_combo_from_mode(self, mode: str) -> None:
        mapping = {
            "both": "Both (Cursor & Highlight)",
            "cursor_only": "Cursor only",
            "highlight_only": "Highlight only",
            "neither": "Neither (Clean)",
        }
        self.indicator_combo.setCurrentText(mapping.get(str(mode).lower(), "Both (Cursor & Highlight)"))

    def _on_indicator_changed(self, text: str) -> None:
        self._mark_dirty()
        self._refresh_preview()

    def _on_cursor_size_changed(self, val: int) -> None:
        self._mark_dirty()
        self._schedule_preview(200)

    def choose_cursor(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose custom cursor", "",
            "Vector & Images (*.svg *.png *.jpg *.jpeg *.webp *.bmp);;SVG Vector (*.svg);;PNG Image (*.png);;All files (*.*)"
        )
        if path:
            self.cursor_path = path
            self._set_asset_label(self.cursor_label, path)
            self._mark_dirty()
            self._refresh_preview()

    def reset_cursor(self) -> None:
        if self.cursor_path:
            self.cursor_path = ""
            self._set_asset_label(self.cursor_label, "")
            self.cursor_label.setText("Default arrow cursor")
            self._mark_dirty()
            self._refresh_preview()

    def _project(self) -> dict:
        if self.collection_title.text().strip() != self._committed_title:
            self._apply_title()
        return {
            "version": 1,
            "collection_title": self._committed_title or "Nasheed Collection",
            "background": self.background_path,
            "logo": self.logo_path,
            "logo_position": self.logo_pos_combo.currentText() if hasattr(self, "logo_pos_combo") else "Bottom-Right",
            "tracks": self.tracks,
            "template": self.template_combo.currentText(),
            "resolution": self.resolution_combo.currentText(),
            "indicator_mode": self._mode_from_combo(),
            "cursor_path": self.cursor_path,
            "cursor_size": self.cursor_size_spin.value(),
            "title_font_family": self.title_font_combo.currentText() if hasattr(self, "title_font_combo") else "Segoe UI",
            "title_font_style": self.title_style_combo.currentText() if hasattr(self, "title_style_combo") else "Bold",
            "title_font_size": self.title_size_spin.value() if hasattr(self, "title_size_spin") else 46,
            "track_font_family": self.track_font_combo.currentText() if hasattr(self, "track_font_combo") else "Segoe UI",
            "track_font_style": self.track_style_combo.currentText() if hasattr(self, "track_style_combo") else "Bold",
            "track_font_size": self.track_size_spin.value() if hasattr(self, "track_size_spin") else 22,
            "website_text": self.website_edit.text().strip() if hasattr(self, "website_edit") else "",
            "website_position": self.website_pos_combo.currentText() if hasattr(self, "website_pos_combo") else "Top-Right",
            "website_font_size": self.website_size_spin.value() if hasattr(self, "website_size_spin") else 18,
            "transition_sfx_enabled": self.sfx_check.isChecked() if hasattr(self, "sfx_check") else False,
            "transition_sfx_path": self.sfx_path,
            "transition_sfx_volume": round(self.sfx_vol_slider.value() / 100.0, 2) if hasattr(self, "sfx_vol_slider") else 0.7,
            "intro_enabled": self.intro_check.isChecked() if hasattr(self, "intro_check") else False,
            "intro_duration": self.intro_dur_spin.value() if hasattr(self, "intro_dur_spin") else 3.0,
            "intro_animation": self.intro_anim_combo.currentText() if hasattr(self, "intro_anim_combo") else "Fade in / out",
            "output_path": self.output_edit.text().strip(),
        }

    # ------------------------------------------------------------------
    # Asset pickers
    # ------------------------------------------------------------------

    def choose_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose background image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self.background_path = path
            self._set_asset_label(self.background_label, path)
            self._mark_dirty()
            self._refresh_preview()

    def choose_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose logo", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self.logo_path = path
            self._set_asset_label(self.logo_label, path)
            self._mark_dirty()
            self._check_logo_website_overlap()
            self._refresh_preview()

    # ------------------------------------------------------------------
    # Track management
    # ------------------------------------------------------------------

    def add_tracks(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add audio tracks", "",
            "Audio files (*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus *.wma);;All files (*.*)"
        )
        added = False
        for path in paths:
            if any(t["path"] == path for t in self.tracks):
                continue
            try:
                duration = get_duration(path)
                title = Path(path).stem.replace("_", " ").replace("-", " ").strip()
                self.tracks.append({"title": title, "path": path, "duration": duration})
                added = True
            except Exception as exc:
                QMessageBox.warning(self, "Could not import audio", f"{Path(path).name}\n\n{exc}")
        if added:
            self._mark_dirty()
            self._refresh_tracks()
            self._refresh_preview()

    def _refresh_tracks(self) -> None:
        self.track_list.blockSignals(True)
        self.track_list.clear()
        for i, track in enumerate(self.tracks):
            mins, secs = divmod(int(track.get("duration", 0)), 60)
            item = QListWidgetItem(
                f"{i+1:02d}   {track['title']}\n       {mins:02d}:{secs:02d}  ·  {Path(track['path']).name}"
            )
            item.setData(Qt.ItemDataRole.UserRole, track["path"])
            item.setToolTip(track["path"])
            self.track_list.addItem(item)
        self.track_list.blockSignals(False)
        total = sum(float(t.get("duration", 0)) for t in self.tracks)
        m, s = divmod(int(total), 60)
        self.render_summary.setText(
            f"{len(self.tracks)} tracks · Estimated duration {m:02d}:{s:02d}"
            if self.tracks else "0 tracks · Add audio files to begin"
        )

    def _on_rows_moved(self, *args) -> None:
        by_path = {t["path"]: t for t in self.tracks}
        reordered = []
        for i in range(self.track_list.count()):
            path = self.track_list.item(i).data(Qt.ItemDataRole.UserRole)
            if path in by_path:
                reordered.append(by_path[path])
        if len(reordered) == len(self.tracks):
            self.tracks = reordered
            self._mark_dirty()
        self._refresh_tracks()
        self._refresh_preview()

    def rename_track(self, item: QListWidgetItem) -> None:
        idx = self.track_list.row(item)
        if idx < 0:
            return
        title, ok = QInputDialog.getText(
            self, "Edit playlist title", "Title shown in the video:",
            text=self.tracks[idx]["title"]
        )
        if ok and title.strip():
            self.tracks[idx]["title"] = title.strip()
            self._mark_dirty()
            self._refresh_tracks()
            self._refresh_preview()

    def remove_track(self) -> None:
        idx = self.track_list.currentRow()
        if idx >= 0:
            self.tracks.pop(idx)
            self._mark_dirty()
            self._refresh_tracks()
            self._refresh_preview()

    def move_track(self, delta: int) -> None:
        idx = self.track_list.currentRow()
        target = idx + delta
        if idx < 0 or not (0 <= target < len(self.tracks)):
            return
        self.tracks[idx], self.tracks[target] = self.tracks[target], self.tracks[idx]
        self._mark_dirty()
        self._refresh_tracks()
        self.track_list.setCurrentRow(target)
        self._refresh_preview()

    # ------------------------------------------------------------------
    # Output path
    # ------------------------------------------------------------------

    def choose_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save rendered video", self.output_edit.text(), "MP4 video (*.mp4)"
        )
        if path:
            if not path.lower().endswith(".mp4"):
                path += ".mp4"
            self.output_edit.setText(path)

    # ------------------------------------------------------------------
    # Preview & Title Draft Handling
    # ------------------------------------------------------------------

    def _on_title_draft_changed(self, text: str) -> None:
        if self._loading_project:
            return
        has_diff = (text.strip() != self._committed_title)
        self.title_apply_btn.setEnabled(has_diff)
        if has_diff:
            self._title_timer.start(1500)
        else:
            self._title_timer.stop()

    def _on_title_changed(self, text: str) -> None:
        """Backward compatibility helper."""
        self._on_title_draft_changed(text)

    def _apply_title(self) -> None:
        """Commit the draft title to the project and refresh preview."""
        if hasattr(self, "_title_timer") and self._title_timer.isActive():
            self._title_timer.stop()
        if hasattr(self, "_preview_timer") and self._preview_timer.isActive():
            self._preview_timer.stop()
        if self._loading_project:
            return
        text = self.collection_title.text().strip()
        if text != self._committed_title:
            self._committed_title = text
            self._mark_dirty()
            self._refresh_preview()
        self.title_apply_btn.setEnabled(False)

    def _cancel_title_draft(self) -> None:
        """Discard draft changes and revert to committed title without dirtying."""
        if hasattr(self, "_title_timer") and self._title_timer.isActive():
            self._title_timer.stop()
        self.collection_title.setText(self._committed_title)
        self.title_apply_btn.setEnabled(False)

    def _refresh_system_fonts(self, initial: bool = False) -> None:
        if not initial:
            refresh_fonts()
        families = list_system_font_families()
        cur_title = self.title_font_combo.currentText() if hasattr(self, "title_font_combo") and self.title_font_combo.count() else "Segoe UI"
        cur_track = self.track_font_combo.currentText() if hasattr(self, "track_font_combo") and self.track_font_combo.count() else "Segoe UI"

        self.title_font_combo.blockSignals(True)
        self.track_font_combo.blockSignals(True)
        self.title_font_combo.clear()
        self.track_font_combo.clear()

        self.title_font_combo.addItems(families)
        self.track_font_combo.addItems(families)

        if cur_title in families:
            self.title_font_combo.setCurrentText(cur_title)
        else:
            self.title_font_combo.setCurrentText("Segoe UI" if "Segoe UI" in families else families[0])

        if cur_track in families:
            self.track_font_combo.setCurrentText(cur_track)
        else:
            self.track_font_combo.setCurrentText("Segoe UI" if "Segoe UI" in families else families[0])

        self.title_font_combo.blockSignals(False)
        self.track_font_combo.blockSignals(False)

        self._update_title_styles()
        self._update_track_styles()

        if not initial:
            self._mark_dirty()
            self._schedule_preview(150)

    def _update_title_styles(self) -> None:
        if not hasattr(self, "title_font_combo") or not hasattr(self, "title_style_combo"):
            return
        fam = self.title_font_combo.currentText()
        styles = list_family_styles(fam)
        cur = self.title_style_combo.currentText()
        self.title_style_combo.blockSignals(True)
        self.title_style_combo.clear()
        self.title_style_combo.addItems(styles)
        if cur in styles:
            self.title_style_combo.setCurrentText(cur)
        elif "Bold" in styles:
            self.title_style_combo.setCurrentText("Bold")
        elif "Regular" in styles:
            self.title_style_combo.setCurrentText("Regular")
        self.title_style_combo.blockSignals(False)

    def _update_track_styles(self) -> None:
        if not hasattr(self, "track_font_combo") or not hasattr(self, "track_style_combo"):
            return
        fam = self.track_font_combo.currentText()
        styles = list_family_styles(fam)
        cur = self.track_style_combo.currentText()
        self.track_style_combo.blockSignals(True)
        self.track_style_combo.clear()
        self.track_style_combo.addItems(styles)
        if cur in styles:
            self.track_style_combo.setCurrentText(cur)
        elif "Bold" in styles:
            self.track_style_combo.setCurrentText("Bold")
        elif "Regular" in styles:
            self.track_style_combo.setCurrentText("Regular")
        self.track_style_combo.blockSignals(False)

    def _on_title_font_changed(self, text: str) -> None:
        self._update_title_styles()
        self._mark_dirty()
        self._schedule_preview(150)

    def _on_title_style_changed(self, text: str) -> None:
        self._mark_dirty()
        self._schedule_preview(150)

    def _on_title_size_changed(self, val: int) -> None:
        self._mark_dirty()
        self._schedule_preview(150)

    def _on_track_font_changed(self, text: str) -> None:
        self._update_track_styles()
        self._mark_dirty()
        self._schedule_preview(150)

    def _on_track_style_changed(self, text: str) -> None:
        self._mark_dirty()
        self._schedule_preview(150)

    def _on_track_size_changed(self, val: int) -> None:
        self._mark_dirty()
        self._schedule_preview(150)

    def _on_logo_pos_changed(self, text: str) -> None:
        self._mark_dirty()
        self._check_logo_website_overlap()
        self._refresh_preview()

    def _on_website_text_changed(self, text: str) -> None:
        self._mark_dirty()
        self._check_logo_website_overlap()
        self._schedule_preview(200)

    def _on_website_pos_changed(self, text: str) -> None:
        self._mark_dirty()
        self._check_logo_website_overlap()
        self._refresh_preview()

    def _on_website_size_changed(self, val: int) -> None:
        self._mark_dirty()
        self._schedule_preview(150)

    def _check_logo_website_overlap(self) -> None:
        if not hasattr(self, "overlap_warning") or not hasattr(self, "logo_pos_combo") or not hasattr(self, "website_pos_combo"):
            return
        has_logo = bool(self.logo_path)
        has_web = bool(self.website_edit.text().strip())
        same_corner = (self.logo_pos_combo.currentText().strip().lower() == self.website_pos_combo.currentText().strip().lower())
        self.overlap_warning.setVisible(has_logo and has_web and same_corner)

    def choose_sfx(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose transition sound effect", "",
            "Audio files (*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus *.wma);;All files (*.*)"
        )
        if path:
            self.sfx_path = path
            self._set_asset_label(self.sfx_label, path)
            self._mark_dirty()

    def reset_sfx(self) -> None:
        if self.sfx_path:
            self.sfx_path = ""
            self._set_asset_label(self.sfx_label, "")
            self.sfx_label.setText("No sound effect selected")
            self._mark_dirty()

    def _on_sfx_toggled(self, checked: bool) -> None:
        self._mark_dirty()

    def _on_sfx_vol_changed(self, val: int) -> None:
        if hasattr(self, "sfx_vol_label"):
            self.sfx_vol_label.setText(f"{val}%")
        self._mark_dirty()

    def _on_intro_toggled(self, checked: bool) -> None:
        self._mark_dirty()

    def _on_intro_dur_changed(self, val: float) -> None:
        self._mark_dirty()

    def _on_intro_anim_changed(self, text: str) -> None:
        self._mark_dirty()

    def _toggle_intro_preview(self) -> None:
        self._previewing_intro = not getattr(self, "_previewing_intro", False)
        if hasattr(self, "preview_intro_btn"):
            if self._previewing_intro:
                self.preview_intro_btn.setText("👁 Preview Playlist")
            else:
                self.preview_intro_btn.setText("👁 Preview Intro Card")
        self._refresh_preview()

    def _on_template_changed(self, text: str) -> None:
        self._mark_dirty()
        self._refresh_preview()

    def _on_resolution_changed(self, text: str) -> None:
        self._mark_dirty()
        self._update_resolution_badge()

    def _schedule_preview(self, delay: int = 300) -> None:
        """Debounce preview generation to keep UI responsive during typing/resizing."""
        self._preview_timer.start(delay)

    def _flush_preview(self) -> None:
        """Immediately update preview if an update is pending."""
        if hasattr(self, "_title_timer") and self._title_timer.isActive():
            self._title_timer.stop()
            self._apply_title()
        elif self._preview_timer.isActive():
            self._preview_timer.stop()
            self._refresh_preview()

    def _update_resolution_badge(self) -> None:
        if getattr(self, "_previewing_intro", False):
            self.preview_badge.setText("PREVIEW · INTRO CARD")
            return
        size = RESOLUTIONS[self.resolution_combo.currentText()]
        self.preview_badge.setText(f"PREVIEW · {size[0]} × {size[1]}")

    def _refresh_preview(self) -> None:
        self._update_resolution_badge()
        if not self.background_path or not Path(self.background_path).is_file():
            self.preview_image.setPixmap(QPixmap())
            self.preview_image.setText(
                "Choose a background image and add audio tracks to preview your composition."
            )
            return

        title_fam = self.title_font_combo.currentText() if hasattr(self, "title_font_combo") else "Segoe UI"
        title_style = self.title_style_combo.currentText() if hasattr(self, "title_style_combo") else "Bold"
        title_sz = self.title_size_spin.value() if hasattr(self, "title_size_spin") else 46
        track_fam = self.track_font_combo.currentText() if hasattr(self, "track_font_combo") else "Segoe UI"
        track_style = self.track_style_combo.currentText() if hasattr(self, "track_style_combo") else "Bold"
        track_sz = self.track_size_spin.value() if hasattr(self, "track_size_spin") else 22
        logo_pos = self.logo_pos_combo.currentText() if hasattr(self, "logo_pos_combo") else "Bottom-Right"
        web_txt = self.website_edit.text().strip() if hasattr(self, "website_edit") else ""
        web_pos = self.website_pos_combo.currentText() if hasattr(self, "website_pos_combo") else "Top-Right"
        web_sz = self.website_size_spin.value() if hasattr(self, "website_size_spin") else 18

        # If user is previewing intro presentation card
        if getattr(self, "_previewing_intro", False):
            try:
                with tempfile.TemporaryDirectory(prefix="nasheed_intro_prev_") as tmp:
                    card_path = create_intro_card(
                        width=1280,
                        height=720,
                        background_path=self.background_path,
                        logo_path=self.logo_path or None,
                        collection_title=self._committed_title or "Nasheed Collection",
                        template=self.template_combo.currentText(),
                        out_dir=tmp,
                        title_font_family=title_fam,
                        title_font_style=title_style,
                        title_font_size=max(28, int(title_sz * 1.2)),
                        website_text=web_txt,
                    )
                    pix = QPixmap(card_path)
                    self.preview_image.setPixmap(
                        pix.scaled(
                            self.preview_image.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    self.preview_image.setText("")
            except Exception as exc:
                self.preview_image.setPixmap(QPixmap())
                self.preview_image.setText(f"Intro preview unavailable: {exc}")
            return

        try:
            from src.services.compositor import create_composition
            with tempfile.TemporaryDirectory(prefix="nasheed_preview_") as tmp:
                titles = (
                    [t["title"] for t in self.tracks]
                    or ["Example Nasheed One", "Example Nasheed Two", "Example Nasheed Three"]
                )
                base, overlays = create_composition(
                    width=1280,
                    height=720,
                    background_path=self.background_path,
                    logo_path=self.logo_path or None,
                    collection_title=self._committed_title or "Nasheed Collection",
                    track_titles=titles,
                    template=self.template_combo.currentText(),
                    out_dir=tmp,
                    indicator_mode=self._mode_from_combo(),
                    cursor_path=self.cursor_path or None,
                    cursor_size=self.cursor_size_spin.value(),
                    preview_only_first_overlay=True,
                    title_font_family=title_fam,
                    title_font_style=title_style,
                    title_font_size=title_sz,
                    track_font_family=track_fam,
                    track_font_style=track_style,
                    track_font_size=track_sz,
                    logo_position=logo_pos,
                    website_text=web_txt,
                    website_position=web_pos,
                    website_font_size=web_sz,
                )
                img = Image.open(base).convert("RGBA")
                if overlays:
                    img = Image.alpha_composite(img, Image.open(overlays[0]).convert("RGBA"))
                preview_path = Path(tmp) / "preview.png"
                img.save(preview_path)
                pix = QPixmap(str(preview_path))
                self.preview_image.setPixmap(
                    pix.scaled(
                        self.preview_image.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.preview_image.setText("")
        except Exception as exc:
            self.preview_image.setPixmap(QPixmap())
            self.preview_image.setText(f"Preview unavailable: {exc}")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._schedule_preview(150)

    def eventFilter(self, obj, event):
        if obj == getattr(self, "collection_title", None) and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self._cancel_title_draft()
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Bug C: Export lifecycle
    # ------------------------------------------------------------------

    def render_video(self) -> None:
        # Duplicate-export guard
        if self._job is not None and self._job.is_running:
            QMessageBox.warning(self, "Export in progress",
                                "An export is already running. Cancel it first.")
            return
        if not self.tracks:
            QMessageBox.warning(self, "No audio tracks",
                                "Add at least one audio track before exporting.")
            return
        if not self.background_path:
            QMessageBox.warning(self, "No background",
                                "Choose a background image before exporting.")
            return
        if not self.output_edit.text().strip():
            QMessageBox.warning(self, "No output path", "Choose where to save the MP4.")
            return

        project = self._project()
        try:
            out_path = Path(project["output_path"]).expanduser().resolve()
            work_dir = out_path.parent / f".{out_path.stem}_render_work"
            command, resolved_out = build_render_command(project, work_dir,
                                                         self._bridge.progress.emit)
        except Exception as exc:
            QMessageBox.critical(self, "Cannot start export", str(exc))
            return

        self._job = ExportJob(
            command, work_dir, resolved_out,
            on_progress=self._bridge.progress.emit,
            on_done=self._bridge.done.emit,
            on_failed=self._bridge.failed.emit,
            on_cancelled=self._bridge.cancelled.emit,
        )
        self._set_ui_running(True)
        self._job.start()

    def _cancel_export(self) -> None:
        if self._job and self._job.is_running:
            self._job.cancel()
            self.status_label.setText("Cancelling…")
            self.cancel_btn.setEnabled(False)

    def _set_ui_running(self, running: bool) -> None:
        self.render_btn.setEnabled(not running)
        self.cancel_btn.setVisible(running)
        self.cancel_btn.setEnabled(running)
        self.progress.setVisible(running)
        if running:
            self.status_label.setText("Preparing render…")

    # -- Export callbacks (received on main thread via Qt signals) --

    def _on_progress(self, message: str) -> None:
        self.status_label.setText(message)

    def _render_complete(self, path: str) -> None:
        self._set_ui_running(False)
        self.status_label.setText(f"Export complete: {path}")
        self._job = None
        QMessageBox.information(self, "Video exported",
                                f"Your MP4 has been created:\n\n{path}")

    def _render_failed(self, message: str) -> None:
        self._set_ui_running(False)
        self.status_label.setText("Export failed. See details.")
        self._job = None
        QMessageBox.critical(self, "Render failed", message)

    def _render_cancelled(self) -> None:
        self._set_ui_running(False)
        self.status_label.setText("Export cancelled.")
        self._job = None

    # ------------------------------------------------------------------
    # Bug C: close-event confirmation
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if getattr(self, "_is_closing", False):
            event.ignore()
            return
        self._is_closing = True
        try:
            # 1. Export in progress check
            if self._job and self._job.is_running:
                answer = QMessageBox.question(
                    self, "Export in progress",
                    "An export is running. Cancel it and close?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return

            # 2. Unsaved changes check
            if self.has_unsaved_changes():
                ret = QMessageBox.warning(
                    self, "Unsaved Changes",
                    "Do you want to save changes before closing?",
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Save,
                )
                if ret == QMessageBox.StandardButton.Save:
                    if not self.save_project():
                        event.ignore()
                        return
                elif ret == QMessageBox.StandardButton.Discard:
                    pass
                else:  # Cancel or dialog dismissed
                    event.ignore()
                    return

            # 3. Clean shutdown: cancel export job if still running
            if self._job and self._job.is_running:
                self._job.cancel()
                # Wait briefly for the worker thread to clean up.
                self._job.join(timeout=5.0)

            # 4. Stop timers
            if hasattr(self, "_title_timer") and self._title_timer.isActive():
                self._title_timer.stop()
            if hasattr(self, "_preview_timer") and self._preview_timer.isActive():
                self._preview_timer.stop()

            event.accept()
        finally:
            if not event.isAccepted():
                self._is_closing = False

    # ------------------------------------------------------------------
    # Project persistence & dirty state
    # ------------------------------------------------------------------

    def _mark_dirty(self, *args) -> None:
        if not self._loading_project:
            self._is_dirty = True

    def has_unsaved_changes(self) -> bool:
        if self._is_dirty:
            return True
        if self.collection_title.text().strip() != self._committed_title:
            return True
        if self.project_path:
            if self._last_saved_snapshot is not None:
                return self._project() != self._last_saved_snapshot
            return False
        default_title = "Abu Ali Nasheeds Collection"
        return bool(
            self.tracks
            or self.background_path
            or self.logo_path
            or (self._committed_title != default_title)
            or (hasattr(self, "website_edit") and self.website_edit.text().strip())
            or (hasattr(self, "sfx_path") and self.sfx_path)
            or (hasattr(self, "intro_check") and self.intro_check.isChecked())
            or (hasattr(self, "sfx_check") and self.sfx_check.isChecked())
        )

    def _get_recent_projects(self) -> list[str]:
        settings = QSettings("NasheedStudio", "NasheedStudio")
        val = settings.value("recent_projects", [])
        if isinstance(val, str):
            val = [val] if val else []
        elif not isinstance(val, list):
            val = []
        return [str(p) for p in val if p]

    def _add_recent_project(self, path: str) -> None:
        try:
            resolved = str(Path(path).resolve())
            recents = [p for p in self._get_recent_projects() if str(Path(p).resolve()) != resolved]
            recents.insert(0, path)
            recents = recents[:10]
            settings = QSettings("NasheedStudio", "NasheedStudio")
            settings.setValue("recent_projects", recents)
            self._rebuild_recent_menu()
        except Exception:
            pass

    def _remove_recent_project(self, path: str) -> None:
        try:
            resolved = str(Path(path).resolve())
            recents = [p for p in self._get_recent_projects() if str(Path(p).resolve()) != resolved]
            settings = QSettings("NasheedStudio", "NasheedStudio")
            settings.setValue("recent_projects", recents)
            self._rebuild_recent_menu()
        except Exception:
            pass

    def _clear_recent_projects(self) -> None:
        settings = QSettings("NasheedStudio", "NasheedStudio")
        settings.remove("recent_projects")
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self) -> None:
        if not self._recent_menu:
            return
        self._recent_menu.clear()
        recents = self._get_recent_projects()
        if not recents:
            empty_act = QAction("No recent projects", self)
            empty_act.setEnabled(False)
            self._recent_menu.addAction(empty_act)
            return

        for p in recents:
            name = Path(p).name
            act = QAction(f"{name}  ({p})", self)
            act.setToolTip(p)
            act.triggered.connect(lambda checked=False, target_path=p: self.open_recent_project(target_path))
            self._recent_menu.addAction(act)

        self._recent_menu.addSeparator()
        clear_act = QAction("Clear recent projects", self)
        clear_act.triggered.connect(self._clear_recent_projects)
        self._recent_menu.addAction(clear_act)

    def open_recent_project(self, path: str) -> None:
        if not Path(path).is_file():
            QMessageBox.warning(
                self, "Project not found",
                f"The project file could not be found:\n\n{path}\n\nIt may have been moved, renamed, or deleted."
            )
            self._remove_recent_project(path)
            return
        if self.has_unsaved_changes():
            answer = QMessageBox.question(
                self, "Unsaved changes", "Discard unsaved changes and open project?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._load_project_file(path)

    def new_project(self) -> None:
        if self.has_unsaved_changes():
            answer = QMessageBox.question(
                self, "New project", "Discard the current unsaved project?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._loading_project = True
        try:
            if hasattr(self, "_title_timer") and self._title_timer.isActive():
                self._title_timer.stop()
            self._committed_title = "Abu Ali Nasheeds Collection"
            self.background_path = ""
            self.logo_path = ""
            self.cursor_path = ""
            self.sfx_path = ""
            self._previewing_intro = False
            self.tracks = []
            self.project_path = ""
            self._set_asset_label(self.background_label, "")
            self.background_label.setText("No background selected")
            self._set_asset_label(self.logo_label, "")
            self.logo_label.setText("No logo selected")
            self._set_asset_label(self.cursor_label, "")
            self.cursor_label.setText("Default arrow cursor")
            if hasattr(self, "sfx_label"):
                self._set_asset_label(self.sfx_label, "")
                self.sfx_label.setText("No sound effect selected")
            self.collection_title.setText(self._committed_title)
            self.title_apply_btn.setEnabled(False)
            self.template_combo.setCurrentText("Cinematic")
            self.resolution_combo.setCurrentIndex(0)
            self._set_combo_from_mode("both")
            self.cursor_size_spin.setValue(32)
            if hasattr(self, "logo_pos_combo"):
                self.logo_pos_combo.setCurrentText("Bottom-Right")
            if hasattr(self, "title_font_combo"):
                self.title_font_combo.setCurrentText("Segoe UI" if "Segoe UI" in [self.title_font_combo.itemText(i) for i in range(self.title_font_combo.count())] else self.title_font_combo.itemText(0))
                self.title_style_combo.setCurrentText("Bold")
                self.title_size_spin.setValue(46)
            if hasattr(self, "track_font_combo"):
                self.track_font_combo.setCurrentText("Segoe UI" if "Segoe UI" in [self.track_font_combo.itemText(i) for i in range(self.track_font_combo.count())] else self.track_font_combo.itemText(0))
                self.track_style_combo.setCurrentText("Bold")
                self.track_size_spin.setValue(22)
            if hasattr(self, "website_edit"):
                self.website_edit.setText("")
                self.website_pos_combo.setCurrentText("Top-Right")
                self.website_size_spin.setValue(18)
                self.overlap_warning.setVisible(False)
            if hasattr(self, "intro_check"):
                self.intro_check.setChecked(False)
                self.intro_dur_spin.setValue(3.0)
                self.intro_anim_combo.setCurrentText("Fade in / out")
                self.preview_intro_btn.setText("👁 Preview Intro Card")
            if hasattr(self, "sfx_check"):
                self.sfx_check.setChecked(False)
                self.sfx_vol_slider.setValue(70)
            self.output_edit.setText(str(Path.home() / "Videos" / "nasheed_collection.mp4"))
            self._refresh_tracks()
            self._refresh_preview()
            self._is_dirty = False
            self._last_saved_snapshot = None
            self.status_label.setText("New project ready.")
        finally:
            self._loading_project = False

    def save_project(self) -> bool:
        if not self.project_path:
            return self.save_project_as()
        return self._write_project(self.project_path)

    def save_project_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save project",
            self.project_path or str(Path.home() / "nasheed_project.json"),
            "Nasheed Studio project (*.json)"
        )
        if path:
            if not path.lower().endswith(".json"):
                path += ".json"
            return self._write_project(path)
        return False

    def _write_project(self, path: str) -> bool:
        try:
            payload = json.dumps(self._project(), indent=2)
            Path(path).write_text(payload, encoding="utf-8")
            self.project_path = path
            self._is_dirty = False
            self._last_saved_snapshot = self._project()
            self._add_recent_project(path)
            self.status_label.setText(f"Project saved: {path}")
            return True
        except Exception as exc:
            # Failed save preserves dirty state
            QMessageBox.critical(self, "Save failed", str(exc))
            return False

    def open_project(self) -> None:
        if self.has_unsaved_changes():
            answer = QMessageBox.question(
                self, "Unsaved changes", "Discard unsaved changes and open project?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open project", "", "Nasheed Studio project (*.json)"
        )
        if not path:
            return
        self._load_project_file(path)

    def _load_project_file(self, path: str) -> None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self._loading_project = True
            try:
                if hasattr(self, "_title_timer") and self._title_timer.isActive():
                    self._title_timer.stop()
                self._committed_title = data.get("collection_title", "Nasheed Collection")
                self.background_path = data.get("background", "")
                self.logo_path = data.get("logo", "")
                self.cursor_path = data.get("cursor_path", "")
                self.sfx_path = data.get("transition_sfx_path", "")
                self._previewing_intro = False
                self.tracks = data.get("tracks", [])
                self.collection_title.setText(self._committed_title)
                self.title_apply_btn.setEnabled(False)
                self.template_combo.setCurrentText(data.get("template", "Cinematic"))
                self.resolution_combo.setCurrentText(data.get("resolution", "1080p · Full HD"))
                self._set_combo_from_mode(data.get("indicator_mode", "both"))
                self.cursor_size_spin.setValue(int(data.get("cursor_size", 32) or 32))
                if hasattr(self, "logo_pos_combo"):
                    self.logo_pos_combo.setCurrentText(data.get("logo_position", "Bottom-Right"))
                if hasattr(self, "title_font_combo"):
                    self.title_font_combo.setCurrentText(data.get("title_font_family", "Segoe UI"))
                    self._update_title_styles()
                    self.title_style_combo.setCurrentText(data.get("title_font_style", "Bold"))
                    self.title_size_spin.setValue(int(data.get("title_font_size", 46) or 46))
                if hasattr(self, "track_font_combo"):
                    self.track_font_combo.setCurrentText(data.get("track_font_family", "Segoe UI"))
                    self._update_track_styles()
                    self.track_style_combo.setCurrentText(data.get("track_font_style", "Bold"))
                    self.track_size_spin.setValue(int(data.get("track_font_size", 22) or 22))
                if hasattr(self, "website_edit"):
                    self.website_edit.setText(data.get("website_text", ""))
                    self.website_pos_combo.setCurrentText(data.get("website_position", "Top-Right"))
                    self.website_size_spin.setValue(int(data.get("website_font_size", 18) or 18))
                if hasattr(self, "intro_check"):
                    self.intro_check.setChecked(bool(data.get("intro_enabled", False)))
                    self.intro_dur_spin.setValue(float(data.get("intro_duration", 3.0) or 3.0))
                    self.intro_anim_combo.setCurrentText(data.get("intro_animation", "Fade in / out"))
                    self.preview_intro_btn.setText("👁 Preview Intro Card")
                if hasattr(self, "sfx_check"):
                    self.sfx_check.setChecked(bool(data.get("transition_sfx_enabled", False)))
                    sfx_vol = int(float(data.get("transition_sfx_volume", 0.7) if data.get("transition_sfx_volume") is not None else 0.7) * 100)
                    self.sfx_vol_slider.setValue(sfx_vol)
                self.output_edit.setText(
                    data.get("output_path", str(Path.home() / "Videos" / "nasheed_collection.mp4"))
                )
                self.project_path = path
                self._set_asset_label(self.background_label, self.background_path)
                if not self.background_path:
                    self.background_label.setText("No background selected")
                self._set_asset_label(self.logo_label, self.logo_path)
                if not self.logo_path:
                    self.logo_label.setText("No logo selected")
                if self.cursor_path:
                    self._set_asset_label(self.cursor_label, self.cursor_path)
                else:
                    self._set_asset_label(self.cursor_label, "")
                    self.cursor_label.setText("Default arrow cursor")
                if hasattr(self, "sfx_label"):
                    if self.sfx_path:
                        self._set_asset_label(self.sfx_label, self.sfx_path)
                    else:
                        self._set_asset_label(self.sfx_label, "")
                        self.sfx_label.setText("No sound effect selected")
                self._check_logo_website_overlap()
                self._refresh_tracks()
                self._refresh_preview()
                self._is_dirty = False
                self._last_saved_snapshot = self._project()
            finally:
                self._loading_project = False

            self._add_recent_project(path)
            self.status_label.setText(f"Project opened: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Could not open project", str(exc))
