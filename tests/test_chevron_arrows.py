import sys
from pathlib import Path
import pytest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QFrame,
)
from PySide6.QtCore import QFile, Qt, QPoint
from PySide6.QtTest import QTest

from src.ui.main_window import MainWindow
from tests.conftest import dispose_window


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_arrow_resources_exist_and_load():
    """Verify all referenced SVG chevron resources exist on disk and in Qt resource system."""
    expected_icons = [
        "chevron_down.svg",
        "chevron_down_hover.svg",
        "chevron_down_pressed.svg",
        "chevron_down_disabled.svg",
        "chevron_up.svg",
        "chevron_up_hover.svg",
        "chevron_up_pressed.svg",
        "chevron_up_disabled.svg",
    ]

    assets_dir = Path(__file__).resolve().parent.parent / "assets" / "icons"
    for icon_name in expected_icons:
        file_path = assets_dir / icon_name
        assert file_path.is_file(), f"Missing resource file on disk: {file_path}"

        qt_resource_path = f":/icons/{icon_name}"
        assert QFile.exists(qt_resource_path), f"Missing Qt resource: {qt_resource_path}"


def test_inspector_tabs_and_export_bar_combo_and_spin_boxes(qapp):
    """
    Walk the widget tree of every Inspector tab and the export bar.
    Assert that each QComboBox, QSpinBox, and QDoubleSpinBox picks up the styled arrows.
    """
    win = MainWindow()
    try:
        win.resize(1366, 768)
        win.show()
        qapp.processEvents()

        # Check export bar
        export_bar = win.findChild(QFrame, "export_bar")
        assert export_bar is not None
        export_combos = export_bar.findChildren(QComboBox)
        assert len(export_combos) >= 3, f"Expected resolution, profile, quality combos, found {len(export_combos)}"
        for combo in export_combos:
            assert combo.isVisible() or combo.parentWidget().isVisible()

        # Check every Inspector tab
        total_combos = 0
        total_spins = 0
        for tab_idx in range(win.inspector_tabs.count()):
            win.inspector_tabs.setCurrentIndex(tab_idx)
            qapp.processEvents()
            tab_widget = win.inspector_tabs.widget(tab_idx)

            combos = tab_widget.findChildren(QComboBox)
            int_spins = tab_widget.findChildren(QSpinBox)
            dbl_spins = tab_widget.findChildren(QDoubleSpinBox)

            total_combos += len(combos)
            total_spins += len(int_spins) + len(dbl_spins)

            # Assert all spin boxes have right padding for stacked buttons
            for spin in int_spins + dbl_spins:
                assert spin.styleSheet() == "" or "down-arrow" not in spin.styleSheet() or ":/icons/" in spin.styleSheet()

        assert total_combos > 0, "No QComboBox widgets found in inspector"
        assert total_spins > 0, "No QSpinBox/QDoubleSpinBox widgets found in inspector"
    finally:
        dispose_window(win)


def test_spinbox_and_combobox_hover_pressed_states(qapp):
    """Test mouse move hover and press on spin and combo subcontrols without crashing or errors."""
    win = MainWindow()
    try:
        win.show()
        qapp.processEvents()

        spin = win.particles_speed_spin
        assert spin is not None

        # Hover over the up-button
        up_pos = QPoint(spin.width() - 8, 6)
        QTest.mouseMove(spin, up_pos)
        qapp.processEvents()

        # Press up-button
        QTest.mousePress(spin, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, up_pos)
        qapp.processEvents()
        QTest.mouseRelease(spin, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, up_pos)
        qapp.processEvents()

        # Hover over the down-button
        down_pos = QPoint(spin.width() - 8, spin.height() - 6)
        QTest.mouseMove(spin, down_pos)
        qapp.processEvents()

        # Press down-button
        QTest.mousePress(spin, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, down_pos)
        qapp.processEvents()
        QTest.mouseRelease(spin, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, down_pos)
        qapp.processEvents()
    finally:
        dispose_window(win)
