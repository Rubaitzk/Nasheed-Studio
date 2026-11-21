"""
Searchable font combo box widget with substring filtering, QCompleter integration,
and safe fallback protection.
"""

from __future__ import annotations

from typing import List, Optional
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import QComboBox, QCompleter, QLineEdit


class SearchableFontComboBox(QComboBox):
    """
    An editable QComboBox tailored for font selection with instant substring searching,
    live autocomplete, and reversion to the last valid selection if an invalid font is typed.
    """

    def __init__(self, parent=None, placeholder: str = "Search font…"):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(6)

        le = self.lineEdit()
        if le:
            le.setPlaceholderText(placeholder)
            le.setClearButtonEnabled(True)
            le.editingFinished.connect(self._on_editing_finished)

        self._completer = QCompleter(self.model(), self)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(self._completer)

        self._last_valid_text = "Segoe UI"
        self.currentIndexChanged.connect(self._on_index_changed)

    def addItems(self, texts) -> None:
        super().addItems(texts)
        if hasattr(self, "_completer"):
            self._completer.setModel(self.model())

    def clear(self) -> None:
        super().clear()
        if hasattr(self, "_completer"):
            self._completer.setModel(self.model())

    def _on_index_changed(self, index: int) -> None:
        if index >= 0:
            txt = self.itemText(index)
            if txt:
                self._last_valid_text = txt

    def _on_editing_finished(self) -> None:
        """Validate entered font name. If match found, select it; otherwise revert to last valid."""
        raw_text = self.currentText().strip()
        if not raw_text:
            self.setCurrentText(self._last_valid_text)
            return

        # Check exact or case-insensitive match
        match_idx = -1
        for i in range(self.count()):
            item_text = self.itemText(i)
            if item_text.lower() == raw_text.lower():
                match_idx = i
                break

        if match_idx >= 0:
            self.setCurrentIndex(match_idx)
            self._last_valid_text = self.itemText(match_idx)
        else:
            # Check substring match
            found = False
            for i in range(self.count()):
                if raw_text.lower() in self.itemText(i).lower():
                    self.setCurrentIndex(i)
                    self._last_valid_text = self.itemText(i)
                    found = True
                    break
            if not found:
                # Revert to last valid font
                self.setCurrentText(self._last_valid_text)

    def set_font_families(self, families: List[str], current: Optional[str] = None) -> None:
        """Populate font items and preserve or apply initial font selection."""
        self.blockSignals(True)
        self.clear()
        self.addItems(families)
        # Update completer model
        self._completer.setModel(self.model())

        target = current or self._last_valid_text or "Segoe UI"
        target_idx = -1
        for i in range(self.count()):
            if self.itemText(i).lower() == target.lower():
                target_idx = i
                break

        if target_idx >= 0:
            self.setCurrentIndex(target_idx)
            self._last_valid_text = self.itemText(target_idx)
        elif self.count() > 0:
            self.setCurrentIndex(0)
            self._last_valid_text = self.itemText(0)

        self.blockSignals(False)
