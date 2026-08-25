import sys

from PySide6.QtWidgets import QApplication

from ui.pages.splash_screen import SplashScreen
from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    splash = SplashScreen()
    main_window = MainWindow()

    splash.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()