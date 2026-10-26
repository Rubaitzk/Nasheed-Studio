"""Global pytest configuration and safeguards against unhandled modal dialogs."""

import pytest
from PySide6.QtWidgets import QMessageBox, QApplication


def dispose_window(win):
    """
    Safely dispose of a MainWindow instance during test fixture teardown
    without triggering interactive close confirmation.
    """
    if win is None:
        return
    if hasattr(win, "_title_timer") and win._title_timer.isActive():
        win._title_timer.stop()
    if hasattr(win, "_preview_timer") and win._preview_timer.isActive():
        win._preview_timer.stop()
    if getattr(win, "_job", None) and win._job.is_running:
        win._job.cancel()
        win._job = None
    # Bypass interactive confirmation during fixture teardown
    win.closeEvent = lambda event: event.accept()
    win.close()
    win.deleteLater()
    app = QApplication.instance()
    if app:
        app.processEvents()


def _fail_on_unexpected_dialog(dialog_type: str, *args, **kwargs):
    title = args[1] if len(args) > 1 else kwargs.get("title", "")
    text = args[2] if len(args) > 2 else kwargs.get("text", "")
    pytest.fail(
        f"Unexpected interactive modal dialog: QMessageBox.{dialog_type}('{title}', '{text}') "
        f"was invoked without an explicit mock. Tests must explicitly mock or patch QMessageBox "
        f"when testing dialog interactions to avoid hanging automated runners."
    )


@pytest.fixture(autouse=True)
def guard_unexpected_modal_dialogs(monkeypatch):
    """
    Autouse safeguard that catches any unexpected modal dialog invocation
    and immediately fails the test with a clear, actionable diagnostic
    rather than blocking the runner on an OS prompt or silently masking defects.
    """
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: _fail_on_unexpected_dialog("information", *a, **kw))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: _fail_on_unexpected_dialog("warning", *a, **kw))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: _fail_on_unexpected_dialog("question", *a, **kw))
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **kw: _fail_on_unexpected_dialog("critical", *a, **kw))
    monkeypatch.setattr(QMessageBox, "exec", lambda self, *a, **kw: _fail_on_unexpected_dialog("exec", self.windowTitle(), self.text()))


@pytest.fixture(autouse=True)
def guard_workspace_qsettings():
    """Ensure no test leaks a temporary directory into persistent QSettings."""
    from PySide6.QtCore import QSettings
    from src.services.workspace_service import is_temp_or_obsolete_path
    settings = QSettings("NasheedStudio", "NasheedStudio")
    orig_ws = settings.value("workspace_root", None)
    orig_has_ws = settings.contains("workspace_root")
    yield
    cur_ws = settings.value("workspace_root", None)
    if is_temp_or_obsolete_path(cur_ws):
        if orig_has_ws and orig_ws and not is_temp_or_obsolete_path(orig_ws):
            settings.setValue("workspace_root", orig_ws)
        else:
            settings.remove("workspace_root")
