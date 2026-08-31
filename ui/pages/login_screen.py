from pathlib import Path
import hashlib

from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from ui.fonts import figma_font, load_application_fonts


BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "ui" / "assets"
CREDENTIALS_PATH = BASE_DIR / ".vault_master_hash"


class LoginScreen(QWidget):

    DESIGN_W = 1440
    DESIGN_H = 1024
    create_new_vault = Signal()
    unlocked = Signal()

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
        self.password_cursor = 0
        self.password_visible = False
        self.password_focused = False
        self.error_message = ""
        self.password_hovered = False
        self.unlock_hovered = False
        self.cursor_visible = True
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self.cursor_timer = QTimer(self)
        self.cursor_timer.timeout.connect(self.blink_cursor)
        self.cursor_timer.start(500)

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

        field_color = (
            QColor("#2E8DE7")
            if self.password_focused
            else QColor("#3A7FFF")
            if self.password_hovered
            else QColor("#1E6CF7")
        )
        field_width = 2 if self.password_focused else 1.5
        painter.setPen(QPen(field_color, field_width))
        painter.setBrush(QColor("#0B0F1C"))
        painter.drawRoundedRect(QRectF(415.25, 413.25, 608.5, 50.5), 6.25, 6.25)
        painter.drawPixmap(424, 429, 18, 18, self.lock_icon)

        painter.setFont(figma_font("Roboto", 14, QFont.Weight.Normal))
        painter.setPen("#CBD7E1")
        password_text = self.password if self.password_visible else "•" * len(self.password)
        painter.drawText(459, 445, password_text or "Enter your master password")
        painter.drawPixmap(996, 429, 18, 18, self.eye_icon)

        if self.password_focused and self.cursor_visible:
            caret_x = 459 + painter.fontMetrics().horizontalAdvance(password_text[:self.password_cursor])
            painter.setPen(QPen(QColor("#F8F6F9"), 1.5))
            painter.drawLine(caret_x, 427, caret_x, 450)

        if self.error_message:
            painter.setFont(figma_font("Inter", 13, QFont.Weight.Normal))
            painter.setPen("#FF4D4F")
            painter.drawText(414, 478, self.error_message)

    def draw_unlock_button(self, painter):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2E8DE7") if self.unlock_hovered else QColor("#1E6CF7"))
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
            else:
                self.password_cursor = self._cursor_from_x(x)
            self.update()
        elif 414.5 <= x <= 1024.5 and 484.5 <= y <= 550.5:
            self.unlock_vault()
        elif 414.5 <= x <= 1024.5 and 630.5 <= y <= 737.5:
            self.create_new_vault.emit()
        else:
            self.password_focused = False
            self.update()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        canvas_x = (self.width() - self.DESIGN_W * scale) / 2
        canvas_y = (self.height() - self.DESIGN_H * scale) / 2
        x = (event.position().x() - canvas_x) / scale
        y = (event.position().y() - canvas_y) / scale
        self.password_hovered = 414.5 <= x <= 1024.5 and 412.5 <= y <= 464.5
        self.unlock_hovered = 414.5 <= x <= 1024.5 and 484.5 <= y <= 550.5
        self.update()
        super().mouseMoveEvent(event)

    def blink_cursor(self):
        if self.password_focused:
            self.cursor_visible = not self.cursor_visible
            self.update()

    def focusOutEvent(self, event):
        self.password_focused = False
        self.cursor_visible = True
        self.update()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if not self.password_focused:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.unlock_vault()
                return
            return super().keyPressEvent(event)

        modifiers = event.modifiers()
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.unlock_vault()
            return
        if event.key() == Qt.Key.Key_Left:
            self.password_cursor = max(0, self.password_cursor - 1)
        elif event.key() == Qt.Key.Key_Right:
            self.password_cursor = min(len(self.password), self.password_cursor + 1)
        elif event.key() == Qt.Key.Key_Home:
            self.password_cursor = 0
        elif event.key() == Qt.Key.Key_End:
            self.password_cursor = len(self.password)
        elif event.key() == Qt.Key.Key_Backspace:
            if self.password_cursor > 0:
                self.password = self.password[:self.password_cursor - 1] + self.password[self.password_cursor:]
                self.password_cursor -= 1
        elif event.key() == Qt.Key.Key_Delete:
            if self.password_cursor < len(self.password):
                self.password = self.password[:self.password_cursor] + self.password[self.password_cursor + 1:]
        elif event.key() == Qt.Key.Key_A and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.password = ""
            self.password_cursor = 0
        elif event.text() and event.text().isprintable():
            text = event.text()
            self.password = self.password[:self.password_cursor] + text + self.password[self.password_cursor:]
            self.password_cursor += len(text)
        else:
            return super().keyPressEvent(event)

        self.cursor_visible = True
        self.update()

    def _cursor_from_x(self, x):
        from PySide6.QtGui import QFontMetrics
        metrics = QFontMetrics(figma_font("Roboto", 14, QFont.Weight.Normal))
        shown = self.password if self.password_visible else "•" * len(self.password)
        target = max(0, x - 459)
        for index in range(len(shown) + 1):
            if metrics.horizontalAdvance(shown[:index]) >= target:
                return index
        return len(shown)

    def unlock_vault(self):
        stored_hash = ""
        if CREDENTIALS_PATH.exists():
            stored_hash = CREDENTIALS_PATH.read_text(encoding="utf-8").strip()
        entered_hash = hashlib.sha256(self.password.encode("utf-8")).hexdigest()

        if not self.password:
            self.error_message = "Enter your master password."
        elif not stored_hash:
            self.error_message = "No existing vault found. Create a new vault first."
        elif entered_hash != stored_hash:
            self.error_message = "Incorrect master password."
        else:
            self.error_message = ""
            self.unlocked.emit()

        self.update()

    @staticmethod
    def store_master_password(password):
        password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        CREDENTIALS_PATH.write_text(password_hash, encoding="utf-8")
