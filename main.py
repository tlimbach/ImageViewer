import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication
)

from core.control_window import ControlWindow
from core.display_window import DisplayWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    dummy_folder = "/Users/thorsten/Datensenke/oldschool"  # Platzhalter, wird durch settings.json ggf. überschrieben
    display = DisplayWindow(dummy_folder)
    control = ControlWindow(display)

    def quit_app():
        QApplication.quit()
        QTimer.singleShot(500, lambda: sys.exit(0))

    display.destroyed.connect(quit_app)
    control.destroyed.connect(quit_app)

    display.show()

    from PyQt5.QtWidgets import QDesktopWidget
    desktop = QDesktopWidget()
    screen_count = desktop.screenCount()

    if screen_count > 1:
        second_screen_geometry = desktop.screenGeometry(1)
    else:
        second_screen_geometry = desktop.availableGeometry()

    control.setGeometry(second_screen_geometry)
    control.showFullScreen()

    sys.exit(app.exec_())
