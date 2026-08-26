from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ui.fonts import figma_font, load_application_fonts


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


class CreateVaultScreen(QWidget):
    DESIGN_W = 1440
    DESIGN_H = 1024

    def __init__(self):
        super().__init__()
        load_application_fonts()
        self.setWindowTitle("Vault AI")
        self.setStyleSheet("background-color: #050B15;")
        self.plus = self.pixmap("create_3.png")
        self.lock = self.pixmap("create_4.png")
        self.eye = self.pixmap("create_2.png")
        self.check = self.pixmap("create_5.png")
        self.right = self.pixmap("create_1.png")
        self.info = self.pixmap("create_6.png")

    def pixmap(self, name):
        return QPixmap(str(ASSETS_DIR / name))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        s = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        p.fillRect(self.rect(), "#050B15")
        p.translate((self.width() - self.DESIGN_W * s) / 2, (self.height() - self.DESIGN_H * s) / 2)
        p.scale(s, s)
        p.setPen(Qt.NoPen); p.setBrush("#0C111F"); p.drawRoundedRect(353, 54, 735, 917, 37, 37)
        self.header(p); self.passwords(p); self.strength(p); self.rules(p); self.create_button(p); self.notice(p)
        p.end()

    def header(self, p):
        p.setPen(Qt.NoPen); p.setBrush(QColor("#2E8DE7")); p.setOpacity(.12); p.drawEllipse(671, 80, 99, 99); p.setOpacity(1)
        p.setPen(QPen(QColor("#2E8DE7"), 1.5)); p.setBrush(Qt.NoBrush); p.drawEllipse(QRectF(679.75, 89.25, 81.5, 81.5)); p.drawPixmap(696, 100, 50, 60, self.plus)
        p.setFont(figma_font("Inter", 40, QFont.Weight.DemiBold)); p.setPen(Qt.white); self.center(p, 720, 234, "Create Your Vault")
        p.setFont(figma_font("Roboto", 16, QFont.Weight.Medium)); p.setPen("#CBD7E1"); self.center(p, 720, 274, "Set a strong master password to protect your vault.")

    def field(self, p, y, label, placeholder, helper=""):
        p.setFont(figma_font("Roboto", 16, QFont.Weight.Bold)); p.setPen(Qt.white); p.drawText(415, y, label)
        p.setPen(QPen(QColor("#1E6CF7"), 1.5)); p.setBrush("#0B0F1C"); p.drawRoundedRect(QRectF(415.25, y + 13.25, 608.5, 50.5), 6.25, 6.25)
        p.drawPixmap(425, y + 29, 18, 18, self.lock); p.setFont(figma_font("Roboto", 14, QFont.Weight.Normal)); p.setPen("#CBD7E1"); p.drawText(459, y + 46, placeholder); p.drawPixmap(996, y + 29, 18, 18, self.eye)
        if helper:
            p.setFont(figma_font("Inter", 15, QFont.Weight.Normal)); p.drawText(415, y + 84, helper)

    def passwords(self, p):
        self.field(p, 320, "Master Password", "Enter your master password", "Must be at least 8 characters long.")
        self.field(p, 456, "Confirm Master Password", "Confirm your master password")

    def strength(self, p):
        p.setFont(figma_font("Roboto", 16, QFont.Weight.Medium)); p.setPen("#CBD7E1"); p.drawText(415, 552, "Password Strength")
        p.setPen(Qt.NoPen); p.setBrush("#1B314C"); p.drawRoundedRect(415, 567, 609, 8, 5, 5); p.setBrush("#FF4D4F"); p.drawRoundedRect(415, 567, 8, 8, 5, 5)

    def rules(self, p):
        p.setPen(QPen(QColor("#262C41"), 3)); p.setBrush("#080E1E"); p.drawRoundedRect(QRectF(416, 599, 607, 105), 5.5, 5.5)
        labels = [(435, 627, "At least one lowercase letter"), (772, 627, "At least one number"), (435, 671, "At least one special charcater"), (772, 671, "At least one uppercase letter")]
        p.setFont(figma_font("Roboto", 16, QFont.Weight.Medium)); p.setPen("#CBD7E1")
        for x, y, text in labels: p.drawPixmap(x, y - 16, 16, 16, self.check); p.drawText(x + 26, y, text)

    def create_button(self, p):
        p.setPen(Qt.NoPen); p.setBrush("#1E6CF7"); p.drawRoundedRect(415, 724, 610, 66, 7, 7); p.drawPixmap(574, 747, 20, 20, self.lock)
        p.setFont(figma_font("Roboto", 20, QFont.Weight.Medium)); p.setPen(Qt.white); p.drawText(604, 769, "CREATE SECURE VAULT"); p.drawPixmap(845, 747, 20, 20, self.right)

    def notice(self, p):
        p.setPen(QPen(QColor("#232840"), 3)); p.setBrush("#101525"); p.drawRoundedRect(QRectF(416, 821, 607, 103), 5.5, 5.5); p.drawPixmap(426, 854, 40, 40, self.info)
        p.setFont(figma_font("Roboto", 20, QFont.Weight.Medium)); p.setPen(Qt.white); p.drawText(480, 859, "Important to remember")
        p.setFont(figma_font("Inter", 15, QFont.Weight.Normal)); p.setPen("#CBD7E1"); p.drawText(480, 886, "There is no recovery option. If your forgot your master password,"); p.drawText(480, 906, "you will lose the access to your Vault permanently.")

    @staticmethod
    def center(p, x, y, text):
        p.drawText(int(x - p.fontMetrics().horizontalAdvance(text) / 2), y, text)
