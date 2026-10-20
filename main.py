"""SIF Viewer desktop entry point. Optionally pass one file path."""

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    if sys.platform == "win32":
        # Keep the viewer's taskbar identity separate from Python when run from source.
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ORI.SIFViewer")
    app = QApplication(sys.argv)
    app.setApplicationName("SIF Viewer")
    app.setApplicationVersion("1.4.6")
    app.setOrganizationName("ORI")
    icon = QIcon(str(Path(__file__).resolve().parent / "assets" / "app.ico"))
    app.setWindowIcon(icon)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()
    QTimer.singleShot(0, window.check_for_updates)
    if len(sys.argv) > 1:
        QTimer.singleShot(0, lambda: window.open_path(sys.argv[1]))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
