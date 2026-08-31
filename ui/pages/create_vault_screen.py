from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ui.fonts import figma_font, load_application_fonts
from ui.pages.login_screen import LoginScreen


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


class CreateVaultScreen(QWidget):
    DESIGN_W = 1440
    DESIGN_H = 1024
    vault_created = Signal()

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
        self.master_password = ""
        self.confirm_password = ""
        self.active_field = 0
        self.password_visible = [False, False]
        self.password_cursors = [0, 0]
        self.hovered_field = 0
        self.error_message = ""
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.cursor_visible = True
        self.cursor_timer = QTimer(self)
        self.cursor_timer.timeout.connect(self.blink_cursor)
        self.cursor_timer.start(500)

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

    def field(self, p, y, label, placeholder, value, field_index, helper=""):
        p.setFont(figma_font("Roboto", 16, QFont.Weight.Bold)); p.setPen(Qt.white); p.drawText(415, y, label)
        focused = self.active_field == field_index
        color = "#2E8DE7" if focused else "#3A7FFF" if self.hovered_field == field_index else "#1E6CF7"
        p.setPen(QPen(QColor(color), 2 if focused else 1.5)); p.setBrush("#0B0F1C"); p.drawRoundedRect(QRectF(415.25, y + 13.25, 608.5, 50.5), 6.25, 6.25)
        p.drawPixmap(425, y + 29, 18, 18, self.lock); p.setFont(figma_font("Roboto", 14, QFont.Weight.Normal)); p.setPen("#CBD7E1")
        # ``active_field`` uses the screen-level field ids (1 and 2), while
        # ``password_visible`` contains only the two password toggle states.
        # Convert the field id to the corresponding visibility slot so the
        # confirmation field cannot index past the end of the list.
        visibility_index = field_index - 1
        shown = value if self.password_visible[visibility_index] else "\u2022" * len(value)
        p.drawText(459, y + 46, shown or placeholder); p.drawPixmap(996, y + 29, 18, 18, self.eye)
        if focused and self.cursor_visible:
            caret_x = 459 + p.fontMetrics().horizontalAdvance(shown[:self.password_cursors[visibility_index]])
            p.setPen(QPen(QColor("#F8F6F9"), 1.5)); p.drawLine(caret_x, y + 27, caret_x, y + 50)
        if helper:
            p.setFont(figma_font("Inter", 15, QFont.Weight.Normal)); p.drawText(415, y + 84, helper)

    def passwords(self, p):
        self.field(p, 320, "Master Password", "Enter your master password", self.master_password, 1, "Must be at least 8 characters long.")
        self.field(p, 456, "Confirm Master Password", "Confirm your master password", self.confirm_password, 2)

    def strength(self, p):
        p.setFont(figma_font("Roboto", 16, QFont.Weight.Medium)); p.setPen("#CBD7E1"); p.drawText(415, 552, "Password Strength")
        p.setPen(Qt.NoPen); p.setBrush("#1B314C"); p.drawRoundedRect(415, 567, 609, 8, 5, 5)
        rules = self._password_rules()
        score = sum(rules) + (len(self.master_password) >= 8)
        strength = score * 20
        if score >= 5:
            color = "#52C41A"
        elif score >= 3:
            color = "#FAAD14"
        else:
            color = "#FF4D4F"
        p.setBrush(color)
        p.drawRoundedRect(415, 567, max(8, int(609 * strength / 100)), 8, 5, 5)

    def rules(self, p):
        p.setPen(QPen(QColor("#262C41"), 3)); p.setBrush("#080E1E"); p.drawRoundedRect(QRectF(416, 599, 607, 105), 5.5, 5.5)
        labels = [
            (435, 627, "At least one lowercase letter", self._password_rules()[0]),
            (772, 627, "At least one number", self._password_rules()[2]),
            (435, 671, "At least one special character", self._password_rules()[3]),
            (772, 671, "At least one uppercase letter", self._password_rules()[1]),
        ]
        p.setFont(figma_font("Roboto", 16, QFont.Weight.Medium))
        for x, y, text, satisfied in labels:
            self._draw_rule_status(p, x, y - 16, satisfied)
            p.setFont(figma_font("Roboto", 16, QFont.Weight.Medium))
            p.setPen("#CBD7E1")
            p.drawText(x + 26, y, text)

    def _password_rules(self):
        password = self.master_password
        return (
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        )

    @staticmethod
    def _draw_rule_status(p, x, y, satisfied):
        color = QColor("#52C41A") if satisfied else QColor("#FF4D4F")
        p.setPen(QPen(color, 1.5)); p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(x + 1, y + 1, 14, 14))
        p.setFont(figma_font("Inter", 11, QFont.Weight.Bold)); p.setPen(color)
        p.drawText(x + 5, y + 12, "✓" if satisfied else "!")

    def create_button(self, p):
        p.setPen(Qt.NoPen); p.setBrush("#1E6CF7"); p.drawRoundedRect(415, 724, 610, 66, 7, 7); p.drawPixmap(574, 747, 20, 20, self.lock)
        p.setFont(figma_font("Roboto", 20, QFont.Weight.Medium)); p.setPen(Qt.white); p.drawText(604, 769, "CREATE SECURE VAULT"); p.drawPixmap(845, 747, 20, 20, self.right)

    def notice(self, p):
        p.setPen(QPen(QColor("#232840"), 3)); p.setBrush("#101525"); p.drawRoundedRect(QRectF(416, 821, 607, 103), 5.5, 5.5); p.drawPixmap(426, 854, 40, 40, self.info)
        p.setFont(figma_font("Roboto", 20, QFont.Weight.Medium)); p.setPen(Qt.white); p.drawText(480, 859, "Important to remember")
        p.setFont(figma_font("Inter", 15, QFont.Weight.Normal)); p.setPen("#CBD7E1"); p.drawText(480, 886, "There is no recovery option. If your forgot your master password,"); p.drawText(480, 906, "you will lose the access to your Vault permanently.")
        if self.error_message:
            p.setFont(figma_font("Inter", 13, QFont.Weight.Normal)); p.setPen("#FF4D4F"); p.drawText(415, 948, self.error_message)

    @staticmethod
    def center(p, x, y, text):
        p.drawText(int(x - p.fontMetrics().horizontalAdvance(text) / 2), y, text)

    def mousePressEvent(self, event):
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        canvas_x = (self.width() - self.DESIGN_W * scale) / 2
        canvas_y = (self.height() - self.DESIGN_H * scale) / 2
        x = (event.position().x() - canvas_x) / scale
        y = (event.position().y() - canvas_y) / scale

        if 415 <= x <= 1025 and 724 <= y <= 790:
            self.create_vault()
        elif 415 <= x <= 1025 and 333 <= y <= 383:
            self.active_field = 1
            if x >= 978:
                self.password_visible[0] = not self.password_visible[0]
            else:
                self.password_cursors[0] = self._cursor_from_x(x, self.master_password, 0)
            self.setFocus(); self.update()
        elif 415 <= x <= 1025 and 469 <= y <= 519:
            self.active_field = 2
            if x >= 978:
                self.password_visible[1] = not self.password_visible[1]
            else:
                self.password_cursors[1] = self._cursor_from_x(x, self.confirm_password, 1)
            self.setFocus(); self.update()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        x = (event.position().x() - (self.width() - self.DESIGN_W * scale) / 2) / scale
        y = (event.position().y() - (self.height() - self.DESIGN_H * scale) / 2) / scale
        self.hovered_field = 1 if 415 <= x <= 1025 and 333 <= y <= 383 else 2 if 415 <= x <= 1025 and 469 <= y <= 519 else 0
        self.update()
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.create_vault()
            return
        if self.active_field not in (1, 2):
            return super().keyPressEvent(event)
        field_index = self.active_field - 1
        value = self.master_password if field_index == 0 else self.confirm_password
        cursor = self.password_cursors[field_index]
        modifiers = event.modifiers()
        if event.key() == Qt.Key.Key_Left:
            cursor = max(0, cursor - 1)
        elif event.key() == Qt.Key.Key_Right:
            cursor = min(len(value), cursor + 1)
        elif event.key() == Qt.Key.Key_Home:
            cursor = 0
        elif event.key() == Qt.Key.Key_End:
            cursor = len(value)
        elif event.key() == Qt.Key.Key_Backspace:
            if cursor > 0:
                value = value[:cursor - 1] + value[cursor:]
                cursor -= 1
        elif event.key() == Qt.Key.Key_Delete:
            if cursor < len(value):
                value = value[:cursor] + value[cursor + 1:]
        elif event.key() == Qt.Key.Key_A and modifiers & Qt.KeyboardModifier.ControlModifier:
            value = ""
            cursor = 0
        elif event.text() and event.text().isprintable():
            text = event.text()
            value = value[:cursor] + text + value[cursor:]
            cursor += len(text)
        else:
            return super().keyPressEvent(event)
        if field_index == 0:
            self.master_password = value
        else:
            self.confirm_password = value
        self.password_cursors[field_index] = cursor
        self.error_message = ""
        self.cursor_visible = True
        self.update()

    def _cursor_from_x(self, x, value, field_index):
        from PySide6.QtGui import QFontMetrics
        metrics = QFontMetrics(figma_font("Roboto", 14, QFont.Weight.Normal))
        shown = value if self.password_visible[field_index] else "•" * len(value)
        target = max(0, x - 459)
        for index in range(len(shown) + 1):
            if metrics.horizontalAdvance(shown[:index]) >= target:
                return index
        return len(shown)

    def blink_cursor(self):
        if self.active_field in (1, 2):
            self.cursor_visible = not self.cursor_visible
            self.update()

    def create_vault(self):
        password = self.master_password
        if len(password) < 8:
            self.error_message = "Password must be at least 8 characters long."
        elif password != self.confirm_password:
            self.error_message = "Passwords do not match."
        elif not all(self._password_rules()):
            self.error_message = "Use uppercase, lowercase, number, and special character."
        else:
            LoginScreen.store_master_password(password)
            self.error_message = ""
            self.vault_created.emit()
        self.update()
