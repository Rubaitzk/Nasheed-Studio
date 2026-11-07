from pathlib import Path

from PIL import Image
from PySide6.QtWidgets import QApplication, QLabel
import pytest

from src.ui import branding


@pytest.fixture(scope="module", autouse=True)
def qapplication():
    return QApplication.instance() or QApplication([])


def test_application_icon_loads_from_source_tree(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    module_dir = source_root / "src" / "ui"
    module_dir.mkdir(parents=True)
    icon_path = source_root / "assets" / "app_icon.png"
    icon_path.parent.mkdir()
    Image.new("RGBA", (32, 32), (40, 120, 80, 255)).save(icon_path)
    monkeypatch.setattr(branding, "__file__", str(module_dir / "branding.py"))

    assert branding.application_icon_path() == icon_path
    assert not branding.application_icon().isNull()


def test_application_icon_is_optional_when_asset_is_missing(tmp_path, monkeypatch):
    module_dir = tmp_path / "source" / "src" / "ui"
    module_dir.mkdir(parents=True)
    monkeypatch.setattr(branding, "__file__", str(module_dir / "branding.py"))

    assert branding.application_icon_path() is None
    assert branding.application_icon().isNull()


def test_application_icon_resolves_from_frozen_bundle(tmp_path, monkeypatch):
    bundle_dir = tmp_path / "release with spaces" / "NCN Studio"
    internal_dir = bundle_dir / "_internal"
    icon_path = internal_dir / "assets" / "app_icon.png"
    icon_path.parent.mkdir(parents=True)
    Image.new("RGBA", (32, 32), (40, 120, 80, 255)).save(icon_path)
    module_dir = internal_dir / "src" / "ui"
    module_dir.mkdir(parents=True)

    monkeypatch.setattr(branding, "__file__", str(module_dir / "branding.py"))
    monkeypatch.setattr(branding.sys, "frozen", True, raising=False)
    monkeypatch.setattr(branding.sys, "executable", str(bundle_dir / "NCN Studio.exe"))
    monkeypatch.setattr(branding.sys, "_MEIPASS", str(internal_dir), raising=False)

    assert branding.application_icon_path() == icon_path
    assert not branding.application_icon().isNull()


def test_main_window_shows_ncn_studio_branding():
    app = QApplication.instance() or QApplication([])
    from src.ui.main_window import MainWindow

    window = MainWindow()
    try:
        assert window.windowTitle().startswith("NCN Studio")
        assert window.findChild(QLabel, "app_title").text() == "NCN Studio"
        help_menu = next(action.menu() for action in window.menuBar().actions() if action.text() == "Help")
        assert any(action.text() == "About NCN Studio" for action in help_menu.actions())
        assert "Nasheed Studio" not in window.windowTitle()
    finally:
        window.close()
