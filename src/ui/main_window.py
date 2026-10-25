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

from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer, QSettings
from PySide6.QtGui import QPixmap, QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QListWidget, QListWidgetItem, QLineEdit, QComboBox, QGroupBox,
    QFormLayout, QSplitter, QMessageBox, QProgressBar, QFrame, QAbstractItemView,
    QToolButton, QInputDialog, QSizePolicy, QSpinBox,
)
from PIL import Image

from src.services.media_probe import get_duration
from src.services.render_service import build_render_command, RESOLUTIONS
from src.services.export_job import ExportJob, STATE_RUNNING


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
        self.tracks: list[dict] = []
        self.project_path = ""
        self._is_dirty = False
        self._last_saved_snapshot: Optional[dict] = None
        self._loading_project = False
        self._recent_menu = None
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

        al.addWidget(self.background_label)
        al.addWidget(self.background_btn)
        al.addSpacing(5)
        al.addWidget(self.logo_label)
        al.addWidget(self.logo_btn)
        left_l.addWidget(assets)

        playlist_box = QGroupBox("PLAYLIST")
        pl = QVBoxLayout(playlist_box)
        title_form = QFormLayout()
        self.collection_title = QLineEdit("Abu Ali Nasheeds Collection")
        self.collection_title.textChanged.connect(self._on_title_changed)
        self.collection_title.editingFinished.connect(self._flush_preview)
        title_form.addRow("Collection title", self.collection_title)
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

        # -- Right panel: design + export --
        right = QWidget()
        right.setMinimumWidth(240)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 0, 0)
        rl.setSpacing(10)

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

        splitter.addWidget(right)
        splitter.setSizes([330, 650, 310])
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
        return {
            "version": 1,
            "collection_title": self.collection_title.text().strip() or "Nasheed Collection",
            "background": self.background_path,
            "logo": self.logo_path,
            "tracks": self.tracks,
            "template": self.template_combo.currentText(),
            "resolution": self.resolution_combo.currentText(),
            "indicator_mode": self._mode_from_combo(),
            "cursor_path": self.cursor_path,
            "cursor_size": self.cursor_size_spin.value(),
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
    # Preview
    # ------------------------------------------------------------------

    def _on_title_changed(self, text: str) -> None:
        self._mark_dirty()
        self._schedule_preview(300)

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
        if self._preview_timer.isActive():
            self._preview_timer.stop()
            self._refresh_preview()

    def _update_resolution_badge(self) -> None:
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
                    collection_title=self.collection_title.text().strip() or "Nasheed Collection",
                    track_titles=titles,
                    template=self.template_combo.currentText(),
                    out_dir=tmp,
                    indicator_mode=self._mode_from_combo(),
                    cursor_path=self.cursor_path or None,
                    cursor_size=self.cursor_size_spin.value(),
                    preview_only_first_overlay=True,
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
        if self._job and self._job.is_running:
            answer = QMessageBox.question(
                self, "Export in progress",
                "An export is running. Cancel it and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._job.cancel()
            # Wait briefly for the worker thread to clean up.
            self._job.join(timeout=5.0)
        event.accept()

    # ------------------------------------------------------------------
    # Project persistence & dirty state
    # ------------------------------------------------------------------

    def _mark_dirty(self, *args) -> None:
        if not self._loading_project:
            self._is_dirty = True

    def has_unsaved_changes(self) -> bool:
        if self._is_dirty:
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
            or (self.collection_title.text().strip() != default_title)
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
            self.background_path = ""
            self.logo_path = ""
            self.cursor_path = ""
            self.tracks = []
            self.project_path = ""
            self._set_asset_label(self.background_label, "")
            self.background_label.setText("No background selected")
            self._set_asset_label(self.logo_label, "")
            self.logo_label.setText("No logo selected")
            self._set_asset_label(self.cursor_label, "")
            self.cursor_label.setText("Default arrow cursor")
            self.collection_title.setText("Abu Ali Nasheeds Collection")
            self.template_combo.setCurrentText("Cinematic")
            self.resolution_combo.setCurrentIndex(0)
            self._set_combo_from_mode("both")
            self.cursor_size_spin.setValue(32)
            self.output_edit.setText(str(Path.home() / "Videos" / "nasheed_collection.mp4"))
            self._refresh_tracks()
            self._refresh_preview()
            self._is_dirty = False
            self._last_saved_snapshot = None
            self.status_label.setText("New project ready.")
        finally:
            self._loading_project = False

    def save_project(self) -> None:
        if not self.project_path:
            return self.save_project_as()
        self._write_project(self.project_path)

    def save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save project",
            self.project_path or str(Path.home() / "nasheed_project.json"),
            "Nasheed Studio project (*.json)"
        )
        if path:
            if not path.lower().endswith(".json"):
                path += ".json"
            self._write_project(path)

    def _write_project(self, path: str) -> None:
        try:
            payload = json.dumps(self._project(), indent=2)
            Path(path).write_text(payload, encoding="utf-8")
            self.project_path = path
            self._is_dirty = False
            self._last_saved_snapshot = self._project()
            self._add_recent_project(path)
            self.status_label.setText(f"Project saved: {path}")
        except Exception as exc:
            # Failed save preserves dirty state
            QMessageBox.critical(self, "Save failed", str(exc))

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
                self.background_path = data.get("background", "")
                self.logo_path = data.get("logo", "")
                self.cursor_path = data.get("cursor_path", "")
                self.tracks = data.get("tracks", [])
                self.collection_title.setText(data.get("collection_title", "Nasheed Collection"))
                self.template_combo.setCurrentText(data.get("template", "Cinematic"))
                self.resolution_combo.setCurrentText(data.get("resolution", "1080p · Full HD"))
                self._set_combo_from_mode(data.get("indicator_mode", "both"))
                self.cursor_size_spin.setValue(int(data.get("cursor_size", 32) or 32))
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
