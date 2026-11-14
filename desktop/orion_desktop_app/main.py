import os
import sys
import ctypes

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from browser_window import OrionDesktopWindow


def _resource_path(relative):
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative)


def main():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "OrionERP.Desktop.1.0"
        )
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Orion ERP Desktop")
    app.setOrganizationName("Orion ERP")

    icon_path = _resource_path(os.path.join("assets", "icon.ico"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = OrionDesktopWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
