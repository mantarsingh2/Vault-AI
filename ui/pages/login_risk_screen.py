from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget
from ui.fonts import load_application_fonts

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


class LoginRiskScreen(QWidget):
    risk_complete = Signal(bool)
    DESIGN_W, DESIGN_H = 1440, 1024
    STATUS_POSITIONS = ((467, 467), (467, 564), (467, 661), (467, 758), (467, 855))

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vault AI")
        self.setStyleSheet("background-color: #050B15;")
        load_application_fonts()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.renderer = QSvgRenderer(str(ASSETS_DIR / "login_risk_reference.svg"))
        self.complete_popup_renderer = QSvgRenderer(str(ASSETS_DIR / "device_complete_popup.svg"))
        self.complete_popup_icon = QPixmap(str(ASSETS_DIR / "device_complete_popup_icon.png"))
        self.assets = [QPixmap(str(ASSETS_DIR / f"login_risk_embedded_{index}.png")) for index in range(7)]
        self.step = 0
        self.done = False
        self.show_complete_popup = False
        self.risk_high = False
        self.dot_index = 0
        self.dot_timer = QTimer(self)
        self.dot_timer.timeout.connect(self.advance_dot)
        self.dot_timer.start(250)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)

        self.finish_timer = QTimer(self)
        self.finish_timer.setSingleShot(True)
        self.finish_timer.timeout.connect(self._emit_complete)

    def showEvent(self, event):
        super().showEvent(event)
        # The screen is created at application startup, so its assessment
        # must begin when it is actually shown, not while it is hidden.
        self.step = 0
        self.done = False
        self.show_complete_popup = False
        self.dot_index = 0
        self.finish_timer.stop()
        self.timer.start(550)
        self.dot_timer.start(250)
        self.setFocus()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        p.fillRect(self.rect(), "#050B15")
        p.translate((self.width() - self.DESIGN_W * scale) / 2, (self.height() - self.DESIGN_H * scale) / 2)
        p.scale(scale, scale)
        self.renderer.render(p, QRectF(0, 0, self.DESIGN_W, self.DESIGN_H))
        p.drawPixmap(705, 129, 50, 60, self.assets[0])
        # Animate the three Figma assessment dots while checks run.
        p.setPen(Qt.NoPen)
        for index, x in enumerate((695, 720, 745)):
            p.setBrush(QColor("#2E8DE7") if index == self.dot_index else QColor("#D9D9D9"))
            p.drawEllipse(QRectF(x - 7, 369, 14, 14))
        # Replace the static right-side labels with the live state.
        p.setPen(Qt.NoPen)
        p.setBrush("#0C111F")
        p.drawRect(QRectF(915, 458, 66, 420))
        p.setFont(self._status_font())
        for index, y in enumerate((483, 580, 677, 774, 871)):
            if index < self.step:
                p.setPen("#52C41A")
                p.drawText(925, y, "Good")
                p.drawPixmap(467, y - 16, 25, 25, self.assets[2])
            elif index == self.step and not self.done:
                p.setPen("#2E8DE7")
                p.drawText(918, y, "Checking...")
                self._draw_pending(p, 467, y - 16, True)
            else:
                p.setPen("#8E9AAF")
                p.drawText(918, y, "Pending")
                self._draw_pending(p, 467, y - 16, False)
        if self.show_complete_popup:
            self.draw_complete_popup(p)
        p.end()

    def draw_complete_popup(self, painter):
        popup_x, popup_y = 561.5, 425
        self.complete_popup_renderer.render(painter, QRectF(popup_x, popup_y, 317, 174))
        painter.drawPixmap(int(popup_x + 138.5), int(popup_y + 29), 40, 40, self.complete_popup_icon)

    @staticmethod
    def _status_font():
        from ui.fonts import figma_font
        from PySide6.QtGui import QFont
        return figma_font("Inter", 14, QFont.Weight.Medium)

    @staticmethod
    def _draw_pending(painter, x, y, active):
        color = QColor("#2E8DE7") if active else QColor("#8E9AAF")
        painter.save(); painter.setPen(QPen(color, 1.5)); painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(x + 3, y + 3, 19, 19))
        if active:
            painter.drawArc(QRectF(x + 3, y + 3, 19, 19), 30 * 16, 220 * 16)
        else:
            painter.drawLine(x + 12, y + 7, x + 12, y + 15); painter.drawPoint(x + 12, y + 19)
        painter.restore()

    def advance(self):
        if self.step < 5:
            self.step += 1
            self.update()
        if self.step == 5:
            self.timer.stop()
            self.dot_timer.stop()
            self.done = True
            self.show_complete_popup = True
            self.update()
            # Keep the completion confirmation visible before continuing.
            self.finish_timer.start(1800)

    def advance_dot(self):
        if not self.done:
            self.dot_index = (self.dot_index + 1) % 3
            self.update()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.done and not self.show_complete_popup and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._emit_complete()
            return
        super().keyPressEvent(event)

    def set_risk_level(self, high):
        self.risk_high = bool(high)

    def _emit_complete(self):
        if self.done and self.show_complete_popup:
            self.show_complete_popup = False
            self.update()
            self.risk_complete.emit(self.risk_high)
