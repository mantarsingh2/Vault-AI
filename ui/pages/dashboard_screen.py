from pathlib import Path

from PySide6.QtCore import Qt, QRectF, Signal, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from ui.fonts import load_application_fonts


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


class DashboardScreen(QWidget):
    """Original Figma dashboard with responsive canvas scaling."""

    DESIGN_W = 1440
    DESIGN_H = 1024
    logged_out = Signal()
    settings_clicked = Signal()

    ASSET_LAYOUT = (
        (0, 34, 25, 45, 45), (1, 149, 144, 20, 20), (2, 44, 211, 20, 20),
        (3, 54, 372, 20, 20), (3, 54, 450, 20, 20), (3, 54, 528, 20, 20),
        (3, 54, 606, 20, 20), (3, 54, 684, 20, 20), (3, 54, 762, 20, 20),
        (4, 346, 868, 24, 24), (5, 44, 921, 22, 22), (6, 44, 971, 22, 22),
        (7, 856, 339, 143, 96), (8, 446, 921, 30, 30), (9, 486, 921, 30, 30),
        (10, 526, 921, 30, 30), (11, 1376, 920, 30, 30),
    )

    def __init__(self):
        super().__init__()
        load_application_fonts()
        self.setWindowTitle("Vault AI")
        self.setStyleSheet("background-color: #050B15;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(480, 480)
        self.renderer = QSvgRenderer(str(ASSETS_DIR / "dashboard_reference.svg"))
        self.assets = [QPixmap(str(ASSETS_DIR / f"dashboard_embedded_{index}.png")) for index in range(12)]
        self.search_text = ""
        self.composer_text = ""
        self.sent_messages = []
        self.active_field = None
        self.cursor_visible = True
        self.cursor_timer = QTimer(self)
        self.cursor_timer.timeout.connect(self.blink_cursor)
        self.cursor_timer.start(500)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        painter.fillRect(self.rect(), QColor("#050B15"))
        scale_x, scale_y = self.canvas_scale()
        painter.scale(scale_x, scale_y)

        # Render the supplied design across the current viewport.  This keeps
        # its exact Figma composition while removing side gutters at any size.
        self.renderer.render(painter, QRectF(0, 0, self.DESIGN_W, self.DESIGN_H))
        for index, x, y, width, height in self.ASSET_LAYOUT:
            painter.drawPixmap(x, y, width, height, self.assets[index])

        painter.setFont(QFont("Inter", 15))
        if self.search_text:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#070A16"))
            painter.drawRoundedRect(QRectF(72, 202, 295, 38), 3, 3)
            painter.setPen(QColor("#CBD7E1"))
            painter.drawText(QRectF(78, 202, 270, 38), Qt.AlignVCenter, self.search_text)
        if self.cursor_visible and self.active_field == "search":
            cursor_x = 78 + painter.fontMetrics().horizontalAdvance(self.search_text)
            painter.setPen(QPen(QColor("#F8F6F9"), 1.5))
            painter.drawLine(cursor_x, 207, cursor_x, 235)

        # These overlays make the exported composer and search box editable
        # without changing their original Figma styling or placement.
        painter.setBrush(QColor("#0A0F1E"))
        painter.setPen(Qt.NoPen)
        painter.drawRect(QRectF(440, 812, 900, 48))
        painter.setPen(QColor("#F8F6F9") if self.composer_text else QColor("#8E9AAF"))
        painter.drawText(QRectF(450, 825, 880, 34), Qt.AlignLeft | Qt.AlignVCenter,
                         self.composer_text or "Type your message...")
        if self.cursor_visible and self.active_field == "composer":
            cursor_x = 450 + painter.fontMetrics().horizontalAdvance(self.composer_text)
            painter.setPen(QPen(QColor("#F8F6F9"), 1.5))
            painter.drawLine(cursor_x, 818, cursor_x, 850)
        if self.sent_messages:
            painter.setPen(QColor("#CBD7E1"))
            painter.drawText(QRectF(450, 470, 850, 30), Qt.AlignLeft | Qt.AlignVCenter, self.sent_messages[-1])

        painter.resetTransform()
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor("#1A2035"), 1))
        painter.drawRect(QRectF(.5, .5, self.width() - 1, self.height() - 1))
        painter.end()

    def mousePressEvent(self, event):
        x, y = self.design_position(event.position())
        if 34 <= x <= 381 and 195 <= y <= 247:
            self.active_field = "search"
        elif 425 <= x <= 1431 and 803 <= y <= 972:
            self.active_field = "composer"
        elif 34 <= x <= 381 and 921 <= y <= 950:
            self.settings_clicked.emit()
        elif 34 <= x <= 220 and 960 <= y <= 1024:
            self.logged_out.emit()
        else:
            self.active_field = None
        self.setFocus()
        self.update()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.active_field not in ("search", "composer"):
            return super().keyPressEvent(event)
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.active_field == "composer" and self.composer_text.strip():
                self.sent_messages.append(self.composer_text.strip())
                self.composer_text = ""
        elif event.key() == Qt.Key_Backspace:
            if self.active_field == "search":
                self.search_text = self.search_text[:-1]
            else:
                self.composer_text = self.composer_text[:-1]
        elif event.text() and event.text().isprintable():
            if self.active_field == "search":
                self.search_text += event.text()
            else:
                self.composer_text += event.text()
        else:
            return super().keyPressEvent(event)
        self.update()

    def blink_cursor(self):
        if self.active_field:
            self.cursor_visible = not self.cursor_visible
            self.update()

    def canvas_scale(self):
        return self.width() / self.DESIGN_W, self.height() / self.DESIGN_H

    def design_position(self, point):
        scale_x, scale_y = self.canvas_scale()
        return point.x() / scale_x, point.y() / scale_y
