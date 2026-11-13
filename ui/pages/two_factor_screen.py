import hashlib
import hmac
import secrets
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from ui.fonts import figma_font, load_application_fonts

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


class TwoFactorScreen(QWidget):
    DESIGN_W = 1440
    DESIGN_H = 1024
    verified = Signal()

    def __init__(self):
        super().__init__()
        load_application_fonts()
        self.setWindowTitle("Vault AI")
        self.setStyleSheet("background-color: #050B15;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.renderer = QSvgRenderer(str(ASSETS_DIR / "two_factor_reference.svg"))
        self.header_icon = QPixmap(str(ASSETS_DIR / "two_factor_embedded_0.png"))
        self.info_icon = QPixmap(str(ASSETS_DIR / "two_factor_embedded_1.png"))
        self.input_icon = QPixmap(str(ASSETS_DIR / "two_factor_embedded_2.png"))
        self.clock_icon = QPixmap(str(ASSETS_DIR / "two_factor_embedded_3.png"))
        self.button_icon = QPixmap(str(ASSETS_DIR / "two_factor_embedded_4.png"))
        self.right_icon = QPixmap(str(ASSETS_DIR / "two_factor_embedded_5.png"))
        self.why_icon = QPixmap(str(ASSETS_DIR / "two_factor_embedded_6.png"))
        self.why_art = QPixmap(str(ASSETS_DIR / "two_factor_embedded_7.png"))
        self.code = ""
        self.code_cursor = 0
        self.focused = False
        self.error_message = ""
        self.secret = secrets.token_bytes(20)
        self.seconds_left = 30 - (int(time.time()) % 30)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(1000)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        ox = (self.width() - self.DESIGN_W * scale) / 2
        oy = (self.height() - self.DESIGN_H * scale) / 2
        painter.fillRect(self.rect(), "#050B15")
        painter.translate(ox, oy)
        painter.scale(scale, scale)
        self.renderer.render(painter, QRectF(0, 0, self.DESIGN_W, self.DESIGN_H))
        # The reference contains a non-functional static timer label. Remove
        # it instead of presenting a countdown that does not update.
        painter.setPen(Qt.NoPen)
        painter.setBrush("#0C111F")
        painter.drawRect(QRectF(410, 588, 625, 38))
        # QSvgRenderer cannot resolve the embedded Figma image patterns in
        # this export, so place the matching local exports at their original
        # Figma coordinates.
        painter.drawPixmap(695, 88, 50, 60, self.header_icon)
        painter.drawPixmap(425, 350, 40, 40, self.info_icon)
        painter.drawPixmap(425, 530, 40, 40, self.input_icon)
        painter.drawPixmap(588, 661, 22, 22, self.button_icon)
        painter.drawPixmap(832, 662, 20, 20, self.right_icon)
        painter.drawPixmap(404, 827, 40, 40, self.why_icon)
        painter.drawPixmap(877, 794, 160, 107, self.why_art)
        if self.focused:
            painter.setPen(QPen(QColor("#2E8DE7"), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(414.5, 514, 612, 67), 8, 8)
        painter.setFont(figma_font("Roboto", 20, QFont.Weight.Medium))
        painter.setPen("#F8F6F9")
        for index, digit in enumerate(self.code):
            painter.drawText(512 + index * 64, 564, digit)
        if self.focused:
            caret_x = 505 + self.code_cursor * 64
            painter.setPen(QPen(QColor("#F8F6F9"), 1.5))
            painter.drawLine(caret_x, 549, caret_x, 568)
        painter.drawPixmap(415, 596, 16, 16, self.clock_icon)
        painter.setFont(figma_font("Inter", 15, QFont.Weight.Normal))
        painter.setPen("#CBD7E1")
        painter.drawText(437, 609, f"Code changes every {self.seconds_left:02d} seconds")
        if self.error_message:
            painter.setFont(figma_font("Inter", 13, QFont.Weight.Normal))
            painter.setPen("#FF4D4F")
            painter.drawText(415, 630, self.error_message)
        painter.end()

    def mousePressEvent(self, event):
        x, y = self.design_position(event.position())
        if 415 <= x <= 1025 and 639 <= y <= 705:
            self.verify_code()
        elif 415 <= x <= 1025 and 514 <= y <= 581:
            self.focused = True
            self.setFocus()
            self.code_cursor = min(6, max(0, round((x - 505) / 64)))
            self.update()
        else:
            self.focused = False
            self.update()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.verify_code()
            return
        if not self.focused:
            return super().keyPressEvent(event)
        if event.key() == Qt.Key.Key_Left:
            self.code_cursor = max(0, self.code_cursor - 1)
        elif event.key() == Qt.Key.Key_Right:
            self.code_cursor = min(len(self.code), self.code_cursor + 1)
        elif event.key() == Qt.Key.Key_Home:
            self.code_cursor = 0
        elif event.key() == Qt.Key.Key_End:
            self.code_cursor = len(self.code)
        elif event.key() == Qt.Key.Key_Backspace:
            if self.code_cursor:
                self.code = self.code[:self.code_cursor - 1] + self.code[self.code_cursor:]
                self.code_cursor -= 1
        elif event.key() == Qt.Key.Key_Delete:
            self.code = self.code[:self.code_cursor] + self.code[self.code_cursor + 1:]
        elif event.text().isdigit() and len(self.code) < 6:
            self.code = self.code[:self.code_cursor] + event.text() + self.code[self.code_cursor:]
            self.code_cursor += 1
        else:
            return super().keyPressEvent(event)
        self.error_message = ""
        self.update()

    def design_position(self, point):
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        ox = (self.width() - self.DESIGN_W * scale) / 2
        oy = (self.height() - self.DESIGN_H * scale) / 2
        return ((point.x() - ox) / scale, (point.y() - oy) / scale)

    def update_timer(self):
        self.seconds_left = 30 - (int(time.time()) % 30)
        self.update()

    def current_code(self):
        counter = int(time.time()) // 30
        digest = hmac.new(self.secret, counter.to_bytes(8, "big"), hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        number = int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF
        return f"{number % 1000000:06d}"

    def verify_code(self):
        if len(self.code) != 6:
            self.error_message = "Enter the six-digit verification code."
        elif not hmac.compare_digest(self.code, self.current_code()):
            self.error_message = "Invalid or expired verification code."
        else:
            self.error_message = ""
            self.verified.emit()
        self.update()
