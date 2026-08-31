from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
DEVICE_KEY_PATH = Path(__file__).resolve().parents[2] / ".vault_device_key"


class DeviceVerificationScreen(QWidget):
    """Existing-vault login verification rendered from the Figma export."""

    DESIGN_W = 1440
    DESIGN_H = 1024
    verified = Signal()
    risk_assessed = Signal(bool)
    STATUS_POSITIONS = ((475, 564), (475, 637), (475, 710), (475, 783))

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vault AI")
        self.setStyleSheet("background-color: #050B15;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.renderer = QSvgRenderer(str(ASSETS_DIR / "device_verification_reference.svg"))
        self.header_icon = QPixmap(str(ASSETS_DIR / "device_verification_embedded_0.png"))
        self.complete_icon = QPixmap(str(ASSETS_DIR / "device_verification_embedded_1.png"))
        self.right_icon = QPixmap(str(ASSETS_DIR / "device_verification_embedded_2.png"))
        self.completed_steps = 0
        self.ready = False
        self.risk_high = False
        self.ring_angle = 0
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.complete_next_step)
        self.ring_timer = QTimer(self)
        self.ring_timer.timeout.connect(self.advance_ring)
        self.ring_timer.start(35)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.ready and not self.check_timer.isActive():
            self.check_timer.start(650)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        painter.fillRect(self.rect(), "#050B15")
        painter.translate((self.width() - self.DESIGN_W * scale) / 2, (self.height() - self.DESIGN_H * scale) / 2)
        painter.scale(scale, scale)
        self.renderer.render(painter, QRectF(0, 0, self.DESIGN_W, self.DESIGN_H))

        painter.setPen(QPen(QColor("#174D9E"), 14, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(631, 345, 178, 178), 0, 360 * 16)
        painter.setPen(QPen(QColor("#2E8DE7"), 14, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(631, 345, 178, 178), -self.ring_angle * 16, 70 * 16)
        painter.drawPixmap(695, 110, 50, 60, self.header_icon)
        painter.drawPixmap(800, 882, 20, 20, self.right_icon)
        for index, (x, y) in enumerate(self.STATUS_POSITIONS):
            if index < self.completed_steps:
                painter.drawPixmap(x, y, 22, 22, self.complete_icon)
            else:
                self.draw_pending_icon(painter, x, y)
        painter.end()

    @staticmethod
    def draw_pending_icon(painter, x, y):
        painter.save()
        color = QColor("#FF4D4F")
        painter.setPen(QPen(color, 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(x + 2, y + 2, 18, 18))
        painter.drawLine(x + 11, y + 6, x + 11, y + 13)
        painter.drawPoint(x + 11, y + 17)
        painter.restore()

    def advance_ring(self):
        if not self.ready:
            self.ring_angle = (self.ring_angle + 5) % 360
            self.update()

    def complete_next_step(self):
        self.completed_steps += 1
        if self.completed_steps >= len(self.STATUS_POSITIONS):
            self.check_timer.stop()
            self.ready = True
            # A device without a locally registered key requires the extra
            # authentication step; a registered device can continue directly.
            self.risk_high = not DEVICE_KEY_PATH.exists()
        self.update()

    def mousePressEvent(self, event):
        x, y = self.design_position(event.position())
        if self.ready and 455 <= x <= 985 and 859 <= y <= 925:
            self.risk_assessed.emit(self.risk_high)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.ready and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.risk_assessed.emit(self.risk_high)
            return
        super().keyPressEvent(event)

    def design_position(self, point):
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        return (
            (point.x() - (self.width() - self.DESIGN_W * scale) / 2) / scale,
            (point.y() - (self.height() - self.DESIGN_H * scale) / 2) / scale,
        )
