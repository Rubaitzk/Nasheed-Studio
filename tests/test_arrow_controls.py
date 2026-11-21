"""
Unit and integration tests for Feature C: Consistent Arrow Controls.

Verifies:
1. All spinboxes standardize to keyboardTracking=False to avoid typing conflicts.
2. Arrow stepping (stepUp / stepDown) increments and decrements correctly.
3. Minimum and maximum limits are strictly enforced.
4. Float vs integer step sizes.
"""

import sys
import pytest
from PySide6.QtWidgets import QApplication, QSpinBox, QDoubleSpinBox

from src.ui.main_window import MainWindow
from tests.conftest import dispose_window


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture(scope="module")
def win(qapp):
    w = MainWindow()
    yield w
    dispose_window(w)


def test_spinbox_standardization_and_stepping(win):
    spin = win.cursor_size_spin
    assert not spin.keyboardTracking(), "keyboardTracking must be False"

    initial = spin.value()
    spin.stepUp()
    assert spin.value() == initial + spin.singleStep()

    spin.stepDown()
    assert spin.value() == initial


def test_spinbox_limits_enforced(win):
    spin = win.playlist_cols_spin
    # Range is 1 to 4
    spin.setValue(1)
    spin.stepDown()
    assert spin.value() == 1, "Spinbox exceeded minimum limit"

    spin.setValue(4)
    spin.stepUp()
    assert spin.value() == 4, "Spinbox exceeded maximum limit"


def test_double_spinbox_stepping(win):
    dspin = win.track_spacing_spin
    assert isinstance(dspin, QDoubleSpinBox)
    assert not dspin.keyboardTracking()

    initial = dspin.value()
    dspin.stepUp()
    assert abs(dspin.value() - (initial + dspin.singleStep())) < 1e-4


def test_visualizer_spinboxes_arrows(win):
    v_spin = win.visualizer_count_spin
    assert not v_spin.keyboardTracking()
    v_spin.setValue(32)
    v_spin.stepUp()
    assert v_spin.value() == 33
    v_spin.stepDown()
    assert v_spin.value() == 32
