from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPainter, QPixmap
from PySide6.QtWidgets import QWidget


BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "ui" / "assets"


class SplashScreen(QWidget):

    DESIGN_W = 1440
    DESIGN_H = 1024

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Vault AI")
        self.setStyleSheet("background-color: #050B15;")

        # Fit design to screen
        screen = self.screen().availableGeometry()

        scale = min(
            screen.width() / self.DESIGN_W,
            screen.height() / self.DESIGN_H,
        )

        self.window_w = int(self.DESIGN_W * scale)
        self.window_h = int(self.DESIGN_H * scale)

        self.setFixedSize(self.window_w, self.window_h)

        # Assets
        self.wave = self.load_pixmap("wave.png")
        self.logo = self.load_pixmap("logo.png")
        self.protect = self.load_pixmap("protect.png")
        self.lock = self.load_pixmap("lock.png")
        self.flash = self.load_pixmap("Flash on.png")
        self.eye = self.load_pixmap("eye.png")

        self.progress = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(30)

    def load_pixmap(self, filename):
        path = ASSETS_DIR / filename
        pixmap = QPixmap(str(path))

        if pixmap.isNull():
            print(f"ERROR: {filename} could not be loaded")

        return pixmap

    def update_progress(self):
        self.progress += 1

        if self.progress > 100:
            self.progress = 0

        self.update()

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Use Figma coordinate system
        sx = self.width() / self.DESIGN_W
        sy = self.height() / self.DESIGN_H

        painter.scale(sx, sy)

        # Background
        painter.fillRect(
            0,
            0,
            self.DESIGN_W,
            self.DESIGN_H,
            Qt.GlobalColor.transparent,
        )

        # -------------------------------------------------
        # WAVE
        # -------------------------------------------------

        if not self.wave.isNull():

            painter.drawPixmap(
                -75,
                207,
                1672,
                941,
                self.wave,
            )

        # -------------------------------------------------
        # LOGO
        # -------------------------------------------------

        if not self.logo.isNull():

            painter.drawPixmap(
                620,
                207,
                200,
                133,
                self.logo,
            )

        # -------------------------------------------------
        # VAULT AI
        # -------------------------------------------------

        painter.setFont(
            QFont(
                "Inter",
                40,
                QFont.Weight.DemiBold,
            )
        )

        vault_width = painter.fontMetrics().horizontalAdvance("VAULT")
        ai_width = painter.fontMetrics().horizontalAdvance("AI")

        spacing = 8

        total_width = (
            vault_width
            + spacing
            + ai_width
        )

        title_x = (
            self.DESIGN_W - total_width
        ) / 2

        painter.setPen(Qt.white)

        painter.drawText(
            int(title_x),
            410,
            "VAULT",
        )

        painter.setPen("#1E6CF7")

        painter.drawText(
            int(
                title_x
                + vault_width
                + spacing
            ),
            410,
            "AI",
        )

        # -------------------------------------------------
        # TAGLINE
        # -------------------------------------------------

        painter.setFont(
            QFont(
                "Inter",
                24,
                QFont.Weight.Normal,
            )
        )

        painter.setPen("#CBD7E1")

        tagline = "Your Intelligent  Desktop Guardian"

        tagline_width = (
            painter.fontMetrics()
            .horizontalAdvance(tagline)
        )

        painter.drawText(
            int(
                (self.DESIGN_W - tagline_width)
                / 2
            ),
            453,
            tagline,
        )

        # -------------------------------------------------
        # PROGRESS BAR
        # -------------------------------------------------

        bar_width = 399
        bar_height = 8

        bar_x = (
            self.DESIGN_W - bar_width
        ) / 2

        bar_y = 556

        painter.setPen(Qt.NoPen)

        painter.setBrush("#17263D")

        painter.drawRoundedRect(
            int(bar_x),
            bar_y,
            bar_width,
            bar_height,
            4,
            4,
        )

        painter.setBrush("#1890FF")

        progress_width = max(
            8,
            int(
                bar_width
                * self.progress
                / 100
            ),
        )

        painter.drawRoundedRect(
            int(bar_x),
            bar_y,
            progress_width,
            bar_height,
            4,
            4,
        )

        # -------------------------------------------------
        # LOADING TEXT
        # -------------------------------------------------

        painter.setFont(
            QFont(
                "Inter",
                15,
                QFont.Weight.Normal,
            )
        )

        painter.setPen(Qt.white)

        loading = "Loading...."

        loading_width = (
            painter.fontMetrics()
            .horizontalAdvance(loading)
        )

        painter.drawText(
            int(
                (self.DESIGN_W - loading_width)
                / 2
            ),
            599,
            loading,
        )

        # -------------------------------------------------
        # FEATURES
        # -------------------------------------------------
        #
        # Four features are now positioned as
        # one centered group with equal spacing.
        #

        feature_centers = [
            480,
            640,
            800,
            960,
        ]

        self.draw_feature(
            painter,
            feature_centers[0],
            self.protect,
            "Secure",
        )

        self.draw_feature(
            painter,
            feature_centers[1],
            self.lock,
            "Privacy",
        )

        self.draw_feature(
            painter,
            feature_centers[2],
            self.flash,
            "powerful",
        )

        self.draw_feature(
            painter,
            feature_centers[3],
            self.eye,
            "Aware",
        )

        painter.end()

    def draw_feature(
        self,
        painter,
        center_x,
        icon,
        text,
    ):

        # Icon
        if not icon.isNull():

            icon_size = 28

            painter.drawPixmap(
                int(
                    center_x
                    - icon_size / 2
                ),
                767,
                icon_size,
                icon_size,
                icon,
            )

        # Text
        painter.setFont(
            QFont(
                "Inter",
                14,
                QFont.Weight.Normal,
            )
        )

        painter.setPen("#CBD7E1")

        text_width = (
            painter.fontMetrics()
            .horizontalAdvance(text)
        )

        painter.drawText(
            int(
                center_x
                - text_width / 2
            ),
            816,
            text,
        )