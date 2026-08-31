import base64
import secrets
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
DEVICE_KEY_PATH = Path(__file__).resolve().parents[2] / ".vault_device_key"


class DeviceSecurityScreen(QWidget):
    """Figma device-security progress screen with real local key generation."""

    DESIGN_W = 1440
    DESIGN_H = 1024
    device_key_generated = Signal()

    STATUS_POSITIONS = ((474, 588), (474, 661), (474, 734), (474, 807))

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vault AI")
        self.setStyleSheet("background-color: #050B15;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.renderer = QSvgRenderer(str(ASSETS_DIR / "device_security_reference.svg"))
        self.complete_popup_renderer = QSvgRenderer(str(ASSETS_DIR / "device_complete_popup.svg"))
        self.header_key = QPixmap(str(ASSETS_DIR / "device_security_embedded_0.png"))
        self.complete_icon = QPixmap(str(ASSETS_DIR / "device_security_embedded_1.png"))
        self.right_icon = QPixmap(str(ASSETS_DIR / "device_security_embedded_2.png"))
        self.complete_popup_icon = QPixmap(str(ASSETS_DIR / "device_complete_popup_icon.png"))
        self.completed_steps = 0
        self.ready = False
        self.show_complete_popup = False
        self.ring_angle = 0
        self.generation_timer = QTimer(self)
        self.generation_timer.timeout.connect(self.complete_next_step)
        self.ring_timer = QTimer(self)
        self.ring_timer.timeout.connect(self.advance_ring)
        self.ring_timer.start(35)
        self.complete_popup_timer = QTimer(self)
        self.complete_popup_timer.setSingleShot(True)
        self.complete_popup_timer.timeout.connect(self.advance_after_popup)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.ready and not self.generation_timer.isActive():
            self.generation_timer.start(650)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        painter.fillRect(self.rect(), "#050B15")
        painter.translate((self.width() - self.DESIGN_W * scale) / 2, (self.height() - self.DESIGN_H * scale) / 2)
        painter.scale(scale, scale)
        self.renderer.render(painter, QRectF(0, 0, self.DESIGN_W, self.DESIGN_H))

        # Replace the exported static highlight with a rotating sky-blue
        # segment on the same Figma progress ring.
        painter.setPen(QPen(QColor("#174D9E"), 14, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(631, 318, 178, 178), 0, 360 * 16)
        painter.setPen(QPen(QColor("#2E8DE7"), 14, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(631, 318, 178, 178), -self.ring_angle * 16, 70 * 16)

        # QSvgRenderer cannot resolve the raster patterns embedded in the
        # exported Figma SVG, so restore them at their Figma coordinates.
        painter.drawPixmap(694, 83, 50, 60, self.header_key)
        painter.drawPixmap(771, 909, 20, 20, self.right_icon)
        for index, (x, y) in enumerate(self.STATUS_POSITIONS):
            if index < self.completed_steps:
                painter.drawPixmap(x, y, 22, 22, self.complete_icon)
            else:
                self.draw_pending_icon(painter, x, y)
        if self.show_complete_popup:
            self.draw_complete_popup(painter)
        painter.end()

    def draw_complete_popup(self, painter):
        popup_x, popup_y = 561.5, 425
        self.complete_popup_renderer.render(painter, QRectF(popup_x, popup_y, 317, 174))
        # Restore the embedded Figma checkmark asset that Qt cannot resolve.
        painter.drawPixmap(int(popup_x + 138.5), int(popup_y + 29), 40, 40, self.complete_popup_icon)

    @staticmethod
    def draw_pending_icon(painter, x, y):
        painter.save()
        color = QColor("#FF4D4F")
        painter.setPen(QPen(color, 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(x + 2, y + 2, 18, 18))
        painter.setPen(color)
        painter.drawLine(x + 11, y + 6, x + 11, y + 13)
        painter.drawPoint(x + 11, y + 17)
        painter.restore()

    def complete_next_step(self):
        self.completed_steps += 1
        if self.completed_steps >= len(self.STATUS_POSITIONS):
            self.generation_timer.stop()
            self.create_local_device_key()
            self.ready = True
            self.show_complete_popup = True
            self.complete_popup_timer.start(1800)
        self.update()

    def advance_after_popup(self):
        self.show_complete_popup = False
        self.device_key_generated.emit()

    def advance_ring(self):
        if not self.ready:
            self.ring_angle = (self.ring_angle + 5) % 360
            self.update()

    @staticmethod
    def create_local_device_key():
        if not DEVICE_KEY_PATH.exists():
            key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
            DEVICE_KEY_PATH.write_text(key, encoding="utf-8")

    def mousePressEvent(self, event):
        x, y = self.design_position(event.position())
        if self.ready and not self.show_complete_popup and 454 <= x <= 985 and 886 <= y <= 952:
            self.device_key_generated.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.ready and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.device_key_generated.emit()
            return
        super().keyPressEvent(event)

    def design_position(self, point):
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        return (
            (point.x() - (self.width() - self.DESIGN_W * scale) / 2) / scale,
            (point.y() - (self.height() - self.DESIGN_H * scale) / 2) / scale,
        )
