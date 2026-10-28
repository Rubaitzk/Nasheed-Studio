"""
Main application window for Nasheed Studio.

Stage 2 Architecture
--------------------
- Top bar: app branding, active project name, dynamic "Unsaved" pill, New, Open, Save (only filled button),
  Templates dropdown menu, Inspector toggle. Menus contain rare actions: Save As, Open Recent,
  Apply/Save Reusable Template, Open Workspace Directory.
- Main QSplitter with three horizontal panes:
    1. Playlist pane (min width 260): collection title draft + Apply button, drag-and-drop track list,
       add/remove/reorder controls, track count & duration summary badge, and empty state.
    2. Preview pane (min width 400, stretch 1): 16:9 aspect-ratio constrained canvas, Playlist/Intro card
       preview toggle, and reserved scrubber row (inert until Stage 3).
    3. Inspector pane (min width 280, collapsible): clean icon tab strip with 4 tabs replacing stacked boxes:
       Tab 1: Layout & Assets (template, background, logo, logo corner).
       Tab 2: Text (title & track font family/style/size, refresh fonts).
       Tab 3: Indicator & Watermark (cursor/highlight mode, custom cursor + size, website watermark, overlap warning).
       Tab 4: Intro & Sound (intro toggle/duration/animation, transition SFX + volume).
- Export bar (full width, bottom, outside inspector): output path + browse, resolution + encoding, resource profile
  combo, Render MP4 (accent filled). While job runs: displays progress bar and Cancel export in the same bar.
- Thin status bar: left status message, right project/track summary.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional, Union

from PySide6.QtCore import Qt, Signal, QObject, QTimer, QSettings, QEvent, QSize, QUrl
from PySide6.QtGui import QPixmap, QAction, QIcon, QDragEnterEvent, QDropEvent, QColor, QPainter, QImage
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QListWidget, QListWidgetItem, QLineEdit, QComboBox,
    QFormLayout, QSplitter, QMessageBox, QProgressBar, QFrame, QAbstractItemView,
    QToolButton, QInputDialog, QSizePolicy, QSpinBox, QScrollArea, QCheckBox,
    QDoubleSpinBox, QSlider, QTabWidget, QMenu, QStyledItemDelegate, QStyleOptionViewItem, QStyle,
    QColorDialog,
)
from PIL import Image

from src.services.media_probe import get_duration, is_video_file, get_video_info
from src.services.render_service import build_render_command, RESOLUTIONS
from src.services.export_job import ExportJob, STATE_RUNNING
from src.services.font_service import list_system_font_families, list_family_styles, refresh_fonts
from src.services.compositor import create_composition, create_intro_card, CORNER_POSITIONS, _hex_to_rgb
from src.services.workspace_service import (
    get_workspace_root, get_projects_dir, get_templates_dir,
    get_exports_dir, get_temp_dir, create_job_work_dir,
    cleanup_job_work_dir, clean_stale_temp_dirs, reset_workspace_root,
)
from src.services.export_service import (
    generate_job_id, get_staging_path, cleanup_staging,
)
from src.services.project_service import (
    discover_user_templates,
    save_project_atomic, extract_template, save_template_atomic,
    load_template, apply_template_to_project, check_missing_assets,
)
from src.ui.icons import get_svg_icon, get_svg_pixmap
from src.ui.style import STYLE, TOKENS


def _set_combo_case_insensitive(combo: Any, text: Any) -> bool:
    """
    Set QComboBox or QFontComboBox current index matching text case-insensitively,
    handling hyphens, spaces, slashes, and substrings safely.
    """
    if text is None or not hasattr(combo, "findText"):
        return False
    s_val = str(text).strip()
    if not s_val:
        return False

    # 1. Exact match
    idx = combo.findText(s_val)
    if idx >= 0:
        combo.setCurrentIndex(idx)
        return True

    # 2. Case-insensitive exact match
    target_lower = s_val.lower()
    for i in range(combo.count()):
        if combo.itemText(i).strip().lower() == target_lower:
            combo.setCurrentIndex(i)
            return True

    # 3. Normalized punctuation-tolerant match (e.g. "two-column" vs "Two Column", "fade in / out" vs "fade in/out")
    norm_target = target_lower.replace("-", " ").replace("_", " ").replace("/", " ").replace("·", " ")
    norm_target = " ".join(norm_target.split())
    for i in range(combo.count()):
        norm_item = combo.itemText(i).strip().lower().replace("-", " ").replace("_", " ").replace("/", " ").replace("·", " ")
        norm_item = " ".join(norm_item.split())
        if norm_item == norm_target:
            combo.setCurrentIndex(i)
            return True

    # 4. Substring / contains match
    for i in range(combo.count()):
        item_lower = combo.itemText(i).strip().lower()
        if target_lower in item_lower or item_lower in target_lower:
            combo.setCurrentIndex(i)
            return True

    return False


# ---------------------------------------------------------------------------
# Qt bridge: relay ExportJob callbacks (worker thread) → Qt signals (main thread)
# ---------------------------------------------------------------------------

class _ExportBridge(QObject):
    progress = Signal(str)
    done = Signal(str)
    failed = Signal(str)
    cancelled = Signal()


# ---------------------------------------------------------------------------
# Aspect ratio container (Strict 16:9 Canvas)
# ---------------------------------------------------------------------------

class AspectRatioContainer(QWidget):
    """Container widget that centers and constrains its child to a 16:9 aspect ratio."""

    def __init__(self, child_widget: QWidget, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.child = child_widget
        self.child.setParent(self)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(360, 202)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        margin = 8
        avail_w = max(10, self.width() - margin * 2)
        avail_h = max(10, self.height() - margin * 2)

        target_w = avail_w
        target_h = int(target_w * 9 / 16)
        if target_h > avail_h:
            target_h = avail_h
            target_w = int(target_h * 16 / 9)

        x = (self.width() - target_w) // 2
        y = (self.height() - target_h) // 2
        self.child.setGeometry(x, y, target_w, target_h)


# ---------------------------------------------------------------------------
# Drag & Drop Aware Track List with Crisp Rendering
# ---------------------------------------------------------------------------

class PlaylistDelegate(QStyledItemDelegate):
    """Item delegate that removes State_HasFocus to prevent dotted focus rects or white artifacts."""

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, opt, index)


class PlaylistListWidget(QListWidget):
    """QListWidget that supports internal reordering and external audio file drops."""

    def __init__(self, main_window: MainWindow, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.setItemDelegate(PlaylistDelegate(self))
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                lp = url.toLocalFile()
                if lp and Path(lp).suffix.lower() in [
                    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"
                ]:
                    paths.append(lp)
            if paths:
                self.main_window.import_audio_paths(paths)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_F2:
            self.main_window._on_rename_track_clicked()
            event.accept()
            return
        super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Nasheed Studio · Playlist Video Automation")
        self.resize(1440, 900)
        self.setMinimumSize(1120, 720)

        # Asset state
        self.background_path = ""
        self.background_type = "image"
        self.video_fit_mode = "Fill / Crop (Cover)"
        self.video_start_time = 0.0
        self.video_loop = True
        self.video_mute_audio = True
        self._video_player: Optional[QMediaPlayer] = None
        self._video_sink: Optional[QVideoSink] = None
        self._is_preview_playing = False
        self._current_overlay_pixmap: Optional[QPixmap] = None
        self.logo_path = ""
        self.cursor_path = ""
        self.sfx_path = ""
        self.highlight_color = (248, 220, 139)
        self.title_color = (255, 255, 255)
        self.track_color = (255, 255, 255)
        self.custom_title_font_path = ""
        self.custom_track_font_path = ""
        self.website_font_family: Optional[str] = None
        self.website_font_style: str = "Regular"
        self.website_color = None
        self._previewing_intro = False
        self.tracks: list[dict] = []
        self.project_path = ""
        self.missing_assets: list[str] = []
        self._is_dirty = False
        self._last_saved_snapshot: Optional[dict] = None
        self._loading_project = False
        self._is_closing = False
        self._recent_menu: Optional[QMenu] = None
        self._committed_title = "Abu Ali Nasheeds Collection"
        self._last_inspector_width = 320

        # Preview cache
        self._cached_preview_key = None
        self._cached_preview_pixmap: Optional[QPixmap] = None

        # Timers
        self._title_timer = QTimer(self)
        self._title_timer.setSingleShot(True)
        self._title_timer.setInterval(1500)
        self._title_timer.timeout.connect(self._apply_title)

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(300)
        self._preview_timer.timeout.connect(self._refresh_preview)

        # Export & Process Job Bridge
        self._job: Optional[ExportJob] = None
        self._bridge = _ExportBridge()
        self._bridge.progress.connect(self._on_progress)
        self._bridge.done.connect(self._render_complete)
        self._bridge.failed.connect(self._render_failed)
        self._bridge.cancelled.connect(self._render_cancelled)

        clean_stale_temp_dirs()
        self._build_ui()
        self._update_highlight_color_btn()
        self._update_title_color_btn()
        self._update_track_color_btn()
        self._update_project_ui_indicators()
        self._refresh_preview()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setStyleSheet(STYLE)

        root = QWidget()
        root.setObjectName("central_root")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 10, 12, 8)
        root_layout.setSpacing(8)

        # --------------------------------------------------------------
        # 1. Top Bar
        # --------------------------------------------------------------
        top_bar = QFrame()
        top_bar.setObjectName("top_bar")
        tbl = QHBoxLayout(top_bar)
        tbl.setContentsMargins(10, 6, 10, 6)
        tbl.setSpacing(10)

        # App Brand & Name
        brand_icon = QLabel()
        brand_icon.setPixmap(get_svg_pixmap("app", 20, "#3d8b58"))
        tbl.addWidget(brand_icon)

        title_lbl = QLabel("Nasheed Studio")
        title_lbl.setObjectName("app_title")
        tbl.addWidget(title_lbl)

        tbl.addSpacing(6)
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setObjectName("hairline_h")
        sep1.setFixedWidth(1)
        tbl.addWidget(sep1)
        tbl.addSpacing(6)

        # Project Name & Unsaved Pill
        self.project_name_label = QLabel("Abu Ali Nasheeds Collection")
        self.project_name_label.setObjectName("project_name")
        self.project_name_label.setToolTip("Active Project Name")
        tbl.addWidget(self.project_name_label)

        self.unsaved_pill = QLabel("Unsaved")
        self.unsaved_pill.setObjectName("unsaved_pill")
        self.unsaved_pill.setVisible(False)
        tbl.addWidget(self.unsaved_pill)

        tbl.addStretch(1)

        # Top Bar Action Buttons
        self.new_btn = QPushButton("New")
        self.new_btn.setIcon(get_svg_icon("new", 14, "#edf2ee"))
        self.new_btn.setToolTip("Create new project (Ctrl+N)")
        self.new_btn.clicked.connect(self.new_project)
        tbl.addWidget(self.new_btn)

        self.open_btn = QPushButton("Open")
        self.open_btn.setIcon(get_svg_icon("open", 14, "#edf2ee"))
        self.open_btn.setToolTip("Open existing project (Ctrl+O)")
        self.open_btn.clicked.connect(self.open_project)
        tbl.addWidget(self.open_btn)

        # Save is the ONLY filled button in the top bar
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("primary")
        self.save_btn.setIcon(get_svg_icon("save", 14, "#ffffff"))
        self.save_btn.setToolTip("Save project changes (Ctrl+S)")
        self.save_btn.clicked.connect(self.save_project)
        tbl.addWidget(self.save_btn)

        # Templates dropdown menu button
        self.templates_btn = QToolButton()
        self.templates_btn.setText("Templates ▾")
        self.templates_btn.setIcon(get_svg_icon("template", 14, "#edf2ee"))
        self.templates_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        tmpl_menu = QMenu(self.templates_btn)
        act_apply_tmpl = tmpl_menu.addAction("Apply Reusable Template…")
        act_apply_tmpl.triggered.connect(self.apply_template)
        act_save_tmpl = tmpl_menu.addAction("Save as Reusable Template…")
        act_save_tmpl.triggered.connect(self.save_as_template)
        tmpl_menu.addSeparator()

        self._populate_templates_menu(tmpl_menu)

        self.templates_btn.setMenu(tmpl_menu)
        tbl.addWidget(self.templates_btn)

        # Inspector toggle button
        self.inspector_toggle_btn = QToolButton()
        self.inspector_toggle_btn.setText("Inspector")
        self.inspector_toggle_btn.setIcon(get_svg_icon("inspector", 14, "#edf2ee"))
        self.inspector_toggle_btn.setCheckable(True)
        self.inspector_toggle_btn.setChecked(True)
        self.inspector_toggle_btn.setToolTip("Toggle Inspector Panel")
        self.inspector_toggle_btn.clicked.connect(self.toggle_inspector)
        tbl.addWidget(self.inspector_toggle_btn)

        root_layout.addWidget(top_bar)

        # --------------------------------------------------------------
        # 2. Main QSplitter (Three Panes)
        # --------------------------------------------------------------
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # Pane 1: Playlist Pane (min 260)
        self.playlist_panel = QFrame()
        self.playlist_panel.setObjectName("playlist_pane")
        self.playlist_panel.setMinimumWidth(260)
        pl_layout = QVBoxLayout(self.playlist_panel)
        pl_layout.setContentsMargins(10, 10, 10, 10)
        pl_layout.setSpacing(8)

        # Header: Collection Title Form
        pl_hdr = QLabel("PLAYLIST & AUDIO")
        pl_hdr.setObjectName("section")
        pl_layout.addWidget(pl_hdr)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title_lbl_hint = QLabel("Collection Title")
        title_lbl_hint.setObjectName("muted")
        title_col.addWidget(title_lbl_hint)

        title_input_row = QHBoxLayout()
        title_input_row.setSpacing(6)
        self.collection_title = QLineEdit(self._committed_title)
        self.collection_title.setPlaceholderText("Collection title shown in video")
        self.collection_title.textChanged.connect(self._on_title_draft_changed)
        self.collection_title.returnPressed.connect(self._apply_title)
        self.collection_title.installEventFilter(self)

        self.title_apply_btn = QPushButton("Apply")
        self.title_apply_btn.setEnabled(False)
        self.title_apply_btn.setToolTip("Commit title changes (Enter)")
        self.title_apply_btn.clicked.connect(self._apply_title)

        title_input_row.addWidget(self.collection_title, 1)
        title_input_row.addWidget(self.title_apply_btn)
        title_col.addLayout(title_input_row)
        pl_layout.addLayout(title_col)

        # Hairline divider
        hl1 = QFrame()
        hl1.setObjectName("hairline_h")
        hl1.setFrameShape(QFrame.Shape.HLine)
        pl_layout.addWidget(hl1)

        # Track List (with DnD and Double-Click rename)
        self.track_list = PlaylistListWidget(self)
        self.track_list.model().rowsMoved.connect(self._on_rows_moved)
        self.track_list.itemDoubleClicked.connect(self.rename_track)
        self.track_list.currentRowChanged.connect(self._on_track_row_changed)
        pl_layout.addWidget(self.track_list, 1)

        # Action Buttons: Add, Remove, Move Up, Move Down
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.add_tracks_btn = QPushButton("Add audio")
        self.add_tracks_btn.setIcon(get_svg_icon("add", 13, "#edf2ee"))
        self.add_tracks_btn.setToolTip("Add audio files (MP3, WAV, M4A, AAC, FLAC)")
        self.add_tracks_btn.clicked.connect(self.add_tracks)

        self.rename_track_btn = QPushButton("Edit title")
        self.rename_track_btn.setIcon(get_svg_icon("edit", 13, "#edf2ee"))
        self.rename_track_btn.setToolTip("Rename / adjust selected nasheed title (F2)")
        self.rename_track_btn.clicked.connect(self._on_rename_track_clicked)

        self.remove_track_btn = QPushButton("Remove")
        self.remove_track_btn.setIcon(get_svg_icon("remove", 13, "#edf2ee"))
        self.remove_track_btn.clicked.connect(self.remove_track)

        self.up_btn = QPushButton()
        self.up_btn.setIcon(get_svg_icon("up", 13, "#edf2ee"))
        self.up_btn.setToolTip("Move selected track up")
        self.up_btn.clicked.connect(lambda: self.move_track(-1))

        self.down_btn = QPushButton()
        self.down_btn.setIcon(get_svg_icon("down", 13, "#edf2ee"))
        self.down_btn.setToolTip("Move selected track down")
        self.down_btn.clicked.connect(lambda: self.move_track(1))

        btn_row.addWidget(self.add_tracks_btn, 1)
        btn_row.addWidget(self.rename_track_btn)
        btn_row.addWidget(self.remove_track_btn)
        btn_row.addWidget(self.up_btn)
        btn_row.addWidget(self.down_btn)
        pl_layout.addLayout(btn_row)

        # Playlist Summary Line Badge
        self.playlist_summary_label = QLabel("0 tracks · Add audio files to begin")
        self.playlist_summary_label.setObjectName("subtle")
        self.playlist_summary_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        pl_layout.addWidget(self.playlist_summary_label)

        self.splitter.addWidget(self.playlist_panel)

        # Pane 2: Preview Pane (min 400, stretch 1)
        self.preview_panel = QFrame()
        self.preview_panel.setObjectName("preview_pane")
        self.preview_panel.setMinimumWidth(400)
        pv_layout = QVBoxLayout(self.preview_panel)
        pv_layout.setContentsMargins(10, 10, 10, 10)
        pv_layout.setSpacing(8)

        # Canvas Header Toolbar
        pv_hdr = QHBoxLayout()
        pv_title = QLabel("VIDEO CANVAS")
        pv_title.setObjectName("section")
        pv_hdr.addWidget(pv_title)
        pv_hdr.addStretch(1)

        self.preview_badge = QLabel("PREVIEW · 16:9 · 1080p")
        self.preview_badge.setObjectName("muted")
        pv_hdr.addWidget(self.preview_badge)

        self.preview_intro_btn = QPushButton("Preview Intro Card")
        self.preview_intro_btn.setIcon(get_svg_icon("eye", 13, "#edf2ee"))
        self.preview_intro_btn.setToolTip("Toggle between composition preview and intro card preview")
        self.preview_intro_btn.clicked.connect(self._toggle_intro_preview)
        pv_hdr.addWidget(self.preview_intro_btn)

        self.play_preview_btn = QPushButton("Play Video Preview")
        self.play_preview_btn.setIcon(get_svg_icon("play", 13, "#edf2ee"))
        self.play_preview_btn.setToolTip("Toggle live playback of video background preview")
        self.play_preview_btn.clicked.connect(self._toggle_video_preview)
        self.play_preview_btn.setVisible(False)
        pv_hdr.addWidget(self.play_preview_btn)
        pv_layout.addLayout(pv_hdr)

        # 16:9 Frame inside AspectRatioContainer
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("preview")
        pf_layout = QVBoxLayout(self.preview_frame)
        pf_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_image = QLabel("Drop audio files here or choose a background to preview.")
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setWordWrap(True)
        self.preview_image.setObjectName("muted")
        pf_layout.addWidget(self.preview_image)

        self.preview_container = AspectRatioContainer(self.preview_frame)
        pv_layout.addWidget(self.preview_container, 1)

        # Reserved Scrubber Row (Inert until Stage 3)
        scrubber_row = QHBoxLayout()
        scrubber_row.setSpacing(8)
        self.scrubber_cur_label = QLabel("00:00")
        self.scrubber_cur_label.setObjectName("subtle")

        self.timeline_scrubber = QSlider(Qt.Orientation.Horizontal)
        self.timeline_scrubber.setRange(0, 100)
        self.timeline_scrubber.setValue(0)
        self.timeline_scrubber.setEnabled(False)  # Inert until Stage 3
        self.timeline_scrubber.setToolTip("Timeline navigation (available in Stage 3)")

        self.scrubber_total_label = QLabel("00:00")
        self.scrubber_total_label.setObjectName("subtle")

        scrubber_row.addWidget(self.scrubber_cur_label)
        scrubber_row.addWidget(self.timeline_scrubber, 1)
        scrubber_row.addWidget(self.scrubber_total_label)
        pv_layout.addLayout(scrubber_row)

        self.splitter.addWidget(self.preview_panel)

        # Pane 3: Inspector Pane (min 280, collapsible)
        self.inspector_panel = QFrame()
        self.inspector_panel.setObjectName("inspector_pane")
        self.inspector_panel.setMinimumWidth(280)
        insp_layout = QVBoxLayout(self.inspector_panel)
        insp_layout.setContentsMargins(8, 8, 8, 8)
        insp_layout.setSpacing(6)

        insp_hdr = QLabel("INSPECTOR")
        insp_hdr.setObjectName("section")
        insp_layout.addWidget(insp_hdr)

        # 4-Tab Icon Tab Strip
        self.inspector_tabs = QTabWidget()
        self.inspector_tabs.setObjectName("inspector_tabs")

        # Tab 1: Layout & Assets
        t1_scroll, t1_layout = self._create_tab_scroll()
        self._build_tab_layout_assets(t1_layout)
        self.inspector_tabs.addTab(t1_scroll, get_svg_icon("tab_layout", 14, "#95a399"), "Layout")
        self.inspector_tabs.setTabToolTip(0, "Layout & Project Assets")

        # Tab 2: Text
        t2_scroll, t2_layout = self._create_tab_scroll()
        self._build_tab_text(t2_layout)
        self.inspector_tabs.addTab(t2_scroll, get_svg_icon("tab_text", 14, "#95a399"), "Text")
        self.inspector_tabs.setTabToolTip(1, "Typography & Fonts")

        # Tab 3: Indicator & Watermark
        t3_scroll, t3_layout = self._create_tab_scroll()
        self._build_tab_indicator_watermark(t3_layout)
        self.inspector_tabs.addTab(t3_scroll, get_svg_icon("tab_indicator", 14, "#95a399"), "Indicator")
        self.inspector_tabs.setTabToolTip(2, "Track Indicator & Website Watermark")

        # Tab 4: Intro & Sound
        t4_scroll, t4_layout = self._create_tab_scroll()
        self._build_tab_intro_sound(t4_layout)
        self.inspector_tabs.addTab(t4_scroll, get_svg_icon("tab_intro", 14, "#95a399"), "Sound")
        self.inspector_tabs.setTabToolTip(3, "Intro Card & Sound Effects")

        insp_layout.addWidget(self.inspector_tabs, 1)
        self.splitter.addWidget(self.inspector_panel)

        # Set default splitter weights & stretch
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([310, 620, 320])
        root_layout.addWidget(self.splitter, 1)

        # --------------------------------------------------------------
        # 3. Export Bar (Full width, bottom, outside inspector)
        # --------------------------------------------------------------
        export_bar = QFrame()
        export_bar.setObjectName("export_bar")
        eb_layout = QHBoxLayout(export_bar)
        eb_layout.setContentsMargins(12, 6, 12, 6)
        eb_layout.setSpacing(10)

        # Output destination
        out_col = QHBoxLayout()
        out_col.setSpacing(6)
        out_lbl = QLabel("Export:")
        out_lbl.setObjectName("muted")
        out_col.addWidget(out_lbl)

        self.output_edit = QLineEdit(str(get_exports_dir() / "nasheed_collection.mp4"))
        self.output_edit.setPlaceholderText("Target MP4 destination path")
        self.output_edit.textChanged.connect(self._mark_dirty)
        out_col.addWidget(self.output_edit, 1)

        self.choose_output_btn = QPushButton("Browse…")
        self.choose_output_btn.setIcon(get_svg_icon("folder", 13, "#edf2ee"))
        self.choose_output_btn.clicked.connect(self.choose_output)
        out_col.addWidget(self.choose_output_btn)
        eb_layout.addLayout(out_col, 2)

        # Resolution & Encoding
        res_col = QHBoxLayout()
        res_col.setSpacing(6)
        res_lbl = QLabel("Resolution:")
        res_lbl.setObjectName("muted")
        res_col.addWidget(res_lbl)

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(list(RESOLUTIONS.keys()))
        self.resolution_combo.currentTextChanged.connect(self._on_resolution_changed)
        res_col.addWidget(self.resolution_combo)

        self.fps_label = QLabel("30 fps · H.264")
        self.fps_label.setObjectName("subtle")
        res_col.addWidget(self.fps_label)
        eb_layout.addLayout(res_col, 1)

        # Encoder Resource Profile (Inert hook for Stage 4)
        prof_col = QHBoxLayout()
        prof_col.setSpacing(6)
        prof_lbl = QLabel("Profile:")
        prof_lbl.setObjectName("muted")
        prof_col.addWidget(prof_lbl)

        self.resource_profile_combo = QComboBox()
        self.resource_profile_combo.addItems(["Balanced", "Background-friendly", "Maximum-speed"])
        self.resource_profile_combo.setToolTip("Encoder resource profile (Stage 4)")
        prof_col.addWidget(self.resource_profile_combo)
        eb_layout.addLayout(prof_col)

        # Progress bar (visible during active job)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setMinimumWidth(120)
        eb_layout.addWidget(self.progress)

        # Cancel button (visible during active job)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancel")
        self.cancel_btn.setIcon(get_svg_icon("cancel", 12, "#f0d0d0"))
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_export)
        eb_layout.addWidget(self.cancel_btn)

        # Render button (Filled green primary button)
        self.render_btn = QPushButton("Render MP4 →")
        self.render_btn.setObjectName("primary")
        self.render_btn.setIcon(get_svg_icon("render", 13, "#ffffff"))
        self.render_btn.clicked.connect(self.render_video)
        eb_layout.addWidget(self.render_btn)

        root_layout.addWidget(export_bar)

        # --------------------------------------------------------------
        # 4. Thin Status Bar
        # --------------------------------------------------------------
        status_bar = QFrame()
        status_bar.setObjectName("status_bar")
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(6, 2, 6, 2)
        sb_layout.setSpacing(12)

        self.status_label = QLabel("Ready when you are.")
        self.status_label.setObjectName("muted")
        sb_layout.addWidget(self.status_label, 1)

        self.render_summary = QLabel("0 tracks · Add audio files to begin")
        self.render_summary.setObjectName("subtle")
        self.render_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        sb_layout.addWidget(self.render_summary)

        root_layout.addWidget(status_bar)

        # --------------------------------------------------------------
        # 5. Application Menus (Rare actions)
        # --------------------------------------------------------------
        file_menu = self.menuBar().addMenu("Project")

        new_act = QAction("New project", self)
        new_act.setShortcut("Ctrl+N")
        new_act.triggered.connect(self.new_project)
        file_menu.addAction(new_act)

        open_act = QAction("Open project…", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_project)
        file_menu.addAction(open_act)

        self._recent_menu = file_menu.addMenu("Open recent")
        self._rebuild_recent_menu()

        save_act = QAction("Save project", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_project)
        file_menu.addAction(save_act)

        save_as_act = QAction("Save project as…", self)
        save_as_act.setShortcut("Ctrl+Shift+S")
        save_as_act.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_act)

        file_menu.addSeparator()

        apply_tmpl_act = QAction("Apply Reusable Template…", self)
        apply_tmpl_act.triggered.connect(self.apply_template)
        file_menu.addAction(apply_tmpl_act)

        save_tmpl_act = QAction("Save as Reusable Template…", self)
        save_tmpl_act.triggered.connect(self.save_as_template)
        file_menu.addAction(save_tmpl_act)

        file_menu.addSeparator()

        workspace_act = QAction("Open Workspace Directory", self)
        workspace_act.triggered.connect(self.open_workspace)
        file_menu.addAction(workspace_act)

        reset_ws_act = QAction("Reset Workspace Location to Default", self)
        reset_ws_act.triggered.connect(self.reset_workspace)
        file_menu.addAction(reset_ws_act)

        help_menu = self.menuBar().addMenu("Help")
        about = QAction("About Nasheed Studio", self)
        about.triggered.connect(lambda: QMessageBox.information(
            self, "About",
            "Nasheed Studio is a local desktop tool for generating "
            "playlist-style Nasheed videos with FFmpeg."
        ))
        help_menu.addAction(about)

    # ------------------------------------------------------------------
    # Inspector Tab Builders
    # ------------------------------------------------------------------

    def _create_tab_scroll(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(10)
        scroll.setWidget(content)
        return scroll, layout

    def _build_tab_layout_assets(self, layout: QVBoxLayout) -> None:
        # Layout template
        sec_lbl = QLabel("LAYOUT TEMPLATE")
        sec_lbl.setObjectName("section")
        layout.addWidget(sec_lbl)

        self.template_combo = QComboBox()
        self.template_combo.addItems(["Cinematic", "Minimal", "Two-column"])
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        layout.addWidget(self.template_combo)

        layout.addSpacing(4)
        div1 = QFrame()
        div1.setObjectName("hairline_h")
        div1.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(div1)
        layout.addSpacing(4)

        # Background Image / Video
        bg_lbl = QLabel("BACKGROUND (IMAGE / MP4 VIDEO)")
        bg_lbl.setObjectName("section")
        layout.addWidget(bg_lbl)

        self.background_label = self._make_asset_label("No background selected")
        self.background_clear_btn = QPushButton()
        self.background_clear_btn.setIcon(get_svg_icon("clear", 12, "#95a399"))
        self.background_clear_btn.setToolTip("Clear background")
        self.background_clear_btn.clicked.connect(self.clear_background)

        self.background_btn = QPushButton("Choose background (image / MP4)…")
        self.background_btn.setIcon(get_svg_icon("image", 13, "#edf2ee"))
        self.background_btn.clicked.connect(self.choose_background)

        bg_row = QHBoxLayout()
        bg_row.setSpacing(6)
        bg_icon = QLabel()
        bg_icon.setPixmap(get_svg_pixmap("image", 14, "#95a399"))
        bg_row.addWidget(bg_icon)
        bg_row.addWidget(self.background_label, 1)
        bg_row.addWidget(self.background_clear_btn)

        self.background_info_label = QLabel("")
        self.background_info_label.setObjectName("subtle")
        self.background_info_label.setWordWrap(True)

        # Video-specific options container
        self.video_controls_group = QWidget()
        vc_layout = QVBoxLayout(self.video_controls_group)
        vc_layout.setContentsMargins(0, 4, 0, 4)
        vc_layout.setSpacing(4)

        fit_row = QHBoxLayout()
        fit_lbl = QLabel("Video Fit:")
        fit_lbl.setObjectName("muted")
        self.video_fit_combo = QComboBox()
        self.video_fit_combo.addItems(["Fill / Crop (Cover)", "Fit with Padding (Letterbox)", "Stretch"])
        self.video_fit_combo.currentTextChanged.connect(self._on_video_settings_changed)
        fit_row.addWidget(fit_lbl)
        fit_row.addWidget(self.video_fit_combo, 1)
        vc_layout.addLayout(fit_row)

        st_row = QHBoxLayout()
        st_lbl = QLabel("Start Time:")
        st_lbl.setObjectName("muted")
        self.video_start_spin = QDoubleSpinBox()
        self.video_start_spin.setRange(0.0, 3600.0)
        self.video_start_spin.setSingleStep(0.5)
        self.video_start_spin.setDecimals(1)
        self.video_start_spin.setSuffix(" s")
        self.video_start_spin.valueChanged.connect(self._on_video_settings_changed)
        st_row.addWidget(st_lbl)
        st_row.addWidget(self.video_start_spin, 1)
        vc_layout.addLayout(st_row)

        self.video_loop_check = QCheckBox("Loop video until audio ends")
        self.video_loop_check.setChecked(True)
        self.video_loop_check.toggled.connect(self._on_video_settings_changed)
        vc_layout.addWidget(self.video_loop_check)

        self.video_mute_check = QCheckBox("Mute video audio (nasheed only)")
        self.video_mute_check.setChecked(True)
        self.video_mute_check.toggled.connect(self._on_video_settings_changed)
        vc_layout.addWidget(self.video_mute_check)
        self.video_controls_group.setVisible(False)

        layout.addLayout(bg_row)
        layout.addWidget(self.background_info_label)
        layout.addWidget(self.background_btn)
        layout.addWidget(self.video_controls_group)

        layout.addSpacing(4)
        div2 = QFrame()
        div2.setObjectName("hairline_h")
        div2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(div2)
        layout.addSpacing(4)

        # Logo overlay
        logo_sec = QLabel("LOGO OVERLAY")
        logo_sec.setObjectName("section")
        layout.addWidget(logo_sec)

        self.logo_label = self._make_asset_label("No logo selected")
        self.logo_clear_btn = QPushButton()
        self.logo_clear_btn.setIcon(get_svg_icon("clear", 12, "#95a399"))
        self.logo_clear_btn.setToolTip("Clear logo image")
        self.logo_clear_btn.clicked.connect(self.clear_logo)

        self.logo_btn = QPushButton("Choose logo…")
        self.logo_btn.setIcon(get_svg_icon("image", 13, "#edf2ee"))
        self.logo_btn.clicked.connect(self.choose_logo)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(6)
        logo_icon = QLabel()
        logo_icon.setPixmap(get_svg_pixmap("image", 14, "#95a399"))
        logo_row.addWidget(logo_icon)
        logo_row.addWidget(self.logo_label, 1)
        logo_row.addWidget(self.logo_clear_btn)

        layout.addLayout(logo_row)
        layout.addWidget(self.logo_btn)

        logo_pos_row = QHBoxLayout()
        logo_pos_row.setSpacing(6)
        logo_pos_lbl = QLabel("Corner:")
        logo_pos_lbl.setObjectName("muted")
        self.logo_pos_combo = QComboBox()
        self.logo_pos_combo.addItems(["Bottom-Right", "Bottom-Left", "Top-Right", "Top-Left"])
        self.logo_pos_combo.currentTextChanged.connect(self._on_logo_pos_changed)
        logo_pos_row.addWidget(logo_pos_lbl)
        logo_pos_row.addWidget(self.logo_pos_combo, 1)
        layout.addLayout(logo_pos_row)

        self.logo_cleanup_check = QCheckBox("Remove solid white / checkerboard background")
        self.logo_cleanup_check.setChecked(True)
        self.logo_cleanup_check.toggled.connect(lambda _: self._on_layout_param_changed())
        layout.addWidget(self.logo_cleanup_check)

        layout.addSpacing(4)
        div3 = QFrame()
        div3.setObjectName("hairline_h")
        div3.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(div3)
        layout.addSpacing(4)

        # Playlist Layout & Background Panel
        pl_sec = QLabel("PLAYLIST LAYOUT & BACKGROUND")
        pl_sec.setObjectName("section")
        layout.addWidget(pl_sec)

        pl_pos_row = QHBoxLayout()
        pl_pos_row.setSpacing(6)
        pl_pos_lbl = QLabel("Position:")
        pl_pos_lbl.setObjectName("muted")
        self.playlist_pos_combo = QComboBox()
        self.playlist_pos_combo.addItems(["Left", "Center", "Right"])
        self.playlist_pos_combo.currentTextChanged.connect(lambda _: self._on_layout_param_changed())
        pl_pos_row.addWidget(pl_pos_lbl)
        pl_pos_row.addWidget(self.playlist_pos_combo, 1)

        cols_lbl = QLabel("Cols:")
        cols_lbl.setObjectName("muted")
        self.playlist_cols_spin = QSpinBox()
        self.playlist_cols_spin.setRange(1, 4)
        self.playlist_cols_spin.setValue(1)
        self.playlist_cols_spin.valueChanged.connect(lambda _: self._on_layout_param_changed())
        pl_pos_row.addWidget(cols_lbl)
        pl_pos_row.addWidget(self.playlist_cols_spin)

        col_sp_lbl = QLabel("Col gap:")
        col_sp_lbl.setObjectName("muted")
        self.col_spacing_spin = QSpinBox()
        self.col_spacing_spin.setRange(10, 250)
        self.col_spacing_spin.setValue(50)
        self.col_spacing_spin.setSuffix(" px")
        self.col_spacing_spin.setToolTip("Distance / gap between playlist columns")
        self.col_spacing_spin.valueChanged.connect(lambda _: self._on_layout_param_changed())
        pl_pos_row.addWidget(col_sp_lbl)
        pl_pos_row.addWidget(self.col_spacing_spin)
        layout.addLayout(pl_pos_row)

        bg_op_row = QHBoxLayout()
        bg_op_row.setSpacing(6)
        bg_op_lbl = QLabel("Panel Opacity:")
        bg_op_lbl.setObjectName("muted")
        self.playlist_bg_slider = QSlider(Qt.Orientation.Horizontal)
        self.playlist_bg_slider.setRange(0, 100)
        self.playlist_bg_slider.setValue(0)
        self.playlist_bg_val_lbl = QLabel("0% (Transparent)")
        self.playlist_bg_val_lbl.setObjectName("muted")
        self.playlist_bg_slider.valueChanged.connect(self._on_playlist_bg_changed)
        bg_op_row.addWidget(bg_op_lbl)
        bg_op_row.addWidget(self.playlist_bg_slider, 1)
        bg_op_row.addWidget(self.playlist_bg_val_lbl)
        layout.addLayout(bg_op_row)

        layout.addStretch(1)

    def _build_tab_text(self, layout: QVBoxLayout) -> None:
        # Title Typography
        title_sec = QLabel("COLLECTION TITLE TYPOGRAPHY")
        title_sec.setObjectName("section")
        layout.addWidget(title_sec)

        tf_box = QHBoxLayout()
        tf_box.setSpacing(6)
        self.title_font_combo = QComboBox()
        self.title_font_combo.currentTextChanged.connect(self._on_title_font_changed)
        self.title_font_browse_btn = QPushButton("Browse…")
        self.title_font_browse_btn.setToolTip("Select custom .ttf/.otf/.ttc font file from disk")
        self.title_font_browse_btn.clicked.connect(self.choose_custom_title_font)
        tf_box.addWidget(self.title_font_combo, 1)
        tf_box.addWidget(self.title_font_browse_btn)
        layout.addLayout(tf_box)

        t_row = QHBoxLayout()
        t_row.setSpacing(6)
        self.title_style_combo = QComboBox()
        self.title_style_combo.currentTextChanged.connect(self._on_title_style_changed)
        self.title_size_spin = QSpinBox()
        self.title_size_spin.setRange(20, 90)
        self.title_size_spin.setValue(46)
        self.title_size_spin.setSuffix(" px")
        self.title_size_spin.valueChanged.connect(self._on_title_size_changed)
        t_row.addWidget(self.title_style_combo, 2)
        t_row.addWidget(self.title_size_spin, 1)
        layout.addLayout(t_row)

        t_pos_row = QHBoxLayout()
        t_pos_row.setSpacing(6)
        self.title_show_check = QCheckBox("Show Title")
        self.title_show_check.setChecked(True)
        self.title_show_check.toggled.connect(self._on_title_visibility_changed)
        self.title_pos_combo = QComboBox()
        self.title_pos_combo.addItems(["Top-Center", "Above Playlist", "Top-Left", "Hidden"])
        self.title_pos_combo.currentTextChanged.connect(self._on_title_visibility_changed)
        t_pos_row.addWidget(self.title_show_check)
        t_pos_row.addWidget(self.title_pos_combo, 1)
        layout.addLayout(t_pos_row)

        t_sp_row = QHBoxLayout()
        t_sp_row.setSpacing(6)
        self.title_spacing_lbl = QLabel("Title-Playlist Spacing:")
        self.title_spacing_lbl.setObjectName("muted")
        self.title_spacing_spin = QSpinBox()
        self.title_spacing_spin.setRange(0, 250)
        self.title_spacing_spin.setValue(40)
        self.title_spacing_spin.setSuffix(" px")
        self.title_spacing_spin.setToolTip("Vertical spacing between title rendered bounds and playlist (0 - 250 px)")
        self.title_spacing_spin.valueChanged.connect(self._on_title_spacing_changed)
        t_sp_row.addWidget(self.title_spacing_lbl, 1)
        t_sp_row.addWidget(self.title_spacing_spin, 1)
        layout.addLayout(t_sp_row)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        top_lbl = QLabel("Title Opacity:")
        top_lbl.setObjectName("muted")
        self.title_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.title_opacity_slider.setRange(10, 100)
        self.title_opacity_slider.setValue(100)
        self.title_opacity_slider.setToolTip("Adjust title text transparency (10% - 100%)")
        self.title_opacity_val = QLabel("100%")
        self.title_opacity_val.setMinimumWidth(40)
        self.title_opacity_val.setObjectName("muted")
        self.title_opacity_slider.valueChanged.connect(self._on_title_opacity_changed)
        top_row.addWidget(top_lbl)
        top_row.addWidget(self.title_opacity_slider, 1)
        top_row.addWidget(self.title_opacity_val)
        layout.addLayout(top_row)

        t_col_row = QHBoxLayout()
        t_col_row.setSpacing(6)
        t_col_lbl = QLabel("Title Color:")
        t_col_lbl.setObjectName("muted")
        self.title_color_btn = QPushButton("Choose color…")
        self.title_color_btn.clicked.connect(self.choose_title_color)
        self.title_color_reset_btn = QPushButton("Reset")
        self.title_color_reset_btn.setToolTip("Reset title text color to default white (#FFFFFF)")
        self.title_color_reset_btn.clicked.connect(self.reset_title_color)
        t_col_row.addWidget(t_col_lbl)
        t_col_row.addWidget(self.title_color_btn, 1)
        t_col_row.addWidget(self.title_color_reset_btn)
        layout.addLayout(t_col_row)

        layout.addSpacing(4)
        div = QFrame()
        div.setObjectName("hairline_h")
        div.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(div)
        layout.addSpacing(4)

        # Track Typography
        track_sec = QLabel("PLAYLIST TRACKS TYPOGRAPHY")
        track_sec.setObjectName("section")
        layout.addWidget(track_sec)

        trf_box = QHBoxLayout()
        trf_box.setSpacing(6)
        self.track_font_combo = QComboBox()
        self.track_font_combo.currentTextChanged.connect(self._on_track_font_changed)
        self.track_font_browse_btn = QPushButton("Browse…")
        self.track_font_browse_btn.setToolTip("Select custom .ttf/.otf/.ttc font file from disk")
        self.track_font_browse_btn.clicked.connect(self.choose_custom_track_font)
        trf_box.addWidget(self.track_font_combo, 1)
        trf_box.addWidget(self.track_font_browse_btn)
        layout.addLayout(trf_box)

        tr_row = QHBoxLayout()
        tr_row.setSpacing(6)
        self.track_style_combo = QComboBox()
        self.track_style_combo.currentTextChanged.connect(self._on_track_style_changed)
        self.track_size_spin = QSpinBox()
        self.track_size_spin.setRange(12, 48)
        self.track_size_spin.setValue(22)
        self.track_size_spin.setSuffix(" px")
        self.track_size_spin.valueChanged.connect(self._on_track_size_changed)
        tr_row.addWidget(self.track_style_combo, 2)
        tr_row.addWidget(self.track_size_spin, 1)
        layout.addLayout(tr_row)

        sp_row = QHBoxLayout()
        sp_row.setSpacing(6)
        sp_lbl = QLabel("Row spacing:")
        sp_lbl.setObjectName("muted")
        self.track_spacing_spin = QDoubleSpinBox()
        self.track_spacing_spin.setRange(1.2, 2.8)
        self.track_spacing_spin.setSingleStep(0.1)
        self.track_spacing_spin.setValue(1.85)
        self.track_spacing_spin.setSuffix("x")
        self.track_spacing_spin.valueChanged.connect(lambda _: self._on_layout_param_changed())
        sp_row.addWidget(sp_lbl)
        sp_row.addWidget(self.track_spacing_spin, 1)

        char_lim_lbl = QLabel("Max title length:")
        char_lim_lbl.setObjectName("muted")
        self.track_max_chars_spin = QSpinBox()
        self.track_max_chars_spin.setRange(0, 120)
        self.track_max_chars_spin.setValue(0)
        self.track_max_chars_spin.setSpecialValueText("Auto")
        self.track_max_chars_spin.setSuffix(" chars")
        self.track_max_chars_spin.setToolTip("Truncate titles after this many characters (0 = Auto fit to column)")
        self.track_max_chars_spin.valueChanged.connect(lambda _: self._on_layout_param_changed())
        sp_row.addWidget(char_lim_lbl)
        sp_row.addWidget(self.track_max_chars_spin, 1)
        layout.addLayout(sp_row)

        trop_row = QHBoxLayout()
        trop_row.setSpacing(6)
        trop_lbl = QLabel("Track Opacity:")
        trop_lbl.setObjectName("muted")
        self.track_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.track_opacity_slider.setRange(10, 100)
        self.track_opacity_slider.setValue(100)
        self.track_opacity_slider.setToolTip("Adjust playlist tracks transparency (10% - 100%)")
        self.track_opacity_val = QLabel("100%")
        self.track_opacity_val.setMinimumWidth(40)
        self.track_opacity_val.setObjectName("muted")
        self.track_opacity_slider.valueChanged.connect(self._on_track_opacity_changed)
        trop_row.addWidget(trop_lbl)
        trop_row.addWidget(self.track_opacity_slider, 1)
        trop_row.addWidget(self.track_opacity_val)
        layout.addLayout(trop_row)

        tr_col_row = QHBoxLayout()
        tr_col_row.setSpacing(6)
        tr_col_lbl = QLabel("Track Text Color:")
        tr_col_lbl.setObjectName("muted")
        self.track_color_btn = QPushButton("Choose color…")
        self.track_color_btn.clicked.connect(self.choose_track_color)
        self.track_color_reset_btn = QPushButton("Reset")
        self.track_color_reset_btn.setToolTip("Reset track text color to default white (#FFFFFF)")
        self.track_color_reset_btn.clicked.connect(self.reset_track_color)
        tr_col_row.addWidget(tr_col_lbl)
        tr_col_row.addWidget(self.track_color_btn, 1)
        tr_col_row.addWidget(self.track_color_reset_btn)
        layout.addLayout(tr_col_row)

        soft_row = QHBoxLayout()
        soft_row.setSpacing(6)
        soft_lbl = QLabel("Text Softening:")
        soft_lbl.setObjectName("muted")
        self.text_softening_spin = QDoubleSpinBox()
        self.text_softening_spin.setRange(0.0, 3.0)
        self.text_softening_spin.setSingleStep(0.1)
        self.text_softening_spin.setValue(0.0)
        self.text_softening_spin.setSpecialValueText("0.0 px (Crisp)")
        self.text_softening_spin.setSuffix(" px")
        self.text_softening_spin.setToolTip("Subtle text-edge softening and background blending (0.0 px = crisp)")
        self.text_softening_spin.valueChanged.connect(lambda _: self._on_layout_param_changed())
        soft_row.addWidget(soft_lbl, 1)
        soft_row.addWidget(self.text_softening_spin, 1)
        layout.addLayout(soft_row)

        layout.addSpacing(4)
        div2 = QFrame()
        div2.setObjectName("hairline_h")
        div2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(div2)
        layout.addSpacing(4)

        self.refresh_fonts_btn = QPushButton("Refresh system fonts")
        self.refresh_fonts_btn.setObjectName("quiet")
        self.refresh_fonts_btn.setIcon(get_svg_icon("refresh", 13, "#95a399"))
        self.refresh_fonts_btn.clicked.connect(lambda: self._refresh_system_fonts(initial=False))
        layout.addWidget(self.refresh_fonts_btn)

        self._refresh_system_fonts(initial=True)
        layout.addStretch(1)

    def _build_tab_indicator_watermark(self, layout: QVBoxLayout) -> None:
        # Active track indicator
        ind_sec = QLabel("ACTIVE TRACK INDICATOR")
        ind_sec.setObjectName("section")
        layout.addWidget(ind_sec)

        self.indicator_combo = QComboBox()
        self.indicator_combo.addItems([
            "Both (Cursor & Highlight)",
            "Cursor only",
            "Highlight only",
            "Neither (Clean)"
        ])
        self.indicator_combo.currentTextChanged.connect(self._on_indicator_changed)
        layout.addWidget(self.indicator_combo)

        self.cursor_label = self._make_asset_label("Default arrow cursor")
        cur_row = QHBoxLayout()
        cur_row.setSpacing(6)
        cur_icon = QLabel()
        cur_icon.setPixmap(get_svg_pixmap("tab_indicator", 14, "#95a399"))
        self.cursor_btn = QPushButton("Choose cursor…")
        self.cursor_btn.clicked.connect(self.choose_cursor)
        self.cursor_reset_btn = QPushButton("Reset")
        self.cursor_reset_btn.clicked.connect(self.reset_cursor)
        cur_row.addWidget(cur_icon)
        cur_row.addWidget(self.cursor_label, 1)
        cur_row.addWidget(self.cursor_reset_btn)
        layout.addLayout(cur_row)
        layout.addWidget(self.cursor_btn)

        sz_row = QHBoxLayout()
        sz_lbl = QLabel("Cursor size:")
        sz_lbl.setObjectName("muted")
        self.cursor_size_spin = QSpinBox()
        self.cursor_size_spin.setRange(16, 96)
        self.cursor_size_spin.setValue(32)
        self.cursor_size_spin.setSuffix(" px")
        self.cursor_size_spin.valueChanged.connect(self._on_cursor_size_changed)
        sz_row.addWidget(sz_lbl)
        sz_row.addWidget(self.cursor_size_spin, 1)
        layout.addLayout(sz_row)

        cur_y_row = QHBoxLayout()
        cur_y_row.setSpacing(6)
        cur_y_lbl = QLabel("Cursor Y-Offset:")
        cur_y_lbl.setObjectName("muted")
        self.cursor_y_offset_spin = QSpinBox()
        self.cursor_y_offset_spin.setRange(-50, 50)
        self.cursor_y_offset_spin.setValue(0)
        self.cursor_y_offset_spin.setSuffix(" px")
        self.cursor_y_offset_spin.setToolTip("Fine-tune vertical positioning of the cursor relative to track text (-50 to +50 px)")
        self.cursor_y_offset_spin.valueChanged.connect(lambda _: self._on_layout_param_changed())
        cur_y_row.addWidget(cur_y_lbl)
        cur_y_row.addWidget(self.cursor_y_offset_spin, 1)
        layout.addLayout(cur_y_row)

        hl_style_row = QHBoxLayout()
        hl_style_row.setSpacing(6)
        hl_style_lbl = QLabel("Highlight Style:")
        hl_style_lbl.setObjectName("muted")
        self.highlight_style_combo = QComboBox()
        self.highlight_style_combo.addItems(["Pill", "Accent Bar", "Outline", "Underline"])
        self.highlight_style_combo.currentTextChanged.connect(lambda _: self._on_layout_param_changed())
        hl_style_row.addWidget(hl_style_lbl)
        hl_style_row.addWidget(self.highlight_style_combo, 1)
        layout.addLayout(hl_style_row)

        hl_col_row = QHBoxLayout()
        hl_col_row.setSpacing(6)
        hl_col_lbl = QLabel("Highlight Color:")
        hl_col_lbl.setObjectName("muted")
        self.highlight_color_btn = QPushButton("Choose color…")
        self.highlight_color_btn.clicked.connect(self.choose_highlight_color)
        self.highlight_color_reset_btn = QPushButton("Reset")
        self.highlight_color_reset_btn.setToolTip("Reset highlight color to default amber gold (#F8DC8B)")
        self.highlight_color_reset_btn.clicked.connect(self.reset_highlight_color)
        hl_col_row.addWidget(hl_col_lbl)
        hl_col_row.addWidget(self.highlight_color_btn, 1)
        hl_col_row.addWidget(self.highlight_color_reset_btn)
        layout.addLayout(hl_col_row)

        hl_op_row = QHBoxLayout()
        hl_op_row.setSpacing(6)
        hl_op_lbl = QLabel("Highlight Tint:")
        hl_op_lbl.setObjectName("muted")
        self.highlight_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.highlight_opacity_slider.setRange(5, 100)
        self.highlight_opacity_slider.setValue(25)
        self.highlight_opacity_val = QLabel("25%")
        self.highlight_opacity_val.setObjectName("muted")
        self.highlight_opacity_slider.valueChanged.connect(self._on_highlight_opacity_changed)
        hl_op_row.addWidget(hl_op_lbl)
        hl_op_row.addWidget(self.highlight_opacity_slider, 1)
        hl_op_row.addWidget(self.highlight_opacity_val)
        layout.addLayout(hl_op_row)

        hl_thick_row = QHBoxLayout()
        hl_thick_row.setSpacing(6)
        hl_thick_lbl = QLabel("Outline Width:")
        hl_thick_lbl.setObjectName("muted")
        self.highlight_outline_spin = QSpinBox()
        self.highlight_outline_spin.setRange(1, 16)
        self.highlight_outline_spin.setValue(2)
        self.highlight_outline_spin.setSuffix(" px")
        self.highlight_outline_spin.setToolTip("Outline thickness for active track rectangle or pill")
        self.highlight_outline_spin.valueChanged.connect(lambda _: self._on_layout_param_changed())
        hl_thick_row.addWidget(hl_thick_lbl)
        hl_thick_row.addWidget(self.highlight_outline_spin, 1)
        layout.addLayout(hl_thick_row)

        hl_corner_row = QHBoxLayout()
        hl_corner_row.setSpacing(6)
        hl_corner_lbl = QLabel("Corner Style:")
        hl_corner_lbl.setObjectName("muted")
        self.highlight_corner_combo = QComboBox()
        self.highlight_corner_combo.addItems(["Rounded", "Square (Sharp)"])
        self.highlight_corner_combo.setToolTip("Corner curvature of the active track outline or pill")
        self.highlight_corner_combo.currentTextChanged.connect(lambda _: self._on_layout_param_changed())
        hl_corner_row.addWidget(hl_corner_lbl)
        hl_corner_row.addWidget(self.highlight_corner_combo, 1)
        layout.addLayout(hl_corner_row)

        hl_target_row = QHBoxLayout()
        hl_target_row.setSpacing(6)
        hl_target_lbl = QLabel("Highlight Target:")
        hl_target_lbl.setObjectName("muted")
        self.highlight_target_combo = QComboBox()
        self.highlight_target_combo.addItems(["Full Row", "Surround Text"])
        self.highlight_target_combo.setToolTip("Surround entire playlist row width or fit tightly around track text")
        self.highlight_target_combo.currentTextChanged.connect(lambda _: self._on_layout_param_changed())
        hl_target_row.addWidget(hl_target_lbl)
        hl_target_row.addWidget(self.highlight_target_combo, 1)
        layout.addLayout(hl_target_row)

        hl_y_row = QHBoxLayout()
        hl_y_row.setSpacing(6)
        hl_y_lbl = QLabel("Highlight Y-Offset:")
        hl_y_lbl.setObjectName("muted")
        self.highlight_y_offset_spin = QSpinBox()
        self.highlight_y_offset_spin.setRange(-50, 50)
        self.highlight_y_offset_spin.setValue(0)
        self.highlight_y_offset_spin.setSuffix(" px")
        self.highlight_y_offset_spin.setToolTip("Fine-tune vertical positioning of highlight box/outline relative to track text (-50 to +50 px)")
        self.highlight_y_offset_spin.valueChanged.connect(lambda _: self._on_layout_param_changed())
        hl_y_row.addWidget(hl_y_lbl)
        hl_y_row.addWidget(self.highlight_y_offset_spin, 1)
        layout.addLayout(hl_y_row)

        layout.addSpacing(4)
        div = QFrame()
        div.setObjectName("hairline_h")
        div.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(div)
        layout.addSpacing(4)

        # Website Watermark
        web_sec = QLabel("WEBSITE WATERMARK")
        web_sec.setObjectName("section")
        layout.addWidget(web_sec)

        self.website_show_check = QCheckBox("Show Website Watermark")
        self.website_show_check.setChecked(True)
        self.website_show_check.toggled.connect(self._on_website_show_toggled)
        layout.addWidget(self.website_show_check)

        self.website_edit = QLineEdit()
        self.website_edit.setPlaceholderText("Optional: e.g. www.nasheedstudio.com")
        self.website_edit.textChanged.connect(self._on_website_text_changed)
        layout.addWidget(self.website_edit)

        pos_row = QHBoxLayout()
        pos_row.setSpacing(6)
        self.website_pos_combo = QComboBox()
        self.website_pos_combo.addItems(["Top-Right", "Top-Left", "Bottom-Left", "Bottom-Right", "Bottom-Center", "Top-Center"])
        self.website_pos_combo.currentTextChanged.connect(self._on_website_pos_changed)
        self.website_size_spin = QSpinBox()
        self.website_size_spin.setRange(10, 48)
        self.website_size_spin.setValue(18)
        self.website_size_spin.setSuffix(" px")
        self.website_size_spin.valueChanged.connect(self._on_website_size_changed)
        pos_row.addWidget(self.website_pos_combo, 2)
        pos_row.addWidget(self.website_size_spin, 1)
        layout.addLayout(pos_row)

        web_op_row = QHBoxLayout()
        web_op_row.setSpacing(6)
        web_op_lbl = QLabel("URL Opacity:")
        web_op_lbl.setObjectName("muted")
        self.website_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.website_opacity_slider.setRange(0, 100)
        self.website_opacity_slider.setValue(100)
        self.website_opacity_val = QLabel("100%")
        self.website_opacity_val.setObjectName("muted")
        self.website_opacity_val.setFixedWidth(40)
        self.website_opacity_slider.valueChanged.connect(self._on_website_opacity_changed)
        web_op_row.addWidget(web_op_lbl)
        web_op_row.addWidget(self.website_opacity_slider, 1)
        web_op_row.addWidget(self.website_opacity_val)
        layout.addLayout(web_op_row)

        self.overlap_warning = QLabel("Logo and website share the same corner. Position will adjust automatically.")
        self.overlap_warning.setObjectName("warning")
        self.overlap_warning.setWordWrap(True)
        self.overlap_warning.setVisible(False)
        layout.addWidget(self.overlap_warning)

        layout.addStretch(1)

    def _build_tab_intro_sound(self, layout: QVBoxLayout) -> None:
        # Intro Presentation
        intro_sec = QLabel("INTRO PRESENTATION")
        intro_sec.setObjectName("section")
        layout.addWidget(intro_sec)

        self.intro_check = QCheckBox("Enable intro sequence")
        self.intro_check.toggled.connect(self._on_intro_toggled)
        layout.addWidget(self.intro_check)

        dur_row = QHBoxLayout()
        dur_lbl = QLabel("Duration:")
        dur_lbl.setObjectName("muted")
        self.intro_dur_spin = QDoubleSpinBox()
        self.intro_dur_spin.setRange(1.0, 10.0)
        self.intro_dur_spin.setValue(3.0)
        self.intro_dur_spin.setSingleStep(0.5)
        self.intro_dur_spin.setSuffix(" s")
        self.intro_dur_spin.valueChanged.connect(self._on_intro_dur_changed)
        dur_row.addWidget(dur_lbl)
        dur_row.addWidget(self.intro_dur_spin, 1)
        layout.addLayout(dur_row)

        anim_row = QHBoxLayout()
        anim_lbl = QLabel("Animation:")
        anim_lbl.setObjectName("muted")
        self.intro_anim_combo = QComboBox()
        self.intro_anim_combo.addItems(["Fade in / out", "Zoom in", "Slide"])
        self.intro_anim_combo.currentTextChanged.connect(self._on_intro_anim_changed)
        anim_row.addWidget(anim_lbl)
        anim_row.addWidget(self.intro_anim_combo, 1)
        layout.addLayout(anim_row)

        layout.addSpacing(4)
        div = QFrame()
        div.setObjectName("hairline_h")
        div.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(div)
        layout.addSpacing(4)

        # Transition Sound Effects
        sfx_sec = QLabel("TRANSITION SOUND EFFECT")
        sfx_sec.setObjectName("section")
        layout.addWidget(sfx_sec)

        self.sfx_check = QCheckBox("Enable track transition SFX")
        self.sfx_check.toggled.connect(self._on_sfx_toggled)
        layout.addWidget(self.sfx_check)

        self.sfx_label = self._make_asset_label("No sound effect selected")
        sfx_row = QHBoxLayout()
        sfx_row.setSpacing(6)
        sfx_icon = QLabel()
        sfx_icon.setPixmap(get_svg_pixmap("tab_intro", 14, "#95a399"))
        self.sfx_reset_btn = QPushButton("Reset")
        self.sfx_reset_btn.clicked.connect(self.reset_sfx)
        self.sfx_btn = QPushButton("Choose SFX…")
        self.sfx_btn.clicked.connect(self.choose_sfx)

        sfx_row.addWidget(sfx_icon)
        sfx_row.addWidget(self.sfx_label, 1)
        sfx_row.addWidget(self.sfx_reset_btn)
        layout.addLayout(sfx_row)
        layout.addWidget(self.sfx_btn)

        vol_row = QHBoxLayout()
        vol_row.setSpacing(6)
        vol_lbl = QLabel("Volume:")
        vol_lbl.setObjectName("muted")
        self.sfx_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.sfx_vol_slider.setRange(0, 100)
        self.sfx_vol_slider.setValue(70)
        self.sfx_vol_slider.valueChanged.connect(self._on_sfx_vol_changed)
        self.sfx_vol_label = QLabel("70%")
        self.sfx_vol_label.setMinimumWidth(36)
        vol_row.addWidget(vol_lbl)
        vol_row.addWidget(self.sfx_vol_slider, 1)
        vol_row.addWidget(self.sfx_vol_label)
        layout.addLayout(vol_row)

        layout.addStretch(1)

    # ------------------------------------------------------------------
    # Inspector Toggle & Workspace Reveal
    # ------------------------------------------------------------------

    def toggle_inspector(self) -> None:
        """Collapse or restore the inspector pane in the main splitter."""
        is_visible = self.inspector_panel.isVisible()
        if is_visible:
            sizes = self.splitter.sizes()
            if len(sizes) >= 3 and sizes[2] > 0:
                self._last_inspector_width = max(280, sizes[2])
            self.inspector_panel.hide()
            self.inspector_toggle_btn.setChecked(False)
        else:
            self.inspector_panel.show()
            self.inspector_toggle_btn.setChecked(True)
            w = max(280, getattr(self, "_last_inspector_width", 320))
            sizes = self.splitter.sizes()
            total = sum(sizes)
            left = sizes[0] if sizes else 310
            right = w
            center = max(400, total - left - right)
            self.splitter.setSizes([left, center, right])

    def open_workspace(self) -> None:
        """Reveal workspace root directory in Windows Explorer."""
        root = get_workspace_root()
        try:
            if sys.platform == "win32":
                os.startfile(str(root))
            else:
                subprocess.run(["xdg-open", str(root)])
        except Exception as exc:
            QMessageBox.warning(self, "Open Workspace", f"Could not open directory:\n\n{exc}")

    def reset_workspace(self) -> None:
        """Reset workspace location to the default durable home directory."""
        new_root = reset_workspace_root()
        self.status_label.setText(f"Workspace reset to default: {new_root}")
        QMessageBox.information(
            self, "Workspace Reset",
            f"Workspace location has been reset to the default durable directory:\n\n{new_root}\n\n"
            "All previous user files and projects remain intact and were not deleted."
        )

    # ------------------------------------------------------------------
    # Asset Label & File Field Helpers (Bug A)
    # ------------------------------------------------------------------

    @staticmethod
    def _make_asset_label(text: str) -> QLabel:
        """A label that truncates long filenames with an ellipsis (Bug A)."""
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

    def clear_background(self) -> None:
        """Clear background asset and refresh preview."""
        self._stop_video_preview()
        if self.background_path:
            self.background_path = ""
            self.background_type = "image"
            self._set_asset_label(self.background_label, "")
            self.background_label.setText("No background selected")
            if hasattr(self, "background_info_label"):
                self.background_info_label.setText("")
            if hasattr(self, "video_controls_group"):
                self.video_controls_group.setVisible(False)
            if hasattr(self, "play_preview_btn"):
                self.play_preview_btn.setVisible(False)
            self._mark_dirty()
            self._refresh_preview()

    def clear_logo(self) -> None:
        """Clear logo asset and refresh preview."""
        if self.logo_path:
            self.logo_path = ""
            self._set_asset_label(self.logo_label, "")
            self.logo_label.setText("No logo selected")
            self._mark_dirty()
            self._check_logo_website_overlap()
            self._refresh_preview()

    # ------------------------------------------------------------------
    # Active Track Indicator & Custom Cursor
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

    # ------------------------------------------------------------------
    # Project Snapshot Builder
    # ------------------------------------------------------------------

    def _project(self) -> dict:
        if self.collection_title.text().strip() != self._committed_title:
            self._apply_title()
        return {
            "version": 1,
            "collection_title": self._committed_title or "Nasheed Collection",
            "background": self.background_path,
            "background_type": getattr(self, "background_type", "image"),
            "video_fit_mode": self.video_fit_combo.currentText() if hasattr(self, "video_fit_combo") else getattr(self, "video_fit_mode", "Fill / Crop (Cover)"),
            "video_start_time": self.video_start_spin.value() if hasattr(self, "video_start_spin") else getattr(self, "video_start_time", 0.0),
            "video_loop": self.video_loop_check.isChecked() if hasattr(self, "video_loop_check") else getattr(self, "video_loop", True),
            "video_mute_audio": self.video_mute_check.isChecked() if hasattr(self, "video_mute_check") else getattr(self, "video_mute_audio", True),
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
            "title_playlist_spacing": self.title_spacing_spin.value() if hasattr(self, "title_spacing_spin") else 40,
            "title_opacity": round(self.title_opacity_slider.value() / 100.0, 2) if hasattr(self, "title_opacity_slider") else 1.0,
            "custom_title_font_path": getattr(self, "custom_title_font_path", ""),
            "track_font_family": self.track_font_combo.currentText() if hasattr(self, "track_font_combo") else "Segoe UI",
            "track_font_style": self.track_style_combo.currentText() if hasattr(self, "track_style_combo") else "Bold",
            "track_font_size": self.track_size_spin.value() if hasattr(self, "track_size_spin") else 22,
            "track_opacity": round(self.track_opacity_slider.value() / 100.0, 2) if hasattr(self, "track_opacity_slider") else 1.0,
            "text_softening": round(self.text_softening_spin.value(), 1) if hasattr(self, "text_softening_spin") else 0.0,
            "title_softening": round(self.text_softening_spin.value(), 1) if hasattr(self, "text_softening_spin") else 0.0,
            "track_softening": round(self.text_softening_spin.value(), 1) if hasattr(self, "text_softening_spin") else 0.0,
            "custom_track_font_path": getattr(self, "custom_track_font_path", ""),
            "website_text": self.website_edit.text().strip() if hasattr(self, "website_edit") else "",
            "website_position": self.website_pos_combo.currentText() if hasattr(self, "website_pos_combo") else "Top-Right",
            "website_font_size": self.website_size_spin.value() if hasattr(self, "website_size_spin") else 18,
            "website_show": self.website_show_check.isChecked() if hasattr(self, "website_show_check") else True,
            "website_opacity": round(self.website_opacity_slider.value() / 100.0, 2) if hasattr(self, "website_opacity_slider") else 1.0,
            "website_font_family": getattr(self, "website_font_family", None) or (self.track_font_combo.currentText() if hasattr(self, "track_font_combo") else "Segoe UI"),
            "website_font_style": getattr(self, "website_font_style", "Regular"),
            "website_color": getattr(self, "website_color", None),
            "transition_sfx_enabled": self.sfx_check.isChecked() if hasattr(self, "sfx_check") else False,
            "transition_sfx_path": self.sfx_path,
            "transition_sfx_volume": round(self.sfx_vol_slider.value() / 100.0, 2) if hasattr(self, "sfx_vol_slider") else 0.7,
            "intro_enabled": self.intro_check.isChecked() if hasattr(self, "intro_check") else False,
            "intro_duration": self.intro_dur_spin.value() if hasattr(self, "intro_dur_spin") else 3.0,
            "intro_animation": self.intro_anim_combo.currentText() if hasattr(self, "intro_anim_combo") else "Fade in / out",
            "resource_profile": self.resource_profile_combo.currentText() if hasattr(self, "resource_profile_combo") else "Balanced",
            "playlist_position": self.playlist_pos_combo.currentText() if hasattr(self, "playlist_pos_combo") else "Left",
            "playlist_columns": self.playlist_cols_spin.value() if hasattr(self, "playlist_cols_spin") else 1,
            "playlist_row_spacing": round(self.track_spacing_spin.value(), 2) if hasattr(self, "track_spacing_spin") else 1.85,
            "playlist_col_spacing": self.col_spacing_spin.value() if hasattr(self, "col_spacing_spin") else 50,
            "track_max_chars": self.track_max_chars_spin.value() if hasattr(self, "track_max_chars_spin") else 0,
            "playlist_bg_opacity": round(self.playlist_bg_slider.value() / 100.0, 2) if hasattr(self, "playlist_bg_slider") else 0.0,
            "logo_cleanup_mode": "auto" if (hasattr(self, "logo_cleanup_check") and self.logo_cleanup_check.isChecked()) else "none",
            "title_position": self.title_pos_combo.currentText() if hasattr(self, "title_pos_combo") else "Top-Center",
            "title_show": self.title_show_check.isChecked() if hasattr(self, "title_show_check") else True,
            "title_color": getattr(self, "title_color", (255, 255, 255)),
            "track_color": getattr(self, "track_color", (255, 255, 255)),
            "highlight_style": self.highlight_style_combo.currentText() if hasattr(self, "highlight_style_combo") else "Pill",
            "highlight_color": getattr(self, "highlight_color", (248, 220, 139)),
            "highlight_bg_opacity": round(self.highlight_opacity_slider.value() / 100.0, 2) if hasattr(self, "highlight_opacity_slider") else 0.25,
            "highlight_outline_width": self.highlight_outline_spin.value() if hasattr(self, "highlight_outline_spin") else 2,
            "highlight_corner_radius": (0 if (hasattr(self, "highlight_corner_combo") and self.highlight_corner_combo.currentText() == "Square (Sharp)") else None),
            "highlight_target": ("text" if (hasattr(self, "highlight_target_combo") and self.highlight_target_combo.currentText() == "Surround Text") else "row"),
            "highlight_opacity": 1.0,
            "cursor_y_offset": self.cursor_y_offset_spin.value() if hasattr(self, "cursor_y_offset_spin") else 0,
            "highlight_y_offset": self.highlight_y_offset_spin.value() if hasattr(self, "highlight_y_offset_spin") else 0,
            "output_path": self.output_edit.text().strip(),
        }

    # ------------------------------------------------------------------
    # Asset Pickers
    # ------------------------------------------------------------------

    def _apply_background_file(self, path: str) -> bool:
        p = Path(path)
        if not p.is_file():
            QMessageBox.warning(self, "File Not Found", f"The background file was not found:\n{path}")
            return False

        if is_video_file(path):
            try:
                info = get_video_info(path)
                if not info.get("has_video"):
                    QMessageBox.warning(self, "Invalid Video", f"The selected file contains no playable video stream:\n{path}")
                    return False
                self.background_path = str(p.resolve())
                self.background_type = "video"
                self._set_asset_label(self.background_label, path)
                dur_s = info.get("duration", 0.0)
                fps = info.get("fps", 30.0)
                w, h = info.get("width", 0), info.get("height", 0)
                codec = info.get("codec", "").upper()
                audio_str = "with audio" if info.get("has_audio") else "muted/no audio"
                if hasattr(self, "background_info_label"):
                    self.background_info_label.setText(f"{w}×{h} · {fps} fps · {dur_s:.1f}s · {codec} ({audio_str})")
                if hasattr(self, "video_start_spin"):
                    self.video_start_spin.blockSignals(True)
                    self.video_start_spin.setMaximum(max(0.0, dur_s - 0.5))
                    self.video_start_spin.blockSignals(False)
                if hasattr(self, "video_controls_group"):
                    self.video_controls_group.setVisible(True)
                if hasattr(self, "play_preview_btn"):
                    self.play_preview_btn.setVisible(True)
                self._stop_video_preview()
                self._mark_dirty()
                self._refresh_preview()
                return True
            except Exception as exc:
                QMessageBox.warning(self, "Video Read Error", f"Could not read video file:\n{exc}")
                return False
        else:
            try:
                with Image.open(path) as img:
                    w, h = img.size
                    fmt = img.format or "IMAGE"
                self.background_path = str(p.resolve())
                self.background_type = "image"
                self._set_asset_label(self.background_label, path)
                if hasattr(self, "background_info_label"):
                    self.background_info_label.setText(f"{w}×{h} · {fmt}")
                if hasattr(self, "video_controls_group"):
                    self.video_controls_group.setVisible(False)
                if hasattr(self, "play_preview_btn"):
                    self.play_preview_btn.setVisible(False)
                self._stop_video_preview()
                self._mark_dirty()
                self._refresh_preview()
                return True
            except Exception as exc:
                QMessageBox.warning(self, "Image Read Error", f"Could not read image file:\n{exc}")
                return False

    def choose_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose background (image or MP4 video)", "",
            "All Supported Media (*.mp4 *.mov *.mkv *.webm *.png *.jpg *.jpeg *.webp *.bmp);;Video Files (*.mp4 *.mov *.mkv *.webm);;Image Files (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self._apply_background_file(path)

    def _on_video_settings_changed(self) -> None:
        if getattr(self, "_loading_project", False):
            return
        self._mark_dirty()
        self._schedule_preview(200)

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
    # Track Management & Audio Import
    # ------------------------------------------------------------------

    def add_tracks(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add audio tracks", "",
            "Audio files (*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus *.wma);;All files (*.*)"
        )
        if paths:
            self.import_audio_paths(paths)

    def import_audio_paths(self, paths: list[str]) -> None:
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
            self._schedule_preview(200)

    def _refresh_tracks(self) -> None:
        self.track_list.blockSignals(True)
        self.track_list.clear()
        for i, track in enumerate(self.tracks):
            track.setdefault("_id", uuid.uuid4().hex)
            mins, secs = divmod(int(track.get("duration", 0)), 60)
            item = QListWidgetItem(
                f"{i+1:02d}   {track['title']}\n       {mins:02d}:{secs:02d}  ·  {Path(track['path']).name}"
            )
            item.setData(Qt.ItemDataRole.UserRole, track["path"])
            item.setData(Qt.ItemDataRole.UserRole + 1, track["_id"])
            item.setToolTip(track["path"])
            self.track_list.addItem(item)
        self.track_list.blockSignals(False)
        self._refresh_tracks_labels()

    def _refresh_tracks_labels(self) -> None:
        total = sum(float(t.get("duration", 0)) for t in self.tracks)
        m, s = divmod(int(total), 60)
        summary_txt = (
            f"{len(self.tracks)} tracks · Estimated duration {m:02d}:{s:02d}"
            if self.tracks else "0 tracks · Add audio files to begin"
        )
        if hasattr(self, "render_summary"):
            self.render_summary.setText(summary_txt)
        if hasattr(self, "playlist_summary_label"):
            self.playlist_summary_label.setText(
                f"{len(self.tracks)} tracks · {m:02d}:{s:02d}" if self.tracks else "0 tracks · Add audio files"
            )
        if hasattr(self, "scrubber_total_label"):
            self.scrubber_total_label.setText(f"{m:02d}:{s:02d}")

    def _on_rows_moved(self, *args) -> None:
        by_id = {t.get("_id"): t for t in self.tracks if "_id" in t}
        reordered = []
        for i in range(self.track_list.count()):
            item = self.track_list.item(i)
            tid = item.data(Qt.ItemDataRole.UserRole + 1)
            if tid and tid in by_id:
                reordered.append(by_id[tid])
            else:
                path = item.data(Qt.ItemDataRole.UserRole)
                for t in self.tracks:
                    if t.get("path") == path and t not in reordered:
                        reordered.append(t)
                        break
        if len(reordered) == len(self.tracks):
            self.tracks = reordered
            self._mark_dirty()
        self._refresh_tracks_labels()
        self._schedule_preview(200)

    def _on_rename_track_clicked(self) -> None:
        row = self.track_list.currentRow()
        if row >= 0:
            self.rename_track(self.track_list.item(row))
        elif self.tracks:
            self.track_list.setCurrentRow(0)
            self.rename_track(self.track_list.item(0))

    def rename_track(self, item: Optional[QListWidgetItem] = None) -> None:
        if item is None:
            row = self.track_list.currentRow()
            if row >= 0:
                item = self.track_list.item(row)
        if item is None:
            return
        idx = self.track_list.row(item)
        if idx < 0 or idx >= len(self.tracks):
            return
        cur_title = self.tracks[idx]["title"]
        title, ok = QInputDialog.getText(
            self, "Edit playlist title",
            f"Title shown in the video for track #{idx + 1:02d} ({len(cur_title)} chars):",
            text=cur_title
        )
        if ok and title.strip():
            self.tracks[idx]["title"] = title.strip()
            self._mark_dirty()
            self._refresh_tracks()
            self._schedule_preview(150)

    def remove_track(self) -> None:
        idx = self.track_list.currentRow()
        if idx >= 0:
            self.tracks.pop(idx)
            self._mark_dirty()
            self._refresh_tracks()
            self._schedule_preview(200)

    def move_track(self, delta: int) -> None:
        idx = self.track_list.currentRow()
        target = idx + delta
        if idx < 0 or not (0 <= target < len(self.tracks)):
            return
        self.tracks[idx], self.tracks[target] = self.tracks[target], self.tracks[idx]
        self._mark_dirty()
        self._refresh_tracks()
        self.track_list.setCurrentRow(target)
        self._schedule_preview(200)

    # ------------------------------------------------------------------
    # Output Path
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
        """Commit draft title to project and schedule preview."""
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

    def choose_custom_title_font(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose custom font file for Title", "",
            "Font files (*.ttf *.otf *.ttc);;TrueType Font (*.ttf);;OpenType Font (*.otf);;All files (*.*)"
        )
        if path:
            self._set_custom_font(path, is_title=True)

    def choose_custom_track_font(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose custom font file for Playlist Tracks", "",
            "Font files (*.ttf *.otf *.ttc);;TrueType Font (*.ttf);;OpenType Font (*.otf);;All files (*.*)"
        )
        if path:
            self._set_custom_font(path, is_title=False)

    def _set_custom_font(self, font_path: str, is_title: bool = True) -> None:
        from src.services.font_service import register_custom_font
        try:
            family, style = register_custom_font(font_path)
            if is_title:
                self.custom_title_font_path = font_path
                self._refresh_system_fonts(initial=False)
                if hasattr(self, "title_font_combo"):
                    self.title_font_combo.setCurrentText(family)
                if style and hasattr(self, "title_style_combo"):
                    self.title_style_combo.setCurrentText(style)
            else:
                self.custom_track_font_path = font_path
                self._refresh_system_fonts(initial=False)
                if hasattr(self, "track_font_combo"):
                    self.track_font_combo.setCurrentText(family)
                if style and hasattr(self, "track_style_combo"):
                    self.track_style_combo.setCurrentText(style)
            self._mark_dirty()
            self._schedule_preview(150)
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Font File", f"Could not load custom font:\n\n{exc}")

    def _on_logo_pos_changed(self, text: str) -> None:
        self._mark_dirty()
        self._check_logo_website_overlap()
        self._schedule_preview(150)

    def _on_website_text_changed(self, text: str) -> None:
        self._mark_dirty()
        self._check_logo_website_overlap()
        self._schedule_preview(200)

    def _on_website_show_toggled(self, checked: bool) -> None:
        if hasattr(self, "website_opacity_slider"):
            self.website_opacity_slider.setEnabled(checked)
        self._check_logo_website_overlap()
        self._on_layout_param_changed()

    def _on_website_opacity_changed(self, val: int) -> None:
        if hasattr(self, "website_opacity_val"):
            self.website_opacity_val.setText(f"{val}%")
        self._on_layout_param_changed()

    def _on_track_row_changed(self, row: int) -> None:
        if not getattr(self, "_loading_project", False):
            self._schedule_preview(120)

    def _on_website_pos_changed(self, text: str) -> None:
        self._mark_dirty()
        self._check_logo_website_overlap()
        self._schedule_preview(150)

    def _on_website_size_changed(self, val: int) -> None:
        self._mark_dirty()
        self._schedule_preview(150)

    def _check_logo_website_overlap(self) -> None:
        if not hasattr(self, "overlap_warning") or not hasattr(self, "logo_pos_combo") or not hasattr(self, "website_pos_combo"):
            return
        has_logo = bool(self.logo_path)
        is_shown = (not hasattr(self, "website_show_check")) or self.website_show_check.isChecked()
        has_web = bool(self.website_edit.text().strip()) and is_shown
        same_corner = (self.logo_pos_combo.currentText().strip().lower() == self.website_pos_combo.currentText().strip().lower())
        self.overlap_warning.setVisible(has_logo and has_web and same_corner)

    def _on_title_visibility_changed(self) -> None:
        self._update_title_spacing_enabled()
        self._on_layout_param_changed()

    def _update_title_spacing_enabled(self) -> None:
        if not hasattr(self, "title_spacing_spin"):
            return
        is_shown = (not hasattr(self, "title_show_check")) or self.title_show_check.isChecked()
        pos = self.title_pos_combo.currentText() if hasattr(self, "title_pos_combo") else "Top-Center"
        enabled = is_shown and (pos != "Hidden")
        self.title_spacing_spin.setEnabled(enabled)
        if hasattr(self, "title_spacing_lbl"):
            self.title_spacing_lbl.setEnabled(enabled)
            if not enabled:
                self.title_spacing_spin.setToolTip("Title-Playlist spacing is inactive because the collection title is hidden.")
            else:
                self.title_spacing_spin.setToolTip("Vertical spacing between title rendered bounds and playlist (0 - 250 px)")

    def _on_title_spacing_changed(self, val: int) -> None:
        self._mark_dirty()
        self._schedule_preview(150)

    def _on_title_opacity_changed(self, val: int) -> None:
        if hasattr(self, "title_opacity_val"):
            self.title_opacity_val.setText(f"{val}%")
        self._on_layout_param_changed()

    def _on_track_opacity_changed(self, val: int) -> None:
        if hasattr(self, "track_opacity_val"):
            self.track_opacity_val.setText(f"{val}%")
        self._on_layout_param_changed()

    def _on_layout_param_changed(self) -> None:
        self._mark_dirty()
        self._schedule_preview(150)

    def _on_playlist_bg_changed(self, val: int) -> None:
        if hasattr(self, "playlist_bg_val_lbl"):
            self.playlist_bg_val_lbl.setText(f"{val}% (Transparent)" if val == 0 else f"{val}%")
        self._on_layout_param_changed()

    def _on_highlight_opacity_changed(self, val: int) -> None:
        if hasattr(self, "highlight_opacity_val"):
            self.highlight_opacity_val.setText(f"{val}%")
        self._on_layout_param_changed()

    def _update_highlight_color_btn(self) -> None:
        if not hasattr(self, "highlight_color_btn"):
            return
        rgb = _hex_to_rgb(getattr(self, "highlight_color", (248, 220, 139)))
        hex_code = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
        pix = QPixmap(14, 14)
        pix.fill(QColor(rgb[0], rgb[1], rgb[2]))
        self.highlight_color_btn.setIcon(QIcon(pix))
        self.highlight_color_btn.setText(f" {hex_code}")
        self.highlight_color_btn.setToolTip(f"Click to change highlight color ({hex_code})")

    def choose_highlight_color(self) -> None:
        rgb = _hex_to_rgb(getattr(self, "highlight_color", (248, 220, 139)))
        init_color = QColor(rgb[0], rgb[1], rgb[2])
        col = QColorDialog.getColor(init_color, self, "Choose Highlight Color")
        if col.isValid():
            new_rgb = (col.red(), col.green(), col.blue())
            self.set_highlight_color(new_rgb)

    def reset_highlight_color(self) -> None:
        self.set_highlight_color((248, 220, 139))

    def set_highlight_color(self, color: Union[str, tuple, list]) -> None:
        """Update highlight color, marking dirty state and scheduling preview update."""
        self.highlight_color = color
        self._update_highlight_color_btn()
        self._on_layout_param_changed()

    def _update_title_color_btn(self) -> None:
        if not hasattr(self, "title_color_btn"):
            return
        rgb = _hex_to_rgb(getattr(self, "title_color", (255, 255, 255)))
        hex_code = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
        pix = QPixmap(14, 14)
        pix.fill(QColor(rgb[0], rgb[1], rgb[2]))
        self.title_color_btn.setIcon(QIcon(pix))
        self.title_color_btn.setText(f" {hex_code}")
        self.title_color_btn.setToolTip(f"Click to change title text color ({hex_code})")

    def choose_title_color(self) -> None:
        rgb = _hex_to_rgb(getattr(self, "title_color", (255, 255, 255)))
        init_color = QColor(rgb[0], rgb[1], rgb[2])
        col = QColorDialog.getColor(init_color, self, "Choose Title Color")
        if col.isValid():
            new_rgb = (col.red(), col.green(), col.blue())
            self.set_title_color(new_rgb)

    def reset_title_color(self) -> None:
        self.set_title_color((255, 255, 255))

    def set_title_color(self, color: Union[str, tuple, list]) -> None:
        self.title_color = color
        self._update_title_color_btn()
        self._on_layout_param_changed()

    def _update_track_color_btn(self) -> None:
        if not hasattr(self, "track_color_btn"):
            return
        rgb = _hex_to_rgb(getattr(self, "track_color", (255, 255, 255)))
        hex_code = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
        pix = QPixmap(14, 14)
        pix.fill(QColor(rgb[0], rgb[1], rgb[2]))
        self.track_color_btn.setIcon(QIcon(pix))
        self.track_color_btn.setText(f" {hex_code}")
        self.track_color_btn.setToolTip(f"Click to change track text color ({hex_code})")

    def choose_track_color(self) -> None:
        rgb = _hex_to_rgb(getattr(self, "track_color", (255, 255, 255)))
        init_color = QColor(rgb[0], rgb[1], rgb[2])
        col = QColorDialog.getColor(init_color, self, "Choose Track Text Color")
        if col.isValid():
            new_rgb = (col.red(), col.green(), col.blue())
            self.set_track_color(new_rgb)

    def reset_track_color(self) -> None:
        self.set_track_color((255, 255, 255))

    def set_track_color(self, color: Union[str, tuple, list]) -> None:
        self.track_color = color
        self._update_track_color_btn()
        self._on_layout_param_changed()

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
                self.preview_intro_btn.setText("Preview Playlist")
            else:
                self.preview_intro_btn.setText("Preview Intro Card")
        self._refresh_preview()

    def _on_template_changed(self, text: str) -> None:
        self._mark_dirty()
        norm = str(text or "").strip().lower()
        if norm == "cinematic":
            if hasattr(self, "playlist_pos_combo"):
                _set_combo_case_insensitive(self.playlist_pos_combo, "Left")
            if hasattr(self, "playlist_cols_spin"):
                self.playlist_cols_spin.setValue(1)
        elif norm == "minimal":
            if hasattr(self, "playlist_pos_combo"):
                _set_combo_case_insensitive(self.playlist_pos_combo, "Right")
            if hasattr(self, "playlist_cols_spin"):
                self.playlist_cols_spin.setValue(1)
        elif norm in ("two-column", "two column", "2-column"):
            if hasattr(self, "playlist_pos_combo"):
                _set_combo_case_insensitive(self.playlist_pos_combo, "Left")
            if hasattr(self, "playlist_cols_spin"):
                self.playlist_cols_spin.setValue(2)
        self._refresh_preview()

    def _on_resolution_changed(self, text: str) -> None:
        self._mark_dirty()
        self._update_resolution_badge()

    def _schedule_preview(self, delay: int = 300) -> None:
        """Debounce preview generation (~300ms) to keep UI thread fluid."""
        self._preview_timer.start(delay)

    def _flush_preview(self) -> None:
        """Immediately commit any pending title or preview updates."""
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
        res_text = self.resolution_combo.currentText() if hasattr(self, "resolution_combo") else "1080p · Full HD"
        size = RESOLUTIONS.get(res_text, (1920, 1080))
        has_bg = bool(self.background_path and Path(self.background_path).is_file())
        is_vid = is_video_file(self.background_path) if has_bg else False
        has_tracks = bool(self.tracks)
        if is_vid:
            self.preview_badge.setText(f"PREVIEW · Video Background (MP4) · 16:9 · {size[0]}×{size[1]}")
        elif not has_bg or not has_tracks:
            self.preview_badge.setText(f"PREVIEW · {size[0]}×{size[1]} · SAMPLE LAYOUT")
        else:
            self.preview_badge.setText(f"PREVIEW · 16:9 · {size[0]}×{size[1]}")

    def _refresh_preview(self) -> None:
        self._update_resolution_badge()
        target_size = self.preview_frame.size()
        if target_size.width() <= 10 or target_size.height() <= 10:
            target_size = QSize(640, 360)

        valid_bg = self.background_path if (self.background_path and Path(self.background_path).is_file()) else ""

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
        web_show = self.website_show_check.isChecked() if hasattr(self, "website_show_check") else True
        web_op = round(self.website_opacity_slider.value() / 100.0, 2) if hasattr(self, "website_opacity_slider") else 1.0
        cur_mode = self._mode_from_combo()
        cur_cursor_size = self.cursor_size_spin.value() if hasattr(self, "cursor_size_spin") else 32
        cur_track_row = max(0, self.track_list.currentRow()) if (hasattr(self, "track_list") and self.track_list.currentRow() >= 0) else 0
        hl_color = getattr(self, "highlight_color", (248, 220, 139))
        hl_rgb = _hex_to_rgb(hl_color, (248, 220, 139))
        col_sp = self.col_spacing_spin.value() if hasattr(self, "col_spacing_spin") else 50
        max_chars = self.track_max_chars_spin.value() if hasattr(self, "track_max_chars_spin") else 0
        title_spacing = self.title_spacing_spin.value() if hasattr(self, "title_spacing_spin") else 40
        title_op = round(self.title_opacity_slider.value() / 100.0, 2) if hasattr(self, "title_opacity_slider") else 1.0
        track_op = round(self.track_opacity_slider.value() / 100.0, 2) if hasattr(self, "track_opacity_slider") else 1.0
        text_soft = round(self.text_softening_spin.value(), 1) if hasattr(self, "text_softening_spin") else 0.0

        cache_key = (
            self.background_path, self.logo_path, self.cursor_path,
            self._committed_title, tuple(t.get("title", "") for t in self.tracks),
            self.template_combo.currentText() if hasattr(self, "template_combo") else "",
            title_fam, title_style, title_sz,
            track_fam, track_style, track_sz,
            logo_pos, web_txt, web_pos, web_sz, web_show, web_op,
            getattr(self, "_previewing_intro", False),
            self.playlist_pos_combo.currentText() if hasattr(self, "playlist_pos_combo") else "Left",
            self.playlist_cols_spin.value() if hasattr(self, "playlist_cols_spin") else 1,
            col_sp,
            max_chars,
            round(self.track_spacing_spin.value(), 2) if hasattr(self, "track_spacing_spin") else 1.85,
            round(self.playlist_bg_slider.value() / 100.0, 2) if hasattr(self, "playlist_bg_slider") else 0.0,
            self.highlight_style_combo.currentText() if hasattr(self, "highlight_style_combo") else "Pill",
            hl_rgb,
            round(self.highlight_opacity_slider.value() / 100.0, 2) if hasattr(self, "highlight_opacity_slider") else 0.25,
            (hasattr(self, "logo_cleanup_check") and self.logo_cleanup_check.isChecked()),
            self.title_pos_combo.currentText() if hasattr(self, "title_pos_combo") else "Top-Center",
            self.title_show_check.isChecked() if hasattr(self, "title_show_check") else True,
            cur_mode,
            cur_cursor_size,
            cur_track_row,
            self.video_fit_combo.currentText() if hasattr(self, "video_fit_combo") else "Fill / Crop (Cover)",
            self.video_start_spin.value() if hasattr(self, "video_start_spin") else 0.0,
            self.video_loop_check.isChecked() if hasattr(self, "video_loop_check") else True,
            title_spacing,
            title_op,
            track_op,
            text_soft,
            self.highlight_outline_spin.value() if hasattr(self, "highlight_outline_spin") else 2,
            self.highlight_corner_combo.currentText() if hasattr(self, "highlight_corner_combo") else "Rounded",
            self.highlight_target_combo.currentText() if hasattr(self, "highlight_target_combo") else "Full Row",
            self.cursor_y_offset_spin.value() if hasattr(self, "cursor_y_offset_spin") else 0,
            self.highlight_y_offset_spin.value() if hasattr(self, "highlight_y_offset_spin") else 0,
            getattr(self, "title_color", (255, 255, 255)),
            getattr(self, "track_color", (255, 255, 255)),
            getattr(self, "active_track_color", None),
        )

        if getattr(self, "_cached_preview_key", None) == cache_key and self._cached_preview_pixmap:
            scaled_pix = self._cached_preview_pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_image.setPixmap(scaled_pix)
            self.preview_image.setText("")
            return

        # If user is previewing intro presentation card
        if getattr(self, "_previewing_intro", False):
            try:
                with tempfile.TemporaryDirectory(prefix="nasheed_intro_prev_") as tmp:
                    card_path = create_intro_card(
                        width=1280,
                        height=720,
                        background_path=valid_bg,
                        logo_path=self.logo_path or None,
                        collection_title=self._committed_title or "Nasheed Collection",
                        template=self.template_combo.currentText(),
                        out_dir=tmp,
                        title_font_family=title_fam,
                        title_font_style=title_style,
                        title_font_size=title_sz,
                        website_text=web_txt,
                        website_show=web_show,
                        website_opacity=web_op,
                        website_font_size=web_sz,
                        website_font_family=getattr(self, "website_font_family", None) or title_fam,
                        website_font_style=getattr(self, "website_font_style", "Regular"),
                        website_color=getattr(self, "website_color", None),
                    )
                    pix = QPixmap(card_path)
                    scaled_pix = pix.scaled(
                        target_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.preview_image.setPixmap(scaled_pix)
                    self.preview_image.setText("")
            except Exception as exc:
                self.preview_image.setPixmap(QPixmap())
                self.preview_image.setText(f"Intro preview unavailable: {exc}")
            return

        try:
            with tempfile.TemporaryDirectory(prefix="nasheed_preview_") as tmp:
                sample_candidates = [
                    "01. Example Nasheed One",
                    "02. Example Nasheed Two",
                    "03. Example Nasheed Three",
                    "04. Example Nasheed Four",
                    "05. Example Nasheed Five",
                    "06. Example Nasheed Six",
                ]
                titles = (
                    [t["title"] for t in self.tracks]
                    or sample_candidates
                )
                base, overlays = create_composition(
                    width=1280,
                    height=720,
                    background_path=valid_bg,
                    logo_path=self.logo_path or None,
                    collection_title=self._committed_title or "Nasheed Collection",
                    track_titles=titles,
                    template=self.template_combo.currentText(),
                    out_dir=tmp,
                    indicator_mode=cur_mode,
                    cursor_path=self.cursor_path or None,
                    cursor_size=cur_cursor_size,
                    preview_only_first_overlay=True,
                    active_track_index=cur_track_row,
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
                    website_show=web_show,
                    website_opacity=web_op,
                    website_font_family=getattr(self, "website_font_family", None) or track_fam,
                    website_font_style=getattr(self, "website_font_style", "Regular"),
                    website_color=getattr(self, "website_color", None),
                    playlist_position=self.playlist_pos_combo.currentText() if hasattr(self, "playlist_pos_combo") else "Left",
                    playlist_columns=self.playlist_cols_spin.value() if hasattr(self, "playlist_cols_spin") else 1,
                    playlist_row_spacing=round(self.track_spacing_spin.value(), 2) if hasattr(self, "track_spacing_spin") else 1.85,
                    playlist_col_spacing=col_sp,
                    track_max_chars=max_chars,
                    playlist_bg_opacity=round(self.playlist_bg_slider.value() / 100.0, 2) if hasattr(self, "playlist_bg_slider") else 0.0,
                    logo_cleanup_mode="auto" if (hasattr(self, "logo_cleanup_check") and self.logo_cleanup_check.isChecked()) else "none",
                    title_position=self.title_pos_combo.currentText() if hasattr(self, "title_pos_combo") else "Top-Center",
                    title_show=self.title_show_check.isChecked() if hasattr(self, "title_show_check") else True,
                    title_color=getattr(self, "title_color", (255, 255, 255)),
                    track_color=getattr(self, "track_color", (255, 255, 255)),
                    cursor_y_offset=self.cursor_y_offset_spin.value() if hasattr(self, "cursor_y_offset_spin") else 0,
                    highlight_y_offset=self.highlight_y_offset_spin.value() if hasattr(self, "highlight_y_offset_spin") else 0,
                    active_track_color=getattr(self, "active_track_color", None),
                    highlight_style=self.highlight_style_combo.currentText() if hasattr(self, "highlight_style_combo") else "Pill",
                    highlight_color=hl_rgb,
                    highlight_bg_opacity=round(self.highlight_opacity_slider.value() / 100.0, 2) if hasattr(self, "highlight_opacity_slider") else 0.25,
                    highlight_outline_width=self.highlight_outline_spin.value() if hasattr(self, "highlight_outline_spin") else 2,
                    highlight_corner_radius=(0 if (hasattr(self, "highlight_corner_combo") and self.highlight_corner_combo.currentText() == "Square (Sharp)") else None),
                    highlight_target=("text" if (hasattr(self, "highlight_target_combo") and self.highlight_target_combo.currentText() == "Surround Text") else "row"),
                    video_start_time=self.video_start_spin.value() if hasattr(self, "video_start_spin") else 0.0,
                    video_fit_mode=self.video_fit_combo.currentText() if hasattr(self, "video_fit_combo") else "Fill / Crop (Cover)",
                    title_playlist_spacing=title_spacing,
                    title_opacity=title_op,
                    track_opacity=track_op,
                    title_softening=text_soft,
                    track_softening=text_soft,
                )

                # Cache transparent foreground overlay for real-time video playback preview
                fg_path = Path(tmp) / "composition_fg.png"
                if fg_path.is_file():
                    try:
                        fg_img = Image.open(fg_path).convert("RGBA")
                        if overlays:
                            fg_img = Image.alpha_composite(fg_img, Image.open(overlays[0]).convert("RGBA"))
                        fg_cached = Path(tmp) / "cached_live_overlay.png"
                        fg_img.save(fg_cached)
                        self._current_overlay_pixmap = QPixmap(str(fg_cached))
                    except Exception:
                        self._current_overlay_pixmap = None

                img = Image.open(base).convert("RGBA")
                if overlays:
                    img = Image.alpha_composite(img, Image.open(overlays[0]).convert("RGBA"))
                preview_path = Path(tmp) / "preview.png"
                img.save(preview_path)
                pix = QPixmap(str(preview_path))
                self._cached_preview_key = cache_key
                self._cached_preview_pixmap = pix

                if not getattr(self, "_is_preview_playing", False):
                    scaled_pix = pix.scaled(
                        target_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.preview_image.setPixmap(scaled_pix)
                    self.preview_image.setText("")
        except Exception as exc:
            self.preview_image.setPixmap(QPixmap())
            self.preview_image.setText(f"Preview unavailable: {exc}")

    def _toggle_video_preview(self) -> None:
        """Toggle live playback preview of video background."""
        if not self.background_path or not is_video_file(self.background_path):
            return
        if self._is_preview_playing:
            self._stop_video_preview()
        else:
            self._start_video_preview()

    def _start_video_preview(self) -> None:
        """Start playing moving background video preview."""
        if not self.background_path or not Path(self.background_path).is_file():
            return
        if not self._video_player:
            self._video_player = QMediaPlayer(self)
            self._video_sink = QVideoSink(self)
            self._video_player.setVideoSink(self._video_sink)
            self._video_sink.videoFrameChanged.connect(self._on_video_frame_received)
            self._video_player.setLoops(QMediaPlayer.Loops.Infinite)

        st_ms = int(self.video_start_spin.value() * 1000.0) if hasattr(self, "video_start_spin") else 0
        self._video_player.setSource(QUrl.fromLocalFile(str(Path(self.background_path).resolve())))
        self._video_player.setPosition(st_ms)
        self._video_player.play()
        self._is_preview_playing = True
        if hasattr(self, "play_preview_btn"):
            self.play_preview_btn.setText("Pause Video Preview")
            self.play_preview_btn.setIcon(get_svg_icon("pause", 13, "#edf2ee"))

    def _stop_video_preview(self) -> None:
        """Stop/pause live moving video preview and restore static representative frame."""
        if self._video_player:
            try:
                self._video_player.pause()
            except Exception:
                pass
        self._is_preview_playing = False
        if hasattr(self, "play_preview_btn"):
            self.play_preview_btn.setText("Play Video Preview")
            self.play_preview_btn.setIcon(get_svg_icon("play", 13, "#edf2ee"))
        # Refresh to pristine representative frame
        if getattr(self, "_cached_preview_pixmap", None) and not self._cached_preview_pixmap.isNull():
            target_size = self.preview_frame.size()
            if target_size.width() <= 10 or target_size.height() <= 10:
                target_size = QSize(640, 360)
            scaled_pix = self._cached_preview_pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_image.setPixmap(scaled_pix)
            self.preview_image.setText("")

    def _on_video_frame_received(self, frame) -> None:
        """Render live video frame with playlist typography overlay composited on top."""
        if not self._is_preview_playing or frame is None or not frame.isValid():
            return
        qimg = frame.toImage()
        if qimg.isNull():
            return
        target_size = self.preview_frame.size()
        if target_size.width() <= 10 or target_size.height() <= 10:
            target_size = QSize(640, 360)

        fit = self.video_fit_combo.currentText().lower() if hasattr(self, "video_fit_combo") else "fill"
        w, h = target_size.width(), target_size.height()

        if "pad" in fit or "letterbox" in fit:
            scaled = qimg.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            canvas = QImage(target_size, QImage.Format.Format_ARGB32_Premultiplied)
            canvas.fill(Qt.GlobalColor.black)
            p = QPainter(canvas)
            ox = (w - scaled.width()) // 2
            oy = (h - scaled.height()) // 2
            p.drawImage(ox, oy, scaled)
        elif "stretch" in fit:
            canvas = qimg.scaled(target_size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            p = QPainter(canvas)
        else:  # "fill / crop (cover)"
            scaled = qimg.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            ox = max(0, (scaled.width() - w) // 2)
            oy = max(0, (scaled.height() - h) // 2)
            canvas = scaled.copy(ox, oy, w, h)
            p = QPainter(canvas)

        if getattr(self, "_current_overlay_pixmap", None) and not self._current_overlay_pixmap.isNull():
            ov_cache_key = (id(self._current_overlay_pixmap), w, h)
            if getattr(self, "_scaled_overlay_cache_key", None) != ov_cache_key or not hasattr(self, "_scaled_overlay_pixmap"):
                self._scaled_overlay_cache_key = ov_cache_key
                self._scaled_overlay_pixmap = self._current_overlay_pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            p.drawPixmap(0, 0, self._scaled_overlay_pixmap)
        p.end()

        self.preview_image.setPixmap(QPixmap.fromImage(canvas))
        self.preview_image.setText("")

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
    # Bug C: Export Lifecycle & Safe Background Rendering
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
                                "Choose a background image or video before exporting.")
            return
        if not self.output_edit.text().strip():
            QMessageBox.warning(self, "No output path", "Choose where to save the MP4.")
            return

        # Collision & Overwrite Guard
        out_path = Path(self.output_edit.text().strip()).expanduser().resolve()
        overwrite = False

        while out_path.exists():
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle("File already exists")
            box.setText(f"The export file already exists:\n\n{out_path.name}\n\nWhat would you like to do?")
            btn_overwrite = box.addButton("Overwrite", QMessageBox.ButtonRole.AcceptRole)
            btn_rename = box.addButton("Choose Another Name", QMessageBox.ButtonRole.ActionRole)
            btn_cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(btn_rename)

            box.exec()
            clicked = box.clickedButton()

            if clicked == btn_cancel or clicked is None:
                return  # Safe abort: existing file left untouched
            elif clicked == btn_overwrite:
                overwrite = True
                break
            elif clicked == btn_rename:
                new_path, _ = QFileDialog.getSaveFileName(
                    self, "Choose another export name", str(out_path), "MP4 video (*.mp4)"
                )
                if not new_path:
                    return
                if not new_path.lower().endswith(".mp4"):
                    new_path += ".mp4"
                self.output_edit.setText(new_path)
                out_path = Path(new_path).expanduser().resolve()

        job_id = generate_job_id()
        # Isolate work_dir in workspace temp/ (never pollute user folder)
        work_dir = create_job_work_dir(job_id=job_id)
        # Staging file in destination directory with valid .mp4 extension for FFmpeg
        staging_path = get_staging_path(out_path, job_id=job_id)

        project = self._project()
        project["output_path"] = str(out_path)

        try:
            command, resolved_out = build_render_command(
                project, work_dir, self._bridge.progress.emit, target_path=staging_path
            )
        except Exception as exc:
            cleanup_job_work_dir(work_dir)
            cleanup_staging(staging_path)
            QMessageBox.critical(self, "Cannot start export", str(exc))
            return

        self._job = ExportJob(
            command, work_dir, out_path,
            staging_path=staging_path,
            overwrite=overwrite,
            job_id=job_id,
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
        if hasattr(self, "progress"):
            import re
            m = re.search(r"(\d+)%", message)
            if m:
                self.progress.setValue(int(m.group(1)))

    def _render_complete(self, path: str) -> None:
        self._set_ui_running(False)
        p = Path(path)
        sz_mb = p.stat().st_size / (1024 * 1024) if p.exists() else 0.0
        res = self.resolution_combo.currentText() if hasattr(self, "resolution_combo") else "1080p"
        self.status_label.setText(f"Export complete: {p.name} ({res}, {sz_mb:.1f} MB)")
        self._job = None
        QMessageBox.information(self, "Video exported",
                                f"Your MP4 has been created:\n\n{path}\n\nResolution: {res}\nFile size: {sz_mb:.1f} MB")

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
    # Bug C: Close-Event Confirmation & Graceful Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if getattr(self, "_is_closing", False):
            event.ignore()
            return
        self._stop_video_preview()
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
    # Project Persistence, Dirty-State & UI Indicators
    # ------------------------------------------------------------------

    def _mark_dirty(self, *args) -> None:
        if not self._loading_project:
            self._is_dirty = True
            self._update_project_ui_indicators()

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

    def _update_project_ui_indicators(self) -> None:
        """Update top bar project name, window title, and unsaved pill badge."""
        dirty = self.has_unsaved_changes()
        name = Path(self.project_path).stem if self.project_path else (self._committed_title or "Unsaved Project")
        if hasattr(self, "project_name_label"):
            self.project_name_label.setText(name)
        if hasattr(self, "unsaved_pill"):
            self.unsaved_pill.setVisible(dirty)
        star = " *" if dirty else ""
        self.setWindowTitle(f"Nasheed Studio · {name}{star}")

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
            if hasattr(self, "title_spacing_spin"):
                self.title_spacing_spin.setValue(40)
            if hasattr(self, "title_opacity_slider"):
                self.title_opacity_slider.setValue(100)
            if hasattr(self, "track_font_combo"):
                self.track_font_combo.setCurrentText("Segoe UI" if "Segoe UI" in [self.track_font_combo.itemText(i) for i in range(self.track_font_combo.count())] else self.track_font_combo.itemText(0))
                self.track_style_combo.setCurrentText("Bold")
                self.track_size_spin.setValue(22)
            if hasattr(self, "track_opacity_slider"):
                self.track_opacity_slider.setValue(100)
            if hasattr(self, "text_softening_spin"):
                self.text_softening_spin.setValue(0.0)
            self._update_title_spacing_enabled()
            if hasattr(self, "website_edit"):
                self.website_edit.setText("")
                self.website_pos_combo.setCurrentText("Top-Right")
                self.website_size_spin.setValue(18)
                if hasattr(self, "website_show_check"):
                    self.website_show_check.setChecked(True)
                if hasattr(self, "website_opacity_slider"):
                    self.website_opacity_slider.setValue(100)
                self.website_font_family = None
                self.website_font_style = "Regular"
                self.website_color = None
                self.overlap_warning.setVisible(False)
            if hasattr(self, "intro_check"):
                self.intro_check.setChecked(False)
                self.intro_dur_spin.setValue(3.0)
                self.intro_anim_combo.setCurrentText("Fade in / out")
                self.preview_intro_btn.setText("Preview Intro Card")
            if hasattr(self, "sfx_check"):
                self.sfx_check.setChecked(False)
                self.sfx_vol_slider.setValue(70)
            self.highlight_color = (248, 220, 139)
            self._update_highlight_color_btn()
            self.title_color = (255, 255, 255)
            self._update_title_color_btn()
            self.track_color = (255, 255, 255)
            self._update_track_color_btn()
            self.active_track_color = None
            if hasattr(self, "cursor_y_offset_spin"):
                self.cursor_y_offset_spin.setValue(0)
            if hasattr(self, "highlight_y_offset_spin"):
                self.highlight_y_offset_spin.setValue(0)
            if hasattr(self, "highlight_outline_spin"):
                self.highlight_outline_spin.setValue(2)
            if hasattr(self, "highlight_corner_combo"):
                self.highlight_corner_combo.setCurrentText("Rounded")
            if hasattr(self, "highlight_target_combo"):
                self.highlight_target_combo.setCurrentText("Full Row")
            if hasattr(self, "highlight_style_combo"):
                self.highlight_style_combo.setCurrentText("Pill")
            if hasattr(self, "highlight_opacity_slider"):
                self.highlight_opacity_slider.setValue(25)
            self.output_edit.setText(str(get_exports_dir() / "nasheed_collection.mp4"))
            self._refresh_tracks()
            self._refresh_preview()
            self._is_dirty = False
            self._last_saved_snapshot = None
            self._update_project_ui_indicators()
            self.status_label.setText("New project ready.")
        finally:
            self._loading_project = False

    def save_project(self) -> bool:
        if not self.project_path:
            return self.save_project_as()
        return self._write_project(self.project_path)

    def save_project_as(self) -> bool:
        default_path = self.project_path or str(get_projects_dir() / "nasheed_project.json")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save project",
            default_path,
            "Nasheed Studio project (*.json)"
        )
        if path:
            if not path.lower().endswith(".json"):
                path += ".json"
            return self._write_project(path)
        return False

    def _write_project(self, path: str) -> bool:
        try:
            save_project_atomic(self._project(), path)
            self.project_path = path
            self._is_dirty = False
            self._last_saved_snapshot = self._project()
            self._add_recent_project(path)
            self._update_project_ui_indicators()
            self.status_label.setText(f"Project saved: {path}")
            return True
        except Exception as exc:
            # Failed save preserves dirty state
            QMessageBox.critical(self, "Save failed", str(exc))
            return False

    def save_as_template(self) -> None:
        """Save reusable visual design and styling settings independently of tracks and titles."""
        name, ok = QInputDialog.getText(
            self, "Save Reusable Template", "Template name:",
            text=self.template_combo.currentText() + " Preset"
        )
        if not ok or not name:
            return
        clean_name = name.strip()
        if not clean_name:
            QMessageBox.warning(self, "Invalid Template Name", "Template name cannot be empty or only spaces.")
            return

        # Sanitize filename: strip characters disallowed on Windows / filesystem
        invalid_chars = '<>:"/\\|?*'
        safe_name = "".join(c for c in clean_name if c not in invalid_chars).strip()
        if not safe_name:
            QMessageBox.warning(self, "Invalid Template Name", "Template name contains only invalid filesystem characters.")
            return

        templates_dir = get_templates_dir()
        target_path = templates_dir / f"{safe_name}.json"

        # Check for intentional overwrite
        if target_path.exists():
            ret = QMessageBox.question(
                self, "Overwrite Existing Template",
                f"A template named '{safe_name}' already exists in your workspace:\n\n{target_path}\n\n"
                "Do you want to overwrite it with current styling?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ret != QMessageBox.StandardButton.Yes:
                return

        try:
            tmpl_data = extract_template(self._project(), template_name=safe_name)
            save_template_atomic(tmpl_data, target_path)
            QMessageBox.information(
                self, "Template Saved",
                f"Design template saved successfully:\n\n{target_path.name}\n\n"
                "You can apply this styling to any project without affecting its tracks or titles."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Save Template Failed", str(exc))

    def apply_template(self) -> None:
        """Apply reusable styling settings from a template onto current project."""
        user_tmpl_dir = Path("user_templates")
        if not user_tmpl_dir.is_dir():
            user_tmpl_dir = Path(__file__).resolve().parent.parent.parent / "user_templates"
        templates_dir = user_tmpl_dir if user_tmpl_dir.is_dir() else get_templates_dir()
        path, _ = QFileDialog.getOpenFileName(
            self, "Apply Reusable Template", str(templates_dir),
            "Nasheed Studio Template (*.json);;All files (*.*)"
        )
        if not path:
            return
        try:
            tmpl = load_template(path)
            missing_warnings = []
            if "cursor_path" in tmpl and tmpl["cursor_path"]:
                cp = Path(tmpl["cursor_path"])
                if not cp.is_file():
                    missing_warnings.append(f"Custom cursor not found on disk: {tmpl['cursor_path']} (retained current cursor)")

            if "transition_sfx_path" in tmpl and tmpl["transition_sfx_path"]:
                sp = Path(tmpl["transition_sfx_path"])
                if not sp.is_file():
                    missing_warnings.append(f"Transition sound effect not found on disk: {tmpl['transition_sfx_path']}")

            self._apply_template_data(tmpl)
            self._mark_dirty()
            self._refresh_preview()
            tmpl_display = tmpl.get("template_name") or Path(path).stem
            layout_desc = self.template_combo.currentText() if hasattr(self, "template_combo") else "Preset"
            self.status_label.setText(f"Applied template: {tmpl_display} ({layout_desc})")

            if missing_warnings:
                QMessageBox.warning(
                    self, "Template Applied (Missing Assets Notice)",
                    f"Template '{tmpl_display}' was applied successfully, but some referenced external assets could not be located:\n\n"
                    + "\n\n".join(missing_warnings)
                )
        except Exception as exc:
            QMessageBox.critical(self, "Apply Template Failed", str(exc))


    def _populate_templates_menu(self, menu: QMenu) -> None:
        """Dynamically populate templates dropdown menu with templates from user_templates/ and templates/."""
        templates = discover_user_templates()
        user_tmpls = [t for t in templates if t["category"] == "User Template"]
        presets = [t for t in templates if t["category"] == "Preset"]

        if user_tmpls:
            sec_lbl = menu.addAction("── User Templates Library ──")
            sec_lbl.setEnabled(False)
            for t in user_tmpls:
                act = menu.addAction(f"Template: {t['name']}")
                if t.get("description"):
                    act.setToolTip(t["description"])
                act.triggered.connect(lambda chk=False, p=t["path"]: self._apply_template_file(p))

        # User templates library displayed cleanly without old built-in presets cluttering menu

    def _apply_template_file(self, file_path: str) -> None:
        """Apply a template JSON file from disk preserving audio and playlist content."""
        p = Path(file_path)
        if not p.is_file():
            QMessageBox.warning(self, "Template Not Found", f"Template file does not exist: {file_path}")
            return
        try:
            tmpl = load_template(str(p))
            self._apply_template_data(tmpl)
            if tmpl.get("background") and Path(tmpl["background"]).is_file():
                self.background_path = str(tmpl["background"])
                self._set_asset_label(self.background_label, self.background_path)
            if tmpl.get("collection_title") and hasattr(self, "collection_title"):
                self.collection_title.setText(str(tmpl["collection_title"]))
            self._mark_dirty()
            self._refresh_preview()
            tmpl_name = tmpl.get("template_name") or p.stem
            self.status_label.setText(f"Applied template: {tmpl_name}")
        except Exception as exc:
            QMessageBox.critical(self, "Apply Template Failed", f"Could not apply template {p.name}: {exc}")

    def _apply_built_in_preset(self, filename: str) -> None:
        """Apply a built-in reference preset directly."""
        preset_path = Path("templates") / filename
        if not preset_path.is_file():
            preset_path = Path(__file__).resolve().parent.parent.parent / "templates" / filename
        if preset_path.is_file():
            try:
                tmpl = load_template(str(preset_path))
                self._apply_template_data(tmpl)
                if tmpl.get("background") and Path(tmpl["background"]).is_file():
                    self.background_path = str(tmpl["background"])
                    self._set_asset_label(self.background_label, self.background_path)
                if tmpl.get("collection_title") and hasattr(self, "collection_title"):
                    self.collection_title.setText(str(tmpl["collection_title"]))
                if "website_text" in tmpl and hasattr(self, "website_edit"):
                    self.website_edit.setText(str(tmpl["website_text"]))
                if tmpl.get("logo") and Path(tmpl["logo"]).is_file():
                    self.logo_path = str(tmpl["logo"])
                    self._set_asset_label(self.logo_label, self.logo_path)
                elif "logo" in tmpl and not tmpl["logo"]:
                    self.logo_path = ""
                    self.logo_label.setText("No file selected")
                self._mark_dirty()
                self._refresh_preview()
                tmpl_display = tmpl.get("template_name") or filename
                self.status_label.setText(f"Applied preset: {tmpl_display}")
            except Exception as exc:
                QMessageBox.critical(self, "Preset Load Error", str(exc))

    def _apply_template_data(self, tmpl: dict) -> None:
        """Update visual controls from a template without modifying tracks, titles, or collection assets."""
        if "template" in tmpl:
            _set_combo_case_insensitive(self.template_combo, tmpl["template"])
        if "resolution" in tmpl:
            res_val = str(tmpl["resolution"])
            if not _set_combo_case_insensitive(self.resolution_combo, res_val):
                # Fuzzy match for resolution variants (e.g. 4K, 1440p, 1080p)
                for i in range(self.resolution_combo.count()):
                    item_text = self.resolution_combo.itemText(i).lower()
                    if any(tok in res_val.lower() for tok in ("4k", "2160")) and "4k" in item_text:
                        self.resolution_combo.setCurrentIndex(i)
                        break
                    elif any(tok in res_val.lower() for tok in ("1440", "qhd")) and "1440" in item_text:
                        self.resolution_combo.setCurrentIndex(i)
                        break
                    elif any(tok in res_val.lower() for tok in ("1080", "fhd")) and "1080" in item_text:
                        self.resolution_combo.setCurrentIndex(i)
                        break
        if "indicator_mode" in tmpl:
            self._set_combo_from_mode(tmpl["indicator_mode"])
        if "cursor_size" in tmpl:
            self.cursor_size_spin.setValue(int(tmpl["cursor_size"]))
        if "cursor_path" in tmpl:
            cp = tmpl["cursor_path"]
            if cp and Path(cp).is_file():
                self.cursor_path = cp
                self._set_asset_label(self.cursor_label, cp)
            elif not cp:
                self.cursor_path = ""
                self._set_asset_label(self.cursor_label, "")
        if "title_font_family" in tmpl:
            _set_combo_case_insensitive(self.title_font_combo, tmpl["title_font_family"])
            self._update_title_styles()
        if "title_font_style" in tmpl:
            _set_combo_case_insensitive(self.title_style_combo, tmpl["title_font_style"])
        if "title_font_size" in tmpl:
            self.title_size_spin.setValue(int(tmpl["title_font_size"]))
        if "title_playlist_spacing" in tmpl and hasattr(self, "title_spacing_spin"):
            self.title_spacing_spin.setValue(int(tmpl["title_playlist_spacing"]))
        if "title_opacity" in tmpl and hasattr(self, "title_opacity_slider"):
            self.title_opacity_slider.setValue(int(float(tmpl["title_opacity"]) * 100))
        if "custom_title_font_path" in tmpl:
            self.custom_title_font_path = tmpl["custom_title_font_path"]
            if self.custom_title_font_path and Path(self.custom_title_font_path).is_file():
                try:
                    from src.services.font_service import register_custom_font
                    register_custom_font(self.custom_title_font_path)
                except Exception:
                    pass
        if "track_font_family" in tmpl:
            _set_combo_case_insensitive(self.track_font_combo, tmpl["track_font_family"])
            self._update_track_styles()
        if "track_font_style" in tmpl:
            _set_combo_case_insensitive(self.track_style_combo, tmpl["track_font_style"])
        if "track_font_size" in tmpl:
            self.track_size_spin.setValue(int(tmpl["track_font_size"]))
        if "track_opacity" in tmpl and hasattr(self, "track_opacity_slider"):
            self.track_opacity_slider.setValue(int(float(tmpl["track_opacity"]) * 100))
        if hasattr(self, "text_softening_spin"):
            if "text_softening" in tmpl:
                self.text_softening_spin.setValue(float(tmpl["text_softening"]))
            elif "title_softening" in tmpl:
                self.text_softening_spin.setValue(float(tmpl["title_softening"]))
        if "custom_track_font_path" in tmpl:
            self.custom_track_font_path = tmpl["custom_track_font_path"]
            if self.custom_track_font_path and Path(self.custom_track_font_path).is_file():
                try:
                    from src.services.font_service import register_custom_font
                    register_custom_font(self.custom_track_font_path)
                except Exception:
                    pass
        if "logo_position" in tmpl:
            _set_combo_case_insensitive(self.logo_pos_combo, tmpl["logo_position"])
        if "website_position" in tmpl:
            _set_combo_case_insensitive(self.website_pos_combo, tmpl["website_position"])
        if "website_font_size" in tmpl:
            self.website_size_spin.setValue(int(tmpl["website_font_size"]))
        if "website_show" in tmpl and hasattr(self, "website_show_check"):
            self.website_show_check.setChecked(bool(tmpl["website_show"]))
        if "website_opacity" in tmpl and hasattr(self, "website_opacity_slider"):
            self.website_opacity_slider.setValue(int(float(tmpl["website_opacity"]) * 100))
        if "website_font_family" in tmpl:
            self.website_font_family = tmpl["website_font_family"]
        if "website_font_style" in tmpl:
            self.website_font_style = tmpl["website_font_style"]
        if "website_color" in tmpl:
            wc = tmpl["website_color"]
            self.website_color = tuple(wc) if isinstance(wc, (list, tuple)) else wc
        if "intro_enabled" in tmpl:
            self.intro_check.setChecked(bool(tmpl["intro_enabled"]))
        if "intro_duration" in tmpl:
            self.intro_dur_spin.setValue(float(tmpl["intro_duration"]))
        if "intro_animation" in tmpl:
            _set_combo_case_insensitive(self.intro_anim_combo, tmpl["intro_animation"])
        if "transition_sfx_enabled" in tmpl and hasattr(self, "sfx_check"):
            self.sfx_check.setChecked(bool(tmpl["transition_sfx_enabled"]))
        if "transition_sfx_volume" in tmpl:
            vol = int(float(tmpl["transition_sfx_volume"]) * 100)
            self.sfx_vol_slider.setValue(vol)
        if "transition_sfx_path" in tmpl:
            sp = tmpl["transition_sfx_path"]
            if sp and Path(sp).is_file():
                self.sfx_path = sp
                self._set_asset_label(self.sfx_label, sp)
            elif not sp:
                self.sfx_path = ""
                self._set_asset_label(self.sfx_label, "")
        if "playlist_position" in tmpl and hasattr(self, "playlist_pos_combo"):
            _set_combo_case_insensitive(self.playlist_pos_combo, tmpl["playlist_position"])
        tmpl_tmpl = str(tmpl.get("template", "")).strip().lower()
        if "playlist_columns" in tmpl and hasattr(self, "playlist_cols_spin"):
            self.playlist_cols_spin.setValue(int(tmpl["playlist_columns"]))
        elif tmpl_tmpl in ("two-column", "two column", "2-column") or (hasattr(self, "template_combo") and self.template_combo.currentText() == "Two-column"):
            if hasattr(self, "playlist_cols_spin"):
                self.playlist_cols_spin.setValue(2)
        elif tmpl_tmpl in ("cinematic", "minimal", "single-column"):
            if hasattr(self, "playlist_cols_spin"):
                self.playlist_cols_spin.setValue(1)
        if "playlist_row_spacing" in tmpl and hasattr(self, "track_spacing_spin"):
            self.track_spacing_spin.setValue(float(tmpl["playlist_row_spacing"]))
        if "playlist_col_spacing" in tmpl and hasattr(self, "col_spacing_spin"):
            self.col_spacing_spin.setValue(int(tmpl["playlist_col_spacing"]))
        if "track_max_chars" in tmpl and hasattr(self, "track_max_chars_spin"):
            self.track_max_chars_spin.setValue(int(tmpl["track_max_chars"]))
        if "playlist_bg_opacity" in tmpl and hasattr(self, "playlist_bg_slider"):
            self.playlist_bg_slider.setValue(int(float(tmpl["playlist_bg_opacity"]) * 100))
        if "title_position" in tmpl and hasattr(self, "title_pos_combo"):
            _set_combo_case_insensitive(self.title_pos_combo, tmpl["title_position"])
        if "title_show" in tmpl and hasattr(self, "title_show_check"):
            self.title_show_check.setChecked(bool(tmpl["title_show"]))
        if "title_color" in tmpl:
            self.title_color = tmpl["title_color"]
        if "track_color" in tmpl:
            self.track_color = tmpl["track_color"]
        if "active_track_color" in tmpl:
            self.active_track_color = tmpl["active_track_color"]
        if "highlight_style" in tmpl and hasattr(self, "highlight_style_combo"):
            _set_combo_case_insensitive(self.highlight_style_combo, tmpl["highlight_style"])
        if "highlight_color" in tmpl:
            self.highlight_color = tmpl["highlight_color"]
            self._update_highlight_color_btn()
        if "highlight_bg_opacity" in tmpl and hasattr(self, "highlight_opacity_slider"):
            self.highlight_opacity_slider.setValue(int(float(tmpl["highlight_bg_opacity"]) * 100))
        if "title_color" in tmpl:
            self.title_color = tmpl["title_color"]
            self._update_title_color_btn()
        if "track_color" in tmpl:
            self.track_color = tmpl["track_color"]
            self._update_track_color_btn()
        if "cursor_y_offset" in tmpl and hasattr(self, "cursor_y_offset_spin"):
            self.cursor_y_offset_spin.setValue(int(tmpl["cursor_y_offset"]))
        if "highlight_y_offset" in tmpl and hasattr(self, "highlight_y_offset_spin"):
            self.highlight_y_offset_spin.setValue(int(tmpl["highlight_y_offset"]))
        if "highlight_outline_width" in tmpl and hasattr(self, "highlight_outline_spin"):
            self.highlight_outline_spin.setValue(int(tmpl["highlight_outline_width"]))
        if "highlight_corner_radius" in tmpl and hasattr(self, "highlight_corner_combo"):
            rad = tmpl["highlight_corner_radius"]
            if rad == 0 or rad == "0":
                self.highlight_corner_combo.setCurrentText("Square (Sharp)")
            else:
                self.highlight_corner_combo.setCurrentText("Rounded")
        if "highlight_target" in tmpl and hasattr(self, "highlight_target_combo"):
            tgt = str(tmpl["highlight_target"]).lower().strip()
            if tgt == "text" or "text" in tgt:
                self.highlight_target_combo.setCurrentText("Surround Text")
            else:
                self.highlight_target_combo.setCurrentText("Full Row")
        if "logo_cleanup_mode" in tmpl and hasattr(self, "logo_cleanup_check"):
            self.logo_cleanup_check.setChecked(tmpl["logo_cleanup_mode"] != "none")
        if "resource_profile" in tmpl and hasattr(self, "resource_profile_combo"):
            _set_combo_case_insensitive(self.resource_profile_combo, tmpl["resource_profile"])
        if "video_fit_mode" in tmpl and hasattr(self, "video_fit_combo"):
            _set_combo_case_insensitive(self.video_fit_combo, tmpl["video_fit_mode"])
        if "video_start_time" in tmpl and hasattr(self, "video_start_spin"):
            self.video_start_spin.setValue(float(tmpl["video_start_time"]))
        if "video_loop" in tmpl and hasattr(self, "video_loop_check"):
            self.video_loop_check.setChecked(bool(tmpl["video_loop"]))
        if "video_mute_audio" in tmpl and hasattr(self, "video_mute_check"):
            self.video_mute_check.setChecked(bool(tmpl["video_mute_audio"]))

        proj_root = Path(__file__).resolve().parent.parent.parent
        if "cursor_path" in tmpl:
            cp = tmpl["cursor_path"]
            if cp:
                c_cand = Path(cp) if Path(cp).is_file() else (proj_root / cp)
                if c_cand.is_file():
                    self.cursor_path = str(c_cand.resolve())
                    self._set_asset_label(self.cursor_label, self.cursor_path)
                else:
                    self.cursor_path = ""
                    self._set_asset_label(self.cursor_label, "")
            else:
                self.cursor_path = ""
                self._set_asset_label(self.cursor_label, "")

        # Adopt starter background / logo only if receiving project does not have one
        if tmpl.get("background") and not self.background_path:
            bg_raw = tmpl["background"]
            bg_cand = Path(bg_raw) if Path(bg_raw).is_file() else (proj_root / bg_raw)
            if bg_cand.is_file():
                self.background_path = str(bg_cand.resolve())
                self._set_asset_label(self.background_label, self.background_path)
        if tmpl.get("logo") and not self.logo_path:
            logo_raw = tmpl["logo"]
            logo_cand = Path(logo_raw) if Path(logo_raw).is_file() else (proj_root / logo_raw)
            if logo_cand.is_file():
                self.logo_path = str(logo_cand.resolve())
                self._set_asset_label(self.logo_label, self.logo_path)

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
            if data.get("type") == "template":
                self._apply_template_data(data)
                self._mark_dirty()
                self._refresh_preview()
                tmpl_name = data.get("template_name") or Path(path).stem
                layout_desc = self.template_combo.currentText() if hasattr(self, "template_combo") else "Preset"
                self.status_label.setText(f"Applied styling template: {tmpl_name} ({layout_desc})")
                QMessageBox.information(
                    self, "Template Styling Applied",
                    f"'{Path(path).name}' is a reusable styling template.\n\n"
                    f"Visual design and layout presets ({tmpl_name}) have been applied to your current project. "
                    "Your playlist tracks and collection title were preserved.",
                )
                return

            self.missing_assets = check_missing_assets(data)
            self._loading_project = True
            try:
                if hasattr(self, "_title_timer") and self._title_timer.isActive():
                    self._title_timer.stop()
                self._committed_title = data.get("collection_title", "Nasheed Collection")
                self.background_path = data.get("background", "")
                self.background_type = data.get("background_type", "video" if is_video_file(self.background_path) else "image")
                if self.background_path and Path(self.background_path).is_file():
                    self._apply_background_file(self.background_path)
                else:
                    self.clear_background()

                if hasattr(self, "video_fit_combo") and "video_fit_mode" in data:
                    _set_combo_case_insensitive(self.video_fit_combo, data["video_fit_mode"])
                if hasattr(self, "video_start_spin") and "video_start_time" in data:
                    self.video_start_spin.setValue(float(data["video_start_time"]))
                if hasattr(self, "video_loop_check") and "video_loop" in data:
                    self.video_loop_check.setChecked(bool(data["video_loop"]))
                if hasattr(self, "video_mute_check") and "video_mute_audio" in data:
                    self.video_mute_check.setChecked(bool(data["video_mute_audio"]))

                self.logo_path = data.get("logo", "")
                self.cursor_path = data.get("cursor_path", "")
                self.sfx_path = data.get("transition_sfx_path", "")
                self._previewing_intro = False
                self.tracks = data.get("tracks", [])
                self.collection_title.setText(self._committed_title)
                self.title_apply_btn.setEnabled(False)
                _set_combo_case_insensitive(self.template_combo, data.get("template", "Cinematic"))
                if not _set_combo_case_insensitive(self.resolution_combo, data.get("resolution", "1080p · Full HD")):
                    self.resolution_combo.setCurrentText(data.get("resolution", "1080p · Full HD"))
                self._set_combo_from_mode(data.get("indicator_mode", "both"))
                self.cursor_size_spin.setValue(int(data.get("cursor_size", 32) or 32))

                # Custom Fonts registration
                self.custom_title_font_path = data.get("custom_title_font_path", "")
                self.custom_track_font_path = data.get("custom_track_font_path", "")
                if self.custom_title_font_path and Path(self.custom_title_font_path).is_file():
                    try:
                        from src.services.font_service import register_custom_font
                        register_custom_font(self.custom_title_font_path)
                    except Exception:
                        pass
                if self.custom_track_font_path and Path(self.custom_track_font_path).is_file():
                    try:
                        from src.services.font_service import register_custom_font
                        register_custom_font(self.custom_track_font_path)
                    except Exception:
                        pass
                self._refresh_system_fonts(initial=False)

                if hasattr(self, "logo_pos_combo"):
                    _set_combo_case_insensitive(self.logo_pos_combo, data.get("logo_position", "Bottom-Right"))
                if hasattr(self, "title_font_combo"):
                    _set_combo_case_insensitive(self.title_font_combo, data.get("title_font_family", "Segoe UI"))
                    self._update_title_styles()
                    _set_combo_case_insensitive(self.title_style_combo, data.get("title_font_style", "Bold"))
                    self.title_size_spin.setValue(int(data.get("title_font_size", 46) or 46))
                if hasattr(self, "title_spacing_spin") and "title_playlist_spacing" in data:
                    self.title_spacing_spin.setValue(int(data["title_playlist_spacing"]))
                if hasattr(self, "title_opacity_slider") and "title_opacity" in data:
                    self.title_opacity_slider.setValue(int(float(data["title_opacity"]) * 100))
                if hasattr(self, "track_font_combo"):
                    _set_combo_case_insensitive(self.track_font_combo, data.get("track_font_family", "Segoe UI"))
                    self._update_track_styles()
                    _set_combo_case_insensitive(self.track_style_combo, data.get("track_font_style", "Bold"))
                    self.track_size_spin.setValue(int(data.get("track_font_size", 22) or 22))
                if hasattr(self, "track_opacity_slider") and "track_opacity" in data:
                    self.track_opacity_slider.setValue(int(float(data["track_opacity"]) * 100))
                if hasattr(self, "text_softening_spin"):
                    if "text_softening" in data:
                        self.text_softening_spin.setValue(float(data["text_softening"]))
                    elif "title_softening" in data:
                        self.text_softening_spin.setValue(float(data["title_softening"]))
                if hasattr(self, "website_edit"):
                    self.website_edit.setText(data.get("website_text", ""))
                    _set_combo_case_insensitive(self.website_pos_combo, data.get("website_position", "Top-Right"))
                    self.website_size_spin.setValue(int(data.get("website_font_size", 18) or 18))
                    if hasattr(self, "website_show_check"):
                        self.website_show_check.setChecked(bool(data.get("website_show", True)))
                    if hasattr(self, "website_opacity_slider"):
                        web_op_val = int(float(data.get("website_opacity", 1.0) if data.get("website_opacity") is not None else 1.0) * 100)
                        self.website_opacity_slider.setValue(web_op_val)
                    self.website_font_family = data.get("website_font_family", None)
                    self.website_font_style = data.get("website_font_style", "Regular")
                    raw_wc = data.get("website_color", None)
                    self.website_color = tuple(raw_wc) if isinstance(raw_wc, (list, tuple)) else raw_wc
                if hasattr(self, "intro_check"):
                    self.intro_check.setChecked(bool(data.get("intro_enabled", False)))
                    self.intro_dur_spin.setValue(float(data.get("intro_duration", 3.0) or 3.0))
                    _set_combo_case_insensitive(self.intro_anim_combo, data.get("intro_animation", "Fade in / out"))
                    self.preview_intro_btn.setText("Preview Intro Card")
                if hasattr(self, "sfx_check"):
                    self.sfx_check.setChecked(bool(data.get("transition_sfx_enabled", False)))
                    sfx_vol = int(float(data.get("transition_sfx_volume", 0.7) if data.get("transition_sfx_volume") is not None else 0.7) * 100)
                    self.sfx_vol_slider.setValue(sfx_vol)
                if hasattr(self, "resource_profile_combo") and "resource_profile" in data:
                    _set_combo_case_insensitive(self.resource_profile_combo, data["resource_profile"])
                if hasattr(self, "playlist_pos_combo") and "playlist_position" in data:
                    _set_combo_case_insensitive(self.playlist_pos_combo, data["playlist_position"])
                if hasattr(self, "playlist_cols_spin") and "playlist_columns" in data:
                    self.playlist_cols_spin.setValue(int(data["playlist_columns"]))
                if hasattr(self, "track_spacing_spin") and "playlist_row_spacing" in data:
                    self.track_spacing_spin.setValue(float(data["playlist_row_spacing"]))
                if hasattr(self, "col_spacing_spin") and "playlist_col_spacing" in data:
                    self.col_spacing_spin.setValue(int(data["playlist_col_spacing"]))
                if hasattr(self, "track_max_chars_spin") and "track_max_chars" in data:
                    self.track_max_chars_spin.setValue(int(data["track_max_chars"]))
                if hasattr(self, "playlist_bg_slider") and "playlist_bg_opacity" in data:
                    self.playlist_bg_slider.setValue(int(float(data["playlist_bg_opacity"]) * 100))
                if hasattr(self, "title_pos_combo") and "title_position" in data:
                    _set_combo_case_insensitive(self.title_pos_combo, data["title_position"])
                if hasattr(self, "title_show_check") and "title_show" in data:
                    self.title_show_check.setChecked(bool(data["title_show"]))
                self._update_title_spacing_enabled()
                if hasattr(self, "highlight_style_combo") and "highlight_style" in data:
                    _set_combo_case_insensitive(self.highlight_style_combo, data["highlight_style"])
                if "title_color" in data:
                    self.title_color = data["title_color"]
                    self._update_title_color_btn()
                if "track_color" in data:
                    self.track_color = data["track_color"]
                    self._update_track_color_btn()
                if "active_track_color" in data:
                    self.active_track_color = data["active_track_color"]
                if hasattr(self, "cursor_y_offset_spin") and "cursor_y_offset" in data:
                    self.cursor_y_offset_spin.setValue(int(data["cursor_y_offset"]))
                if hasattr(self, "highlight_y_offset_spin") and "highlight_y_offset" in data:
                    self.highlight_y_offset_spin.setValue(int(data["highlight_y_offset"]))
                if hasattr(self, "highlight_outline_spin") and "highlight_outline_width" in data:
                    self.highlight_outline_spin.setValue(int(data["highlight_outline_width"]))
                if hasattr(self, "highlight_corner_combo") and "highlight_corner_radius" in data:
                    rad = data["highlight_corner_radius"]
                    if rad == 0 or rad == "0":
                        self.highlight_corner_combo.setCurrentText("Square (Sharp)")
                    else:
                        self.highlight_corner_combo.setCurrentText("Rounded")
                if hasattr(self, "highlight_target_combo") and "highlight_target" in data:
                    tgt = str(data["highlight_target"]).lower().strip()
                    if tgt == "text" or "text" in tgt:
                        self.highlight_target_combo.setCurrentText("Surround Text")
                    else:
                        self.highlight_target_combo.setCurrentText("Full Row")
                if "highlight_color" in data:
                    self.highlight_color = data["highlight_color"]
                    self._update_highlight_color_btn()
                if hasattr(self, "highlight_opacity_slider") and "highlight_bg_opacity" in data:
                    self.highlight_opacity_slider.setValue(int(float(data["highlight_bg_opacity"]) * 100))
                if hasattr(self, "logo_cleanup_check") and "logo_cleanup_mode" in data:
                    self.logo_cleanup_check.setChecked(data["logo_cleanup_mode"] != "none")
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
                self._update_project_ui_indicators()
            finally:
                self._loading_project = False

            self._add_recent_project(path)
            self.status_label.setText(f"Project opened: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Could not open project", str(exc))
