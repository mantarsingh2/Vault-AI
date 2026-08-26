from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from ui.fonts import figma_font, load_application_fonts


BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "ui" / "assets"


class SplashScreen(QWidget):

    DESIGN_W = 1440
    DESIGN_H = 1024
    get_started = Signal()

    def __init__(self):
        super().__init__()

        load_application_fonts()

        self.setWindowTitle("Vault AI")
        self.setStyleSheet("background-color: #050B15;")

        # -----------------------------------------
        # WINDOW SIZE
        # -----------------------------------------

        screen = self.screen().availableGeometry()

        scale = min(
            screen.width() / self.DESIGN_W,
            screen.height() / self.DESIGN_H,
        )

        self.window_w = int(self.DESIGN_W * scale)
        self.window_h = int(self.DESIGN_H * scale)

        # Start at the largest size that fits the current desktop, while
        # remaining resizable. paintEvent keeps the Figma canvas proportional
        # at every window size.
        self.resize(
            self.window_w,
            self.window_h,
        )

        # -----------------------------------------
        # LOAD ASSETS
        # -----------------------------------------

        self.wave = self.load_pixmap("wave.png")
        self.logo = self.load_pixmap("logo.png")
        self.protect = self.load_pixmap("protect.png")
        self.lock = self.load_pixmap("lock.png")
        self.flash = self.load_pixmap("Flash on.png")
        self.eye = self.load_pixmap("eye.png")

        self.progress = 0
        self.show_get_started = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(30)

    # ---------------------------------------------
    # LOAD IMAGE
    # ---------------------------------------------

    def load_pixmap(self, filename):

        path = ASSETS_DIR / filename

        pixmap = QPixmap(str(path))

        if pixmap.isNull():
            print(f"ERROR: {filename} could not be loaded")

        return pixmap

    def update_progress(self):

        self.progress += 1

        if self.progress >= 100:

            self.progress = 100
            self.timer.stop()
            self.show_get_started = True

        self.update()

    # ---------------------------------------------
    # DRAW SCREEN
    # ---------------------------------------------

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.Antialiasing
        )

        painter.setRenderHint(
            QPainter.SmoothPixmapTransform
        )

        # -----------------------------------------
        # SCALE TO DESIGN SIZE
        # -----------------------------------------

        scale = min(
            self.width() / self.DESIGN_W,
            self.height() / self.DESIGN_H,
        )

        canvas_x = (self.width() - self.DESIGN_W * scale) / 2
        canvas_y = (self.height() - self.DESIGN_H * scale) / 2

        painter.fillRect(self.rect(), "#050B15")
        painter.translate(canvas_x, canvas_y)
        painter.scale(scale, scale)

        # -----------------------------------------
        # BACKGROUND
        # -----------------------------------------

        # -----------------------------------------
        # WAVE
        # -----------------------------------------

        if not self.wave.isNull():

            painter.drawPixmap(
                -96,
                167,
                1672,
                941,
                self.wave,
            )

        # -----------------------------------------
        # LOGO
        # -----------------------------------------

        if not self.logo.isNull():

            painter.drawPixmap(
                620,
                207,
                200,
                133,
                self.logo,
            )

        # -----------------------------------------
        # VAULT AI
        # -----------------------------------------

        painter.setFont(
            figma_font("Inter", 40, QFont.Weight.DemiBold)
        )

        vault_width = (
            painter.fontMetrics()
            .horizontalAdvance("VAULT")
        )

        ai_width = (
            painter.fontMetrics()
            .horizontalAdvance("AI")
        )

        total_width = (
            vault_width
            + 8
            + ai_width
        )

        x = (
            self.DESIGN_W - total_width
        ) / 2

        painter.setPen("#F8F6F9")

        painter.drawText(
            int(x),
            410,
            "VAULT",
        )

        painter.setPen("#1E6CF7")

        painter.drawText(
            int(x + vault_width + 8),
            410,
            "AI",
        )

        # -----------------------------------------
        # TAGLINE
        # -----------------------------------------

        painter.setFont(
            figma_font("Inter", 24, QFont.Weight.Normal)
        )

        painter.setPen("#CBD7E1")

        tagline = (
            "Your Intelligent  Desktop Guardian"
        )

        tagline_width = (
            painter.fontMetrics()
            .horizontalAdvance(tagline)
        )

        painter.drawText(
            int(
                (self.DESIGN_W - tagline_width) / 2
            ),
            453,
            tagline,
        )

        # -----------------------------------------
        # LOADING / GET STARTED
        # -----------------------------------------

        if self.show_get_started:
            self.draw_get_started(painter)
        else:
            self.draw_progress(painter)

        # -----------------------------------------
        # FEATURES
        # -----------------------------------------

        self.draw_feature(
            painter,
            542.5,
            self.protect,
            "Secure",
        )

        self.draw_feature(
            painter,
            653,
            self.lock,
            "Privacy",
        )

        self.draw_feature(
            painter,
            778,
            self.flash,
            "powerful",
        )

        self.draw_feature(
            painter,
            897.5,
            self.eye,
            "Aware",
        )

        painter.end()

    def draw_progress(self, painter):

        bar_x = (self.DESIGN_W - 399) / 2
        bar_y = 556

        painter.setPen(Qt.NoPen)
        painter.setBrush("#17263D")
        painter.drawRoundedRect(int(bar_x), bar_y, 399, 8, 4, 4)

        painter.setBrush("#1890FF")
        progress_width = max(8, int(399 * self.progress / 100))
        painter.drawRoundedRect(int(bar_x), bar_y, progress_width, 8, 4, 4)

        painter.setFont(figma_font("Inter", 15, QFont.Weight.Normal))
        painter.setPen(Qt.white)

        loading = "Loading...."
        loading_width = painter.fontMetrics().horizontalAdvance(loading)
        painter.drawText(int((self.DESIGN_W - loading_width) / 2), 599, loading)

    # ---------------------------------------------
    # GET STARTED BUTTON
    # ---------------------------------------------

    def draw_get_started(self, painter):

        button_x = 568
        button_y = 545
        button_w = 304
        button_h = 62

        painter.setPen(Qt.NoPen)

        painter.setBrush("#2E8DE7")

        painter.drawRoundedRect(
            button_x,
            button_y,
            button_w,
            button_h,
            9,
            9,
        )

        painter.setFont(
            figma_font("Roboto", 24, QFont.Weight.Medium)
        )

        painter.setPen(Qt.white)

        text = "Get Started"

        text_width = (
            painter.fontMetrics()
            .horizontalAdvance(text)
        )

        painter.drawText(
            int(
                button_x
                + (button_w - text_width) / 2
            ),
            button_y + 40,
            text,
        )

    # ---------------------------------------------
    # FEATURES
    # ---------------------------------------------

    def draw_feature(
        self,
        painter,
        center_x,
        icon,
        text,
    ):

        if not icon.isNull():

            painter.drawPixmap(
                int(center_x - 12),
                767,
                24,
                24,
                icon,
            )

        painter.setFont(
            figma_font("Inter", 14, QFont.Weight.Normal)
        )

        painter.setPen("#CBD7E1")

        width = (
            painter.fontMetrics()
            .horizontalAdvance(text)
        )

        painter.drawText(
            int(center_x - width / 2),
            816,
            text,
        )

    # ---------------------------------------------
    # GET STARTED CLICK
    # ---------------------------------------------

    def mousePressEvent(self, event):

        if (
            self.show_get_started
            and event.button() == Qt.MouseButton.LeftButton
        ):

            # Button area
            button_x = 568
            button_y = 545
            button_w = 304
            button_h = 62

            # Convert mouse position
            scale = min(
                self.width() / self.DESIGN_W,
                self.height() / self.DESIGN_H,
            )

            canvas_x = (self.width() - self.DESIGN_W * scale) / 2
            canvas_y = (self.height() - self.DESIGN_H * scale) / 2

            x = (event.position().x() - canvas_x) / scale
            y = (event.position().y() - canvas_y) / scale

            if (
                button_x <= x <= button_x + button_w
                and
                button_y <= y <= button_y + button_h
            ):

                print("Get Started clicked")
                self.get_started.emit()

        super().mousePressEvent(event)
