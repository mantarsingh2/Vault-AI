"""Pixel-perfect, fully interactive Vault AI Dashboard screen."""

from __future__ import annotations

import os
import platform
import socket
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget, QLineEdit

from core.ai import execute_agent_pipeline
from core.device import get_hardware_identifiers, get_key_storage_info
from database import (
    add_message,
    create_session,
    delete_session,
    ensure_default_session,
    get_session_messages,
    get_sessions,
    update_session_title,
)
from ui.fonts import figma_font, load_application_fonts


BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "ui" / "assets"


class PipelineWorker(QThread):
    chunk_signal = Signal(str)
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, query: str, session_id: str, conversation_history: list[dict[str, str]] | None = None, parent=None):
        super().__init__(parent)
        self.query = query
        self.session_id = session_id
        self.conversation_history = conversation_history or []

    def run(self):
        try:
            result = execute_agent_pipeline(
                self.query,
                session_id=self.session_id,
                conversation_history=self.conversation_history,
                on_chunk=self.chunk_signal.emit,
            )
            self.finished_signal.emit(result)
        except Exception as e:
            self.error_signal.emit(str(e))


class DashboardScreen(QWidget):
    """Interactive, database-connected Vault AI Dashboard screen."""

    DESIGN_W = 1440
    DESIGN_H = 1024

    logged_out = Signal()
    settings_clicked = Signal()
    new_chat_clicked = Signal()
    chat_selected = Signal(int, str)
    message_sent = Signal(str)

    def __init__(self):
        super().__init__()
        load_application_fonts()

        self.setWindowTitle("Vault AI")
        self.setStyleSheet("background-color: #050B15;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(800, 560)

        self.assets = [
            QPixmap(str(ASSETS_DIR / f"dashboard_embedded_{index}.png"))
            for index in range(12)
        ]

        # Active Session State
        self.current_session_id = ensure_default_session()
        self.sessions: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self.scroll_y = 0
        self.max_scroll_y = 0

        # UI State
        self.search_text = ""
        self.search_cursor = 0
        self.composer_text = ""
        self.composer_cursor = 0
        self.active_field: str | None = "composer"  # default to composer
        self.hovered_item: str | None = None
        self.selected_chat_index = 0
        self.is_thinking = False
        self.streaming_content = ""
        self.show_security_modal = False

        # Cursor blink timer
        self.cursor_visible = True
        self.cursor_timer = QTimer(self)
        self.cursor_timer.timeout.connect(self.blink_cursor)
        self.cursor_timer.start(500)

        # Pulse animation for thinking & orb
        self.anim_tick = 0
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_anim_tick)
        self.anim_timer.start(50)

        # Load initial data
        self.reload_sessions()
        self.reload_messages()

        # Native QLineEdit for robust text input
        self.input_box = QLineEdit(self)
        self.input_box.setStyleSheet("background: transparent; color: white; border: none; font-family: Roboto; font-size: 15px;")
        self.input_box.setPlaceholderText("Ask Vault AI anything or give a task...")
        self.input_box.returnPressed.connect(self.send_composer_message)
        self.input_box.show()

    def showEvent(self, event):
        super().showEvent(event)
        self.active_field = "composer"
        QTimer.singleShot(100, self.force_focus)

    def force_focus(self):
        self.activateWindow()
        self.raise_()
        self.setFocus()

    def _on_anim_tick(self):
        self.anim_tick = (self.anim_tick + 1) % 360
        if self.is_thinking or len(self.messages) == 0:
            self.update()

    def blink_cursor(self):
        if self.active_field:
            self.cursor_visible = not self.cursor_visible
            self.update()

    def reload_sessions(self):
        """Load session list from SQLite."""
        self.sessions = get_sessions(search=self.search_text)
        if not self.sessions:
            self.current_session_id = create_session("Initial Workspace")
            self.sessions = get_sessions(search=self.search_text)

    def reload_messages(self):
        """Load messages for active session from SQLite."""
        if self.current_session_id:
            self.messages = get_session_messages(self.current_session_id)
        else:
            self.messages = []
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        """Scroll chat feed to the newest message."""
        self.scroll_y = 0  # 0 represents bottom view
        self.update()

    @classmethod
    def get_default_username(cls) -> str:
        return (
            platform.node()
            or socket.gethostname()
            or os.environ.get("COMPUTERNAME")
            or "Victus"
        )

    # -------------------------------------------------------------
    # Painting & Rendering
    # -------------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        canvas_x = (self.width() - self.DESIGN_W * scale) / 2
        canvas_y = (self.height() - self.DESIGN_H * scale) / 2
        
        self.input_box.setGeometry(
            int(canvas_x + 465 * scale),
            int(canvas_y + 800 * scale),
            int(900 * scale),
            int(40 * scale)
        )
        font = self.input_box.font()
        font.setPixelSize(int(15 * scale))
        self.input_box.setFont(font)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing
            | QPainter.SmoothPixmapTransform
            | QPainter.TextAntialiasing
        )

        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        canvas_x = (self.width() - self.DESIGN_W * scale) / 2
        canvas_y = (self.height() - self.DESIGN_H * scale) / 2

        painter.fillRect(self.rect(), QColor("#050B15"))
        painter.translate(canvas_x, canvas_y)
        painter.scale(scale, scale)

        self.draw_sidebar(painter)
        self.draw_main_pane(painter)

        if self.show_security_modal:
            self.draw_security_modal(painter)

        painter.end()

    def draw_sidebar(self, painter: QPainter):
        # Divider Line
        painter.setPen(QPen(QColor("#101726"), 1.5))
        painter.drawLine(415, 0, 415, self.DESIGN_H)

        # Header Logo & App Name
        painter.drawPixmap(34, 25, 38, 38, self.assets[0])

        painter.setFont(figma_font("Inter", 26, QFont.Weight.Bold))
        painter.setPen(Qt.white)
        painter.drawText(88, 54, "Vault ")
        vault_advance = painter.fontMetrics().horizontalAdvance("Vault ")
        painter.setPen(QColor("#2E8DE7"))
        painter.drawText(88 + vault_advance, 54, "AI")

        # New Chat Button
        new_chat_hovered = self.hovered_item == "new_chat"
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2E8DE7") if new_chat_hovered else QColor("#1E6CF7"))
        painter.drawRoundedRect(QRectF(34, 124, 347, 54), 8, 8)

        painter.drawPixmap(148, 141, 20, 20, self.assets[1])
        painter.setFont(figma_font("Roboto", 16, QFont.Weight.Medium))
        painter.setPen(Qt.white)
        painter.drawText(178, 157, "New Chat")

        # Search Input Field
        search_focused = self.active_field == "search"
        search_hovered = self.hovered_item == "search"
        search_border = (
            QColor("#2E8DE7")
            if search_focused
            else QColor("#223354")
            if search_hovered
            else QColor("#152238")
        )
        painter.setPen(QPen(search_border, 1.5))
        painter.setBrush(QColor("#070C18"))
        painter.drawRoundedRect(QRectF(34, 192, 347, 48), 8, 8)

        painter.drawPixmap(44, 206, 20, 20, self.assets[2])

        painter.setFont(figma_font("Roboto", 14, QFont.Weight.Normal))
        if self.search_text:
            painter.setPen(QColor("#CBD7E1"))
            painter.drawText(74, 222, self.search_text)
        else:
            painter.setPen(QColor("#8E9AAF"))
            painter.drawText(74, 222, "Search Chats..")

        if search_focused and self.cursor_visible:
            cursor_x = 74 + painter.fontMetrics().horizontalAdvance(self.search_text[:self.search_cursor])
            painter.setPen(QPen(QColor("#F8F6F9"), 1.5))
            painter.drawLine(cursor_x, 207, cursor_x, 226)

        # Recent Chats Section Title
        painter.setFont(figma_font("Roboto", 15, QFont.Weight.Normal))
        painter.setPen(QColor("#CBD7E1"))
        painter.drawText(34, 314, "Recent Chats")

        # Recent Chats Cards from Database
        chat_y_start = 340
        card_height = 64
        card_gap = 14

        for display_idx, session in enumerate(self.sessions[:6]):
            y_pos = chat_y_start + display_idx * (card_height + card_gap)
            is_hovered = self.hovered_item == f"session_{session['id']}"
            is_del_hovered = self.hovered_item == f"delete_{session['id']}"
            is_selected = session["id"] == self.current_session_id

            bg_color = (
                QColor("#131E35")
                if is_selected
                else QColor("#0D1629")
                if (is_hovered or is_del_hovered)
                else QColor("#09101F")
            )
            border_color = (
                QColor("#2E8DE7")
                if is_selected
                else QColor("#223354")
                if (is_hovered or is_del_hovered)
                else QColor("#152238")
            )

            painter.setPen(QPen(border_color, 1.5))
            painter.setBrush(bg_color)
            painter.drawRoundedRect(QRectF(34, y_pos, 347, card_height), 8, 8)

            painter.drawPixmap(52, y_pos + 22, 20, 20, self.assets[3])

            painter.setFont(figma_font("Roboto", 15, QFont.Weight.Medium))
            painter.setPen(Qt.white)
            title_text = session["title"]
            if len(title_text) > 18:
                title_text = title_text[:16] + ".."
            painter.drawText(84, y_pos + 38, title_text)

            # Delete button — only visible on hover
            if is_hovered or is_del_hovered:
                del_rect = QRectF(348, y_pos + 18, 26, 26)
                del_bg = QColor("#5C1A1A") if is_del_hovered else QColor("#2A1515")
                del_border = QColor("#FF4D4F") if is_del_hovered else QColor("#7A2020")
                painter.setPen(QPen(del_border, 1.0))
                painter.setBrush(del_bg)
                painter.drawRoundedRect(del_rect, 5, 5)
                # Draw a minimal trash icon (✕ cross for simplicity)
                painter.setPen(QPen(QColor("#FF4D4F") if is_del_hovered else QColor("#C04040"), 1.8))
                cx, cy = 361, y_pos + 31
                painter.drawLine(int(cx - 4), int(cy - 4), int(cx + 4), int(cy + 4))
                painter.drawLine(int(cx + 4), int(cy - 4), int(cx - 4), int(cy + 4))
            else:
                painter.setFont(figma_font("Roboto", 12, QFont.Weight.Normal))
                painter.setPen(QColor("#8E9AAF"))
                time_label = session.get("updated_at", "")[11:16] or "Active"
                time_w = painter.fontMetrics().horizontalAdvance(time_label)
                painter.drawText(362 - time_w, y_pos + 38, time_label)

        # Bottom Profile Row
        profile_hovered = self.hovered_item == "profile"
        if profile_hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#0D1629"))
            painter.drawRoundedRect(QRectF(26, 832, 363, 56), 8, 8)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2E8DE7"))
        painter.drawEllipse(34, 840, 40, 40)

        username = self.get_default_username()
        painter.setFont(figma_font("Roboto", 16, QFont.Weight.Bold))
        painter.setPen(Qt.white)
        painter.drawText(88, 866, username)

        painter.drawPixmap(356, 852, 18, 18, self.assets[4])

        # Account Settings Row
        settings_hovered = self.hovered_item == "settings"
        painter.drawPixmap(44, 900, 20, 20, self.assets[5])
        painter.setFont(figma_font("Roboto", 15, QFont.Weight.Normal))
        painter.setPen(QColor("#FFFFFF") if settings_hovered else QColor("#CBD7E1"))
        painter.drawText(76, 916, "Security & Device Info")

        # Logout Row
        logout_hovered = self.hovered_item == "logout"
        painter.drawPixmap(44, 948, 20, 20, self.assets[6])
        painter.setFont(figma_font("Roboto", 15, QFont.Weight.Medium))
        painter.setPen(QColor("#FF7875") if logout_hovered else QColor("#FF4D4F"))
        painter.drawText(76, 964, "Logout")

    def draw_main_pane(self, painter: QPainter):
        # If no messages in active session, draw the Welcome Orb
        if not self.messages:
            self.draw_welcome_view(painter)
        else:
            self.draw_conversation_feed(painter)

        # Always draw the bottom Composer
        self.draw_composer(painter)

    def draw_welcome_view(self, painter: QPainter):
        # Top Left Greeting
        display_name = self.get_default_username()
        painter.setFont(figma_font("Inter", 32, QFont.Weight.DemiBold))
        painter.setPen(Qt.white)
        painter.drawText(440, 95, f"Welcome back, {display_name}")

        painter.setFont(figma_font("Roboto", 16, QFont.Weight.Normal))
        painter.setPen(QColor("#CBD7E1"))
        painter.drawText(440, 130, "How can I assist you today?")

        # Center Orb Graphics
        center_x = 927
        center_y = 360
        self.draw_orb(painter, center_x, center_y)

        # Center Welcome Text
        painter.setFont(figma_font("Inter", 28, QFont.Weight.DemiBold))
        painter.setPen(Qt.white)
        self.draw_centered_text(painter, center_x, 520, "Hello! I’m Vault AI")

        painter.setFont(figma_font("Roboto", 16, QFont.Weight.Normal))
        painter.setPen(QColor("#CBD7E1"))
        self.draw_centered_text(
            painter, center_x, 555, "Your secure, resource-aware AI desktop agent."
        )
        self.draw_centered_text(
            painter, center_x, 580, "Ask to monitor system load, inspect files, check TPM identity, or run tasks."
        )

    def draw_orb(self, painter: QPainter, cx: float, cy: float):
        # Concentric Glowing Rings with subtle rotation
        rings = [
            (98, QColor("#123F91"), 2.5),
            (84, QColor(18, 63, 145, 170), 2.0),
            (70, QColor(18, 63, 145, 120), 2.0),
        ]
        painter.setBrush(Qt.NoBrush)
        for radius, color, width in rings:
            painter.setPen(QPen(color, width))
            painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

        # Cyan Glowing Dots on Outer Ring
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#72E3F3"))
        dot_radius = 4.5
        for dx, dy in ((0, -98), (98, 0), (0, 98), (-98, 0)):
            painter.drawEllipse(
                QRectF(cx + dx - dot_radius, cy + dy - dot_radius, dot_radius * 2, dot_radius * 2)
            )

        # Small dots on inner rings
        small_dot = 2.5
        for dx, dy in ((0, -84), (0, 84), (0, -70), (0, 70)):
            painter.drawEllipse(
                QRectF(cx + dx - small_dot, cy + dy - small_dot, small_dot * 2, small_dot * 2)
            )

        # Center Shield Icon
        painter.drawPixmap(int(cx - 71), int(cy - 48), 143, 96, self.assets[7])

    def draw_conversation_feed(self, painter: QPainter):
        # Header bar for active conversation
        painter.setFont(figma_font("Inter", 20, QFont.Weight.Bold))
        painter.setPen(Qt.white)
        active_title = "Active Conversation"
        for s in self.sessions:
            if s["id"] == self.current_session_id:
                active_title = s["title"]
                break
        painter.drawText(440, 50, active_title)

        # Local Engine status badge
        badge_rect = QRectF(1240, 28, 165, 30)
        painter.setPen(QPen(QColor("#153A6A"), 1.0))
        painter.setBrush(QColor("#09172E"))
        painter.drawRoundedRect(badge_rect, 15, 15)
        painter.setFont(figma_font("Roboto", 12, QFont.Weight.Medium))
        painter.setPen(QColor("#4AE290"))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, "🟢 Local Engine Ready")

        # Chat Viewport area: X: 440 to 1405, Y: 75 to 765
        painter.save()
        viewport_rect = QRectF(440, 75, 965, 690)
        painter.setClipRect(viewport_rect)

        # Measure & render messages from bottom to top
        y_cursor = 750 + self.scroll_y
        card_spacing = 18

        # Render streaming assistant response if actively generating
        if self.streaming_content:
            stream_text = self.streaming_content + " ▌"
            painter.setFont(figma_font("Roboto", 14, QFont.Weight.Normal))
            text_rect = QRectF(0, 0, 860, 2000)
            bounds = painter.boundingRect(text_rect, Qt.TextFlag.TextWordWrap, stream_text)
            card_w = 930
            card_h = bounds.height() + 55

            card_x = 440
            card_y = y_cursor - card_h

            painter.setPen(QPen(QColor("#2E8DE7"), 1.2))
            painter.setBrush(QColor("#081120"))
            painter.drawRoundedRect(QRectF(card_x, card_y, card_w, card_h), 12, 12)

            painter.drawPixmap(card_x + 16, card_y + 14, 20, 20, self.assets[0])
            painter.setFont(figma_font("Inter", 13, QFont.Weight.Bold))
            painter.setPen(QColor("#2E8DE7"))
            painter.drawText(card_x + 44, card_y + 29, "Vault AI Assistant (Live)")

            painter.setFont(figma_font("Roboto", 11, QFont.Weight.Medium))
            painter.setPen(QColor("#72E3F3"))
            painter.drawText(card_x + card_w - 180, card_y + 29, "[GENERATING]")

            painter.setFont(figma_font("Roboto", 14, QFont.Weight.Normal))
            painter.setPen(QColor("#E2E8F0"))
            painter.drawText(
                QRectF(card_x + 18, card_y + 44, card_w - 36, card_h - 50),
                Qt.TextFlag.TextWordWrap,
                stream_text,
            )

            y_cursor = card_y - card_spacing

        for msg in reversed(self.messages):
            is_user = msg["role"] == "user"
            content = msg["content"]

            if is_user:
                # User Message Card (Right Aligned)
                painter.setFont(figma_font("Roboto", 15, QFont.Weight.Normal))
                text_rect = QRectF(0, 0, 700, 1000)
                bounds = painter.boundingRect(text_rect, Qt.TextFlag.TextWordWrap, content)
                card_w = min(720, bounds.width() + 40)
                card_h = bounds.height() + 30

                card_x = 1405 - card_w
                card_y = y_cursor - card_h

                painter.setPen(QPen(QColor("#2E8DE7"), 1.0))
                painter.setBrush(QColor("#102B52"))
                painter.drawRoundedRect(QRectF(card_x, card_y, card_w, card_h), 12, 12)

                painter.setPen(Qt.white)
                painter.drawText(
                    QRectF(card_x + 20, card_y + 15, card_w - 40, card_h - 20),
                    Qt.TextFlag.TextWordWrap,
                    content,
                )

                y_cursor = card_y - card_spacing

            else:
                # Assistant Message Card (Left Aligned)
                lines = content.split("\n")
                painter.setFont(figma_font("Roboto", 14, QFont.Weight.Normal))
                text_rect = QRectF(0, 0, 860, 2000)
                bounds = painter.boundingRect(text_rect, Qt.TextFlag.TextWordWrap, content)
                card_w = 930
                card_h = bounds.height() + 55

                card_x = 440
                card_y = y_cursor - card_h

                painter.setPen(QPen(QColor("#1B2E4E"), 1.2))
                painter.setBrush(QColor("#081120"))
                painter.drawRoundedRect(QRectF(card_x, card_y, card_w, card_h), 12, 12)

                # Vault AI Header Badge on response
                painter.drawPixmap(card_x + 16, card_y + 14, 20, 20, self.assets[0])
                painter.setFont(figma_font("Inter", 13, QFont.Weight.Bold))
                painter.setPen(QColor("#2E8DE7"))
                painter.drawText(card_x + 44, card_y + 29, "Vault AI Assistant")

                # Intent tag
                intent_label = msg.get("intent", "general").replace("_", " ").upper()
                painter.setFont(figma_font("Roboto", 11, QFont.Weight.Medium))
                painter.setPen(QColor("#7088A8"))
                painter.drawText(card_x + card_w - 180, card_y + 29, f"[{intent_label}]")

                # Content Body
                painter.setFont(figma_font("Roboto", 14, QFont.Weight.Normal))
                painter.setPen(QColor("#E2E8F0"))
                painter.drawText(
                    QRectF(card_x + 18, card_y + 44, card_w - 36, card_h - 50),
                    Qt.TextFlag.TextWordWrap,
                    content,
                )

                y_cursor = card_y - card_spacing

        # If Assistant is thinking, draw pulsing indicator
        if self.is_thinking and not self.streaming_content:
            think_rect = QRectF(440, y_cursor - 45, 340, 38)
            painter.setPen(QPen(QColor("#2E8DE7"), 1.0))
            painter.setBrush(QColor("#0C1B33"))
            painter.drawRoundedRect(think_rect, 8, 8)
            painter.setFont(figma_font("Roboto", 13, QFont.Weight.Medium))
            painter.setPen(QColor("#72E3F3"))
            painter.drawText(think_rect, Qt.AlignmentFlag.AlignCenter, "🧠 Vault AI is analyzing & planning...")

        painter.restore()

    def draw_composer(self, painter: QPainter):
        composer_rect = QRectF(440, 785, 965, 165)
        composer_focused = self.active_field == "composer"
        composer_hovered = self.hovered_item == "composer"
        border_color = (
            QColor("#2E8DE7")
            if composer_focused
            else QColor("#223354")
            if composer_hovered
            else QColor("#152238")
        )

        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(QColor("#060B16"))
        painter.drawRoundedRect(composer_rect, 12, 12)

        # Text input is now handled by self.input_box QLineEdit
        
        # Left Attachment / Action Icons
        clip_hovered = self.hovered_item == "clip"
        mic_hovered = self.hovered_item == "mic"
        img_hovered = self.hovered_item == "img"

        painter.setOpacity(1.0 if clip_hovered else 0.85)
        painter.drawPixmap(465, 902, 24, 24, self.assets[8])

        painter.setOpacity(1.0 if mic_hovered else 0.85)
        painter.drawPixmap(505, 902, 24, 24, self.assets[9])

        painter.setOpacity(1.0 if img_hovered else 0.85)
        painter.drawPixmap(545, 902, 24, 24, self.assets[10])

        painter.setOpacity(1.0)

        # Quick action pills above send
        painter.setFont(figma_font("Roboto", 12, QFont.Weight.Normal))
        painter.setPen(QColor("#475569"))
        painter.drawText(600, 918, "Try: 'Show CPU stats' | 'List files' | 'Check TPM security'")

        # Right Send Button
        send_hovered = self.hovered_item == "send_button"
        send_rect = QRectF(1337, 887, 58, 50)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2E8DE7") if send_hovered else QColor("#1E6CF7"))
        painter.drawRoundedRect(send_rect, 8, 8)

        painter.drawPixmap(1351, 897, 30, 30, self.assets[11])

    def draw_security_modal(self, painter: QPainter):
        """Draw interactive Security & TPM Information Modal."""
        # Backdrop
        painter.fillRect(QRectF(0, 0, self.DESIGN_W, self.DESIGN_H), QColor(0, 0, 0, 180))

        modal_rect = QRectF(420, 220, 600, 480)
        painter.setPen(QPen(QColor("#2E8DE7"), 1.5))
        painter.setBrush(QColor("#0B1528"))
        painter.drawRoundedRect(modal_rect, 16, 16)

        # Header
        painter.drawPixmap(450, 250, 36, 36, self.assets[0])
        painter.setFont(figma_font("Inter", 22, QFont.Weight.Bold))
        painter.setPen(Qt.white)
        painter.drawText(500, 276, "Device Cryptographic Identity")

        sec_info = get_key_storage_info()
        hw_ids = get_hardware_identifiers()

        lines = [
            ("Key Storage Provider:", "TPM 2.0 (Hardware-backed)" if sec_info.get("hardware_backed") else "Windows CNG / Software KSP (OS-Protected)"),
            ("Private Key Status:", "Non-Exportable (Locked in OS boundary)"),
            ("Signing Algorithm:", "NIST ECDSA P-256 (SHA-256)"),
            ("Hardware Hostname:", hw_ids.get("hostname", "LocalDevice")),
            ("MAC Address:", hw_ids.get("mac_address", "N/A")),
            ("Platform OS:", hw_ids.get("platform", "Windows")),
        ]

        y = 330
        for label, val in lines:
            painter.setFont(figma_font("Roboto", 14, QFont.Weight.Medium))
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(450, y, label)

            painter.setFont(figma_font("Roboto", 14, QFont.Weight.Normal))
            painter.setPen(QColor("#E2E8F0"))
            painter.drawText(650, y, val)
            y += 40

        # Close button
        close_btn_rect = QRectF(660, 620, 120, 44)
        close_hover = self.hovered_item == "modal_close"
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2E8DE7") if close_hover else QColor("#1E6CF7"))
        painter.drawRoundedRect(close_btn_rect, 8, 8)
        painter.setFont(figma_font("Roboto", 15, QFont.Weight.Medium))
        painter.setPen(Qt.white)
        painter.drawText(close_btn_rect, Qt.AlignmentFlag.AlignCenter, "Close")

    @staticmethod
    def draw_centered_text(painter: QPainter, center_x: float, baseline_y: float, text: str):
        width = painter.fontMetrics().horizontalAdvance(text)
        painter.drawText(int(center_x - width / 2), int(baseline_y), text)


    # -------------------------------------------------------------
    # User Input & Message Handling
    # -------------------------------------------------------------
    def send_composer_message(self):
        text = self.input_box.text().strip()
        if not text or self.is_thinking:
            return

        # Clear composer input
        self.input_box.clear()
        self.composer_text = ""
        self.composer_cursor = 0

        # If this is the first message in session, update title
        if not self.messages and self.current_session_id:
            title_candidate = text[:26] + ("..." if len(text) > 26 else "")
            update_session_title(self.current_session_id, title_candidate)
            self.reload_sessions()

        # 1. Save user message to database
        add_message(self.current_session_id, role="user", content=text)
        self.reload_messages()
        self.message_sent.emit(text)

        # 2. Retrieve bounded history for local model context
        conversation_history = self.conversation_manager.get_bounded_history(
            self.current_session_id
        )

        # 3. Set thinking state and trigger agent pipeline asynchronously in background
        self.is_thinking = True
        self.update()

        self.pipeline_worker = PipelineWorker(
            text, str(self.current_session_id), conversation_history, self
        )
        self.pipeline_worker.chunk_signal.connect(self._on_agent_chunk)
        self.pipeline_worker.finished_signal.connect(self._on_agent_finished)
        self.pipeline_worker.error_signal.connect(self._on_agent_error)
        self.pipeline_worker.start()

    def _on_agent_chunk(self, chunk: str):
        self.is_thinking = False
        self.streaming_content += chunk
        self.update()

    def _on_agent_finished(self, agent_result: dict):
        add_message(
            self.current_session_id,
            role=agent_result.get("role", "assistant"),
            content=agent_result.get("content", ""),
            intent=agent_result.get("intent", "general"),
            status=agent_result.get("status", "success"),
        )
        self.is_thinking = False
        self.streaming_content = ""
        self.reload_messages()
        self.reload_sessions()
        self.update()

    def _on_agent_error(self, error_msg: str):
        add_message(
            self.current_session_id,
            role="assistant",
            content=f"⚠️ **Error executing agent pipeline:** {error_msg}",
            status="error",
        )
        self.is_thinking = False
        self.streaming_content = ""
        self.reload_messages()
        self.reload_sessions()
        self.update()

    def start_new_chat(self):
        """Create a fresh chat session."""
        self.current_session_id = create_session("New Chat")
        self.reload_sessions()
        self.reload_messages()
        self.composer_text = ""
        self.composer_cursor = 0
        self.active_field = "composer"
        self.new_chat_clicked.emit()
        self.update()

    def delete_chat_session(self, session_id: int):
        """Delete a chat session and all its messages from the database."""
        delete_session(session_id)
        # If we deleted the active session, switch to another
        if self.current_session_id == session_id:
            self.reload_sessions()
            if self.sessions:
                self.current_session_id = self.sessions[0]["id"]
            else:
                self.current_session_id = create_session("New Chat")
                self.reload_sessions()
        else:
            self.reload_sessions()
        self.reload_messages()
        self.hovered_item = None
        self.update()

    def select_session(self, session_id: int):
        """Switch active session."""
        self.current_session_id = session_id
        self.reload_messages()
        self.update()

    def wheelEvent(self, event):
        """Enable mouse wheel scrolling in conversation feed."""
        delta = event.angleDelta().y()
        self.scroll_y = max(0, self.scroll_y + delta)
        self.update()

    def mousePressEvent(self, event):
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        canvas_x = (self.width() - self.DESIGN_W * scale) / 2
        canvas_y = (self.height() - self.DESIGN_H * scale) / 2
        x = (event.position().x() - canvas_x) / scale
        y = (event.position().y() - canvas_y) / scale

        # Security Modal Close Button
        if self.show_security_modal:
            if 660 <= x <= 780 and 620 <= y <= 664:
                self.show_security_modal = False
                self.update()
                return
            if not (420 <= x <= 1020 and 220 <= y <= 700):
                self.show_security_modal = False
                self.update()
                return
            return

        # New Chat Button
        if 34 <= x <= 381 and 124 <= y <= 178:
            self.start_new_chat()
            return

        # Search Bar
        if 34 <= x <= 381 and 192 <= y <= 240:
            self.active_field = "search"
            self.search_cursor = len(self.search_text)
            self.setFocus()
            self.update()
            return

        # Recent Chat Cards — check delete button first, then card select
        for idx, session in enumerate(self.sessions[:6]):
            card_y = 340 + idx * (64 + 14)
            if 34 <= x <= 381 and card_y <= y <= card_y + 64:
                # Delete button zone (right edge of card)
                if 345 <= x <= 381 and card_y + 14 <= y <= card_y + 50:
                    self.delete_chat_session(session["id"])
                    return
                self.select_session(session["id"])
                return

        # Profile / Account Settings Row
        if (26 <= x <= 389 and 832 <= y <= 888) or (34 <= x <= 220 and 896 <= y <= 930):
            self.show_security_modal = True
            self.settings_clicked.emit()
            self.update()
            return

        # Logout
        if 34 <= x <= 220 and 944 <= y <= 980:
            self.logged_out.emit()
            return

        # Composer Send Button
        if 1337 <= x <= 1395 and 887 <= y <= 937:
            self.send_composer_message()
            return

        # Quick Suggestion Icons in Composer
        if 460 <= x <= 495 and 895 <= y <= 935:
            self.composer_text = "List files in this project"
            self.composer_cursor = len(self.composer_text)
            self.active_field = "composer"
            self.update()
            return
        elif 500 <= x <= 535 and 895 <= y <= 935:
            self.composer_text = "Check system health and CPU load"
            self.composer_cursor = len(self.composer_text)
            self.active_field = "composer"
            self.update()
            return
        elif 540 <= x <= 575 and 895 <= y <= 935:
            self.composer_text = "Verify TPM device identity"
            self.composer_cursor = len(self.composer_text)
            self.active_field = "composer"
            self.update()
            return

        # Composer Text Area
        if 440 <= x <= 1405 and 785 <= y <= 950:
            self.active_field = "composer"
            self.composer_cursor = len(self.composer_text)
            self.setFocus()
            self.update()
            return

        # If clicked outside, default to composer so user can always type
        if not self.active_field:
            self.active_field = "composer"
            
        self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scale = min(self.width() / self.DESIGN_W, self.height() / self.DESIGN_H)
        canvas_x = (self.width() - self.DESIGN_W * scale) / 2
        canvas_y = (self.height() - self.DESIGN_H * scale) / 2
        x = (event.position().x() - canvas_x) / scale
        y = (event.position().y() - canvas_y) / scale

        prev_hover = self.hovered_item
        self.hovered_item = None

        if self.show_security_modal:
            if 660 <= x <= 780 and 620 <= y <= 664:
                self.hovered_item = "modal_close"
        elif 34 <= x <= 381 and 124 <= y <= 178:
            self.hovered_item = "new_chat"
        elif 34 <= x <= 381 and 192 <= y <= 240:
            self.hovered_item = "search"
        elif 26 <= x <= 389 and 832 <= y <= 888:
            self.hovered_item = "profile"
        elif 34 <= x <= 220 and 896 <= y <= 930:
            self.hovered_item = "settings"
        elif 34 <= x <= 220 and 944 <= y <= 980:
            self.hovered_item = "logout"
        elif 1337 <= x <= 1395 and 887 <= y <= 937:
            self.hovered_item = "send_button"
        elif 460 <= x <= 495 and 895 <= y <= 935:
            self.hovered_item = "clip"
        elif 500 <= x <= 535 and 895 <= y <= 935:
            self.hovered_item = "mic"
        elif 540 <= x <= 575 and 895 <= y <= 935:
            self.hovered_item = "img"
        elif 440 <= x <= 1405 and 785 <= y <= 950:
            self.hovered_item = "composer"
        else:
            for idx, session in enumerate(self.sessions[:6]):
                card_y = 340 + idx * (64 + 14)
                if 34 <= x <= 381 and card_y <= y <= card_y + 64:
                    # Check if hovering the delete button zone
                    if 345 <= x <= 381 and card_y + 14 <= y <= card_y + 50:
                        self.hovered_item = f"delete_{session['id']}"
                    else:
                        self.hovered_item = f"session_{session['id']}"
                    break

        if self.hovered_item != prev_hover:
            self.update()

        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if not self.active_field:
            return super().keyPressEvent(event)

        key = event.key()
        modifiers = event.modifiers()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.active_field == "composer":
                self.send_composer_message()
            return

        if self.active_field == "search":
            if key == Qt.Key.Key_Left:
                self.search_cursor = max(0, self.search_cursor - 1)
            elif key == Qt.Key.Key_Right:
                self.search_cursor = min(len(self.search_text), self.search_cursor + 1)
            elif key == Qt.Key.Key_Home:
                self.search_cursor = 0
            elif key == Qt.Key.Key_End:
                self.search_cursor = len(self.search_text)
            elif key == Qt.Key.Key_Backspace:
                if self.search_cursor > 0:
                    self.search_text = self.search_text[: self.search_cursor - 1] + self.search_text[self.search_cursor :]
                    self.search_cursor -= 1
                    self.reload_sessions()
            elif key == Qt.Key.Key_Delete:
                if self.search_cursor < len(self.search_text):
                    self.search_text = self.search_text[: self.search_cursor] + self.search_text[self.search_cursor + 1 :]
                    self.reload_sessions()
            elif key == Qt.Key.Key_A and modifiers & Qt.KeyboardModifier.ControlModifier:
                self.search_text = ""
                self.search_cursor = 0
                self.reload_sessions()
            elif event.text() and event.text().isprintable():
                t = event.text()
                self.search_text = self.search_text[: self.search_cursor] + t + self.search_text[self.search_cursor :]
                self.search_cursor += len(t)
                self.reload_sessions()
            else:
                return super().keyPressEvent(event)



        self.cursor_visible = True
        self.update()

    def blink_cursor(self):
        if self.active_field:
            self.cursor_visible = not self.cursor_visible
            self.update()

    def focusOutEvent(self, event):
        self.cursor_visible = True
        self.update()
        super().focusOutEvent(event)
