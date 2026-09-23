import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF, Signal, QThread
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from core.device import verify_device
from ui.pages.login_screen import LoginScreen


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


class DeviceVerificationWorker(QThread):
    """Worker thread that executes real cryptographic challenge signing & hardware verification."""

    step_completed = Signal(int)
    finished_verification = Signal(dict)

    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.username = username

    def run(self):
        def on_step(step_idx: int, step_name: str):
            self.step_completed.emit(step_idx)
            # Micro-pause to allow UI to render step completion smoothly
            time.sleep(0.18)

        result = verify_device(self.username, progress_callback=on_step)
        self.finished_verification.emit(result)


class DeviceVerificationScreen(QWidget):
    """Existing-vault login verification with real cryptographic identity and hardware verification."""

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
        self.worker = None

        self.ring_timer = QTimer(self)
        self.ring_timer.timeout.connect(self.advance_ring)
        self.ring_timer.start(35)

    def showEvent(self, event):
        super().showEvent(event)
        self.completed_steps = 0
        self.ready = False
        self.risk_high = False
        self.start_verification()

    def start_verification(self):
        username = LoginScreen.get_default_username()
        if self.worker is not None and self.worker.isRunning():
            return
        self.worker = DeviceVerificationWorker(username, self)
        self.worker.step_completed.connect(self.on_step_completed)
        self.worker.finished_verification.connect(self.on_verification_finished)
        self.worker.start()

    def on_step_completed(self, step_idx: int):
        self.completed_steps = step_idx
        self.update()

    def on_verification_finished(self, result: dict):
        self.completed_steps = len(self.STATUS_POSITIONS)
        self.ready = True
        self.risk_high = result.get("risk_high", False)
        self.update()

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

