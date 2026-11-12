"""Status badge component for displaying system readiness (Ollama, models, scan states)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class StatusBadge(QWidget):
    """A pill-shaped status indicator widget."""

    def __init__(self, initial_text: str = "Checking AI...", is_online: bool = False, parent=None):
        super().__init__(parent)
        self._is_online = is_online

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        self.dot = QFrame()
        self.dot.setFixedSize(8, 8)

        self.label = QLabel(initial_text)
        self.label.setStyleSheet("font-size: 12px; font-weight: 500;")

        layout.addWidget(self.dot)
        layout.addWidget(self.label)

        self.update_status(is_online, initial_text)

    def update_status(self, is_online: bool, text: str):
        self._is_online = is_online
        self.label.setText(text)

        if is_online:
            self.dot.setStyleSheet("background-color: #10B981; border-radius: 4px;")
            self.label.setStyleSheet("color: #10B981; font-size: 12px; font-weight: 500;")
            self.setStyleSheet("""
                StatusBadge {
                    background-color: #064E3B;
                    border: 1px solid #059669;
                    border-radius: 12px;
                }
            """)
        else:
            self.dot.setStyleSheet("background-color: #EF4444; border-radius: 4px;")
            self.label.setStyleSheet("color: #F87171; font-size: 12px; font-weight: 500;")
            self.setStyleSheet("""
                StatusBadge {
                    background-color: #450A0A;
                    border: 1px solid #DC2626;
                    border-radius: 12px;
                }
            """)
