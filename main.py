import sys

from PySide6.QtWidgets import QApplication

from database import initialize_database
from ui.pages.create_vault_screen import CreateVaultScreen
from ui.pages.dashboard_screen import DashboardScreen
from ui.pages.device_security_screen import DeviceSecurityScreen
from ui.pages.device_verification_screen import DeviceVerificationScreen
from ui.pages.login_risk_screen import LoginRiskScreen
from ui.pages.login_screen import LoginScreen
from ui.pages.splash_screen import SplashScreen


def main():
    initialize_database()
    app = QApplication(sys.argv)

    splash = SplashScreen()
    login_screen = LoginScreen()
    create_vault_screen = CreateVaultScreen()
    device_security_screen = DeviceSecurityScreen()
    device_verification_screen = DeviceVerificationScreen()
    login_risk_screen = LoginRiskScreen()
    dashboard_screen = DashboardScreen()

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

    def show_device_verification():
        login_screen.close()
        device_verification_screen.resize(login_screen.size())
        device_verification_screen.show()

    login_screen.unlocked.connect(show_device_verification)

    def show_login_risk(device_risk=False):
        device_verification_screen.close()
        login_risk_screen.set_risk_level(device_risk)
        login_risk_screen.resize(device_verification_screen.size())
        login_risk_screen.show()

    def show_dashboard_from_risk(_risk_high=False):
        # 2FA temporarily removed — always proceed directly to dashboard.
        login_risk_screen.close()
        dashboard_screen.reload_sessions()
        dashboard_screen.reload_messages()
        dashboard_screen.resize(login_risk_screen.size())
        dashboard_screen.show()

    device_verification_screen.risk_assessed.connect(show_login_risk)
    login_risk_screen.risk_complete.connect(show_dashboard_from_risk)

    def show_login_from_dashboard():
        dashboard_screen.close()
        login_screen.password = ""
        login_screen.error_message = ""
        login_screen.resize(splash.size())
        login_screen.show()

    dashboard_screen.logged_out.connect(show_login_from_dashboard)

    def show_device_security():
        create_vault_screen.close()
        device_security_screen.resize(create_vault_screen.size())
        device_security_screen.show()

    create_vault_screen.vault_created.connect(show_device_security)

    def show_dashboard_from_device():
        device_security_screen.close()
        dashboard_screen.reload_sessions()
        dashboard_screen.reload_messages()
        dashboard_screen.resize(device_security_screen.size())
        dashboard_screen.show()

    device_security_screen.device_key_generated.connect(show_dashboard_from_device)

    splash.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
