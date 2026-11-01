import sys
import unittest
from PySide6.QtWidgets import QApplication, QSpinBox, QSlider, QComboBox
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QWheelEvent, QKeyEvent

from src.ui.main_window import MainWindow
from tests.conftest import dispose_window

_app = None

def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestInspectorWheel(unittest.TestCase):
    def setUp(self):
        self.app = _get_app()
        self.win = MainWindow()
        self.win.resize(1280, 720)
        self.win.show()
        self.app.processEvents()

    def tearDown(self):
        dispose_window(self.win)

    def test_passive_wheel_does_not_change_spinbox_and_scrolls_panel(self):
        win = self.win
        win.inspector_tabs.setCurrentIndex(0)
        self.app.processEvents()

        scroll_area = win.inspector_tabs.widget(0)
        vsb = scroll_area.verticalScrollBar()
        target_sb = win.playlist_cols_spin

        # Clear focus to container
        scroll_area.widget().setFocus()
        self.app.processEvents()
        self.assertFalse(target_sb.hasFocus())

        val_before = target_sb.value()
        scroll_before = vsb.value()

        # Passive wheel event down over target_sb
        evt_down = QWheelEvent(
            QPoint(10, 10), QPoint(10, 10), QPoint(), QPoint(0, -120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False
        )
        self.app.sendEvent(target_sb, evt_down)
        self.app.processEvents()

        # Value must remain strictly unchanged!
        self.assertEqual(target_sb.value(), val_before)
        # Scroll area must have scrolled down
        self.assertGreater(vsb.value(), scroll_before)

    def test_focused_wheel_adjusts_spinbox_value(self):
        win = self.win
        win.inspector_tabs.setCurrentIndex(0)
        self.app.processEvents()

        target_sb = win.playlist_cols_spin
        target_sb.setFocus()
        self.app.processEvents()
        self.assertTrue(target_sb.hasFocus() or any(c.hasFocus() for c in target_sb.findChildren(target_sb.__class__)))

        val_before = target_sb.value()
        scroll_area = win.inspector_tabs.widget(0)
        vsb = scroll_area.verticalScrollBar()
        scroll_before = vsb.value()

        # Wheel event up while focused
        evt_up = QWheelEvent(
            QPoint(10, 10), QPoint(10, 10), QPoint(), QPoint(0, 120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False
        )
        self.app.sendEvent(target_sb, evt_up)
        self.app.processEvents()

        # Focused control adjusts value
        self.assertEqual(target_sb.value(), val_before + 1)
        # Scroll area position did not change
        self.assertEqual(vsb.value(), scroll_before)

    def test_passive_wheel_does_not_change_combobox(self):
        win = self.win
        win.inspector_tabs.setCurrentIndex(0)
        self.app.processEvents()

        combo = win.template_combo
        scroll_area = win.inspector_tabs.widget(0)
        scroll_area.widget().setFocus()
        self.app.processEvents()
        self.assertFalse(combo.hasFocus())

        idx_before = combo.currentIndex()
        evt_down = QWheelEvent(
            QPoint(10, 10), QPoint(10, 10), QPoint(), QPoint(0, -120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False
        )
        self.app.sendEvent(combo, evt_down)
        self.app.processEvents()

        self.assertEqual(combo.currentIndex(), idx_before)

    def test_keyboard_input_preserved(self):
        win = self.win
        win.inspector_tabs.setCurrentIndex(0)
        self.app.processEvents()

        target_sb = win.playlist_cols_spin
        target_sb.setFocus()
        target_sb.setValue(2)
        self.app.processEvents()

        # Simulate keyboard up arrow
        key_evt = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(target_sb, key_evt)
        self.app.processEvents()

        self.assertEqual(target_sb.value(), 3)
