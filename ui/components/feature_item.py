from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
)
from PySide6.QtSvgWidgets import QSvgWidget


class FeatureItem(QWidget):

    def __init__(
        self,
        icon_path: str,
        text: str,
        parent=None
    ):

        super().__init__(
            parent
        )

        self.setFixedWidth(
            95
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        layout.setSpacing(
            8
        )

        # ---------------------------------------------
        # Icon
        # ---------------------------------------------

        icon = QSvgWidget()

        if Path(icon_path).exists():

            icon.load(
                icon_path
            )

        icon.setFixedSize(
            30,
            30
        )

        layout.addWidget(
            icon,
            alignment=Qt.AlignCenter
        )

        # ---------------------------------------------
        # Text
        # ---------------------------------------------

        label = QLabel(
            text
        )

        label.setAlignment(
            Qt.AlignCenter
        )

        label.setStyleSheet("""
            QLabel {
                color: #C7D0DB;
                font-size: 12px;
                font-weight: 400;
            }
        """)

        layout.addWidget(
            label
        )