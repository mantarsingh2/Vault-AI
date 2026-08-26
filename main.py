import sys

from PySide6.QtWidgets import QApplication

from ui.pages.splash_screen import SplashScreen
from ui.pages.login_screen import LoginScreen
from ui.pages.create_vault_screen import CreateVaultScreen


def main():
    app = QApplication(sys.argv)

    splash = SplashScreen()
    login_screen = LoginScreen()
    create_vault_screen = CreateVaultScreen()

    def show_login():
        splash.close()
        login_screen.resize(splash.size())
        login_screen.show()

    splash.get_started.connect(show_login)

    def show_create_vault():
        login_screen.close()
        create_vault_screen.resize(login_screen.size())
        create_vault_screen.show()

    login_screen.create_new_vault.connect(show_create_vault)

    splash.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
