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
