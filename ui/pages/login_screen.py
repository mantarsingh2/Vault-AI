from pathlib import Path

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from ui.fonts import figma_font, load_application_fonts


BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "ui" / "assets"


class LoginScreen(QWidget):

    DESIGN_W = 1440
    DESIGN_H = 1024
    create_new_vault = Signal()

    def __init__(self):
        super().__init__()

        load_application_fonts()

        self.setWindowTitle("Vault AI")
        self.setStyleSheet("background-color: #050B15;")

        self.user_icon = self.load_pixmap("login_plus_shield.png")
        self.lock_icon = self.load_pixmap("login_right.png")
        self.eye_icon = self.load_pixmap("login_eye.png")
        self.right_icon = self.load_pixmap("login_user.png")
        self.plus_shield_icon = self.load_pixmap("login_lock.png")
        self.protect_icon = self.load_pixmap("login_protect.png")
        self.divider = QSvgRenderer(str(ASSETS_DIR / "login_divider.svg"))
        self.password = ""
        self.password_visible = False
        self.password_focused = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def load_pixmap(self, filename):
        return QPixmap(str(ASSETS_DIR / filename))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform
        )

        scale = min(
            self.width() / self.DESIGN_W,
            self.height() / self.DESIGN_H,
        )
        canvas_x = (self.width() - self.DESIGN_W * scale) / 2
        canvas_y = (self.height() - self.DESIGN_H * scale) / 2

        painter.fillRect(self.rect(), "#050B15")
        painter.translate(canvas_x, canvas_y)
        painter.scale(scale, scale)

        painter.setPen(Qt.NoPen)
        painter.setBrush("#0C111F")
        painter.drawRoundedRect(352, 129, 735, 767, 37, 37)

        self.draw_header(painter)
        self.draw_password_field(painter)
        self.draw_unlock_button(painter)
        self.draw_divider(painter)
        self.draw_create_vault_card(painter)
        self.draw_information_card(painter)

        painter.end()

    def draw_header(self, painter):
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2E8DE7"))
        painter.setOpacity(0.12)
        painter.drawEllipse(670, 141, 99, 99)
        painter.setOpacity(1)
        painter.setPen(QPen(QColor("#2E8DE7"), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(678.75, 150.25, 81.5, 81.5))
        painter.drawPixmap(694, 161, 50, 60, self.user_icon)

        painter.setFont(figma_font("Inter", 40, QFont.Weight.DemiBold))
        painter.setPen(Qt.white)
        self.draw_centered_text(painter, 720, 295, "Welcome Back")

        painter.setFont(figma_font("Roboto", 16, QFont.Weight.Medium))
        painter.setPen("#CBD7E1")
        self.draw_centered_text(
            painter, 720, 335, "Unlock your secure vault to continue"
        )
        painter.restore()

    def draw_password_field(self, painter):
        painter.setFont(figma_font("Roboto", 16, QFont.Weight.Bold))
        painter.setPen(Qt.white)
        painter.drawText(414, 400, "Master Password")

        painter.setPen(QPen(QColor("#1E6CF7"), 1.5))
        painter.setBrush(QColor("#0B0F1C"))
        painter.drawRoundedRect(QRectF(415.25, 413.25, 608.5, 50.5), 6.25, 6.25)
        painter.drawPixmap(424, 429, 18, 18, self.lock_icon)

        painter.setFont(figma_font("Roboto", 14, QFont.Weight.Normal))
        painter.setPen("#CBD7E1")
        password_text = self.password if self.password_visible else "•" * len(self.password)
        painter.drawText(459, 445, password_text or "Enter your master password")
        painter.drawPixmap(996, 429, 18, 18, self.eye_icon)

    def draw_unlock_button(self, painter):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1E6CF7"))
        painter.drawRoundedRect(QRectF(414.5, 484.5, 610, 66), 7, 7)
        painter.drawPixmap(611, 507, 20, 20, self.lock_icon)

        painter.setFont(figma_font("Roboto", 20, QFont.Weight.Medium))
        painter.setPen(Qt.white)
        painter.drawText(641, 529, "UNLOCK VAULT")
        painter.drawPixmap(808, 507, 20, 20, self.right_icon)

    def draw_divider(self, painter):
        self.divider.render(painter, QRectF(414, 590, 287, 2))
        self.divider.render(painter, QRectF(737, 590, 287, 2))
        painter.setFont(figma_font("Inter", 15, QFont.Weight.Normal))
        painter.setPen("#CBD7E1")
        self.draw_centered_text(painter, 720, 596, "OR")

    def draw_create_vault_card(self, painter):
        painter.setPen(QPen(QColor("#232840"), 3))
        painter.setBrush(QColor("#0A1123"))
        painter.drawRoundedRect(QRectF(416, 632, 607, 104), 5.5, 5.5)
        painter.drawPixmap(424, 661, 45, 45, self.plus_shield_icon)

        painter.setFont(figma_font("Roboto", 16, QFont.Weight.Normal))
        painter.setPen("#CBD7E1")
        painter.drawText(479, 665, "New to Vault AI?")
        painter.setFont(figma_font("Roboto", 20, QFont.Weight.Medium))
        painter.setPen(Qt.white)
        painter.drawText(479, 699, "CREATE NEW VAULT")
        painter.drawPixmap(986, 681, 18, 18, self.right_icon)
        painter.setFont(figma_font("Inter", 15, QFont.Weight.Normal))
        painter.setPen("#CBD7E1")
        painter.drawText(479, 721, "Set up your secure vault for the first time")

    def draw_information_card(self, painter):
        painter.setPen(QPen(QColor("#232840"), 3))
        painter.setBrush(QColor("#101525"))
        painter.drawRoundedRect(QRectF(416, 770, 607, 103), 5.5, 5.5)
        painter.drawPixmap(424, 801, 40, 40, self.protect_icon)

        painter.setFont(figma_font("Roboto", 20, QFont.Weight.Medium))
        painter.setPen(Qt.white)
        painter.drawText(478, 806, "What happens next?")
        painter.setFont(figma_font("Inter", 15, QFont.Weight.Normal))
        painter.setPen("#CBD7E1")
        painter.drawText(
            478, 833,
            "After unlocking, Vault AI will automatically verify this device",
        )
        painter.drawText(
            478, 853, "and assess login risk to keep your data secure."
        )

    @staticmethod
    def draw_centered_text(painter, center_x, baseline_y, text):
        width = painter.fontMetrics().horizontalAdvance(text)
        painter.drawText(int(center_x - width / 2), baseline_y, text)

    def mousePressEvent(self, event):
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        x = (event.position().x() - (self.width() - self.DESIGN_W * scale) / 2) / scale
        y = (event.position().y() - (self.height() - self.DESIGN_H * scale) / 2) / scale

        if 414.5 <= x <= 1024.5 and 412.5 <= y <= 464.5:
            self.password_focused = True
            self.setFocus()
            if x >= 978:
                self.password_visible = not self.password_visible
            self.update()
        elif 414.5 <= x <= 1024.5 and 630.5 <= y <= 737.5:
            self.create_new_vault.emit()
        else:
            self.password_focused = False
            self.update()

        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if not self.password_focused:
            return super().keyPressEvent(event)

        if event.key() == Qt.Key.Key_Backspace:
            self.password = self.password[:-1]
        elif event.text() and event.text().isprintable():
            self.password += event.text()
        else:
            return super().keyPressEvent(event)

        self.update()
