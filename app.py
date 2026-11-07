import sys
from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.ui.branding import application_icon


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("NCN Studio")
    icon = application_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    window = MainWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
