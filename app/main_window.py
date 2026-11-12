"""Main Application Window for Vault AI — Prompt-Driven Assistant UI."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.workers import AgentPromptWorker, OllamaCheckWorker
from ui.components.status_badge import StatusBadge


class ChatBubble(QFrame):
    """A styled message bubble in the conversation feed."""

    def __init__(self, text: str, is_user: bool = False, extra_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.extra_data = extra_data or {}

        self._init_ui(text)

    def _init_ui(self, text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Header tag
        tag_layout = QHBoxLayout()
        tag_label = QLabel("YOU" if self.is_user else "VAULT AI (qwen3:8b)")
        tag_label.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #93C5FD;" if self.is_user
            else "font-size: 11px; font-weight: 700; color: #34D399;"
        )
        tag_layout.addWidget(tag_label)
        tag_layout.addStretch()
        layout.addLayout(tag_layout)

        # Main message text
        msg_label = QLabel(text)
        msg_label.setWordWrap(True)
        msg_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        msg_label.setStyleSheet("font-size: 13px; line-height: 1.4; color: #F1F5F9;")
        layout.addWidget(msg_label)

        # Extra data widgets (Duplicates, Suggestions, Matched Files)
        if not self.is_user and self.extra_data:
            self._render_extra_data(layout)

        # Frame Styling
        if self.is_user:
            self.setStyleSheet("""
                ChatBubble {
                    background-color: #1E3A8A;
                    border: 1px solid #2563EB;
                    border-radius: 12px;
                    margin-left: 60px;
                    margin-right: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                ChatBubble {
                    background-color: #0B1728;
                    border: 1px solid #162B4A;
                    border-radius: 12px;
                    margin-left: 10px;
                    margin-right: 60px;
                }
            """)

    def _render_extra_data(self, layout: QVBoxLayout):
        duplicates = self.extra_data.get("duplicates", [])
        suggestions = self.extra_data.get("suggestions", [])
        matched_files = self.extra_data.get("matched_files", [])

        # 1. Duplicate files tree
        if duplicates:
            dup_title = QLabel(f"🔁 Duplicate Files Detected ({len(duplicates)} Groups)")
            dup_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #60A5FA; margin-top: 4px;")
            layout.addWidget(dup_title)

            tree = QTreeWidget()
            tree.setHeaderLabels(["File / Path", "Size", "Savings", "Hash"])
            tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
            tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
            tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
            tree.setStyleSheet("background-color: #081220; border: 1px solid #162B4A; font-size: 12px; border-radius: 6px;")
            tree.setMinimumHeight(140)

            for d in duplicates[:6]:
                parent_item = QTreeWidgetItem([
                    f"Duplicate Group ({d.get('count', 2)} copies)",
                    d.get("human_size", ""),
                    f"Saves {d.get('potential_savings', '')}",
                    d.get("hash", "")[:12] + "...",
                ])
                parent_item.setForeground(0, QColor("#60A5FA"))
                for path in d.get("files", []):
                    child = QTreeWidgetItem([path, "", "", ""])
                    parent_item.addChild(child)
                tree.addTopLevelItem(parent_item)
                parent_item.setExpanded(True)

            layout.addWidget(tree)

        # 2. Suggested Organization Moves
        if suggestions:
            sugg_title = QLabel(f"💡 Organization Recommendations ({len(suggestions)} Suggestions)")
            sugg_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #FBBF24; margin-top: 6px;")
            layout.addWidget(sugg_title)

            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Original File", "Suggested Destination", "Category", "Reason"])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
            table.setStyleSheet("background-color: #081220; border: 1px solid #162B4A; font-size: 12px; border-radius: 6px;")
            table.setRowCount(len(suggestions[:10]))
            table.setMinimumHeight(140)

            for r, s in enumerate(suggestions[:10]):
                table.setItem(r, 0, QTableWidgetItem(s.get("original_path", "")))
                table.setItem(r, 1, QTableWidgetItem(s.get("suggested_destination", "")))
                table.setItem(r, 2, QTableWidgetItem(s.get("category", "")))
                table.setItem(r, 3, QTableWidgetItem(s.get("reason", "")))

            layout.addWidget(table)

            notice = QLabel("🛡️ Plan-First: These are recommendations. No files are moved or deleted automatically.")
            notice.setStyleSheet("font-size: 11px; color: #93C5FD; font-style: italic;")
            layout.addWidget(notice)

        # 3. Matched Search Files
        elif matched_files:
            match_title = QLabel(f"📄 Matched Files ({len(matched_files)})")
            match_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #34D399; margin-top: 4px;")
            layout.addWidget(match_title)

            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["File Name", "Category", "Size", "Location"])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            table.header = table.horizontalHeader()
            table.header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            table.header.setSectionResizeMode(3, QHeaderView.Stretch)
            table.setStyleSheet("background-color: #081220; border: 1px solid #162B4A; font-size: 12px; border-radius: 6px;")
            table.setRowCount(len(matched_files[:10]))
            table.setMinimumHeight(130)

            for r, f in enumerate(matched_files[:10]):
                table.setItem(r, 0, QTableWidgetItem(f.get("name", "")))
                table.setItem(r, 1, QTableWidgetItem(f.get("category", "")))
                table.setItem(r, 2, QTableWidgetItem(f.get("human_size", "")))
                table.setItem(r, 3, QTableWidgetItem(f.get("path", "")))

            layout.addWidget(table)


class MainWindow(QMainWindow):
    """Main dashboard window for Vault AI desktop application."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vault AI — Intelligent Desktop Guardian")
        self.resize(1100, 780)
        self.setMinimumSize(850, 600)

        self.prompt_worker: Optional[AgentPromptWorker] = None

        self._setup_styles()
        self._init_ui()
        self._check_ollama_status()

    def _setup_styles(self):
        """Apply unified dark theme styling."""
        self.setStyleSheet("""
            QMainWindow, QWidget#CentralWidget {
                background-color: #050B15;
                color: #CBD7E1;
                font-family: 'Segoe UI', Inter, sans-serif;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QFrame#welcomeCard {
                background-color: #0B1728;
                border: 1px solid #162B4A;
                border-radius: 10px;
                padding: 16px;
            }
            QLabel {
                color: #CBD7E1;
            }
            QLabel#headerTitle {
                font-size: 20px;
                font-weight: 700;
                color: #FFFFFF;
            }
            QPushButton {
                background-color: #1E6CF7;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2F7CFF;
            }
            QPushButton:pressed {
                background-color: #1656C9;
            }
            QPushButton:disabled {
                background-color: #192D4D;
                color: #556B88;
            }
            QPushButton#chipButton {
                background-color: #112239;
                color: #93C5FD;
                border: 1px solid #1E3A63;
                border-radius: 14px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton#chipButton:hover {
                background-color: #1E3A63;
                color: #FFFFFF;
                border-color: #1E6CF7;
            }
            QPushButton#secondaryButton {
                background-color: #162B4A;
                color: #CBD7E1;
                border: 1px solid #234373;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton#secondaryButton:hover {
                background-color: #1E3A63;
            }
            QLineEdit#promptInput {
                background-color: #081220;
                border: 2px solid #162B4A;
                border-radius: 10px;
                color: #FFFFFF;
                padding: 12px 16px;
                font-size: 14px;
            }
            QLineEdit#promptInput:focus {
                border-color: #1E6CF7;
            }
            QProgressBar {
                background-color: #0B1728;
                border: 1px solid #162B4A;
                border-radius: 4px;
                text-align: center;
                color: #FFFFFF;
                font-size: 11px;
                height: 6px;
            }
            QProgressBar::chunk {
                background-color: #1890FF;
                border-radius: 3px;
            }
        """)

    def _init_ui(self):
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)

        # 1. Header (Branding + Status badge)
        header_layout = QHBoxLayout()
        title_label = QLabel("🛡️ VAULT AI — Intelligent Desktop Guardian")
        title_label.setObjectName("headerTitle")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.status_badge = StatusBadge("Checking Ollama...", is_online=False)
        header_layout.addWidget(self.status_badge)

        self.btn_refresh_status = QPushButton("↻")
        self.btn_refresh_status.setObjectName("secondaryButton")
        self.btn_refresh_status.setFixedWidth(36)
        self.btn_refresh_status.setToolTip("Refresh Ollama status")
        self.btn_refresh_status.clicked.connect(self._check_ollama_status)
        header_layout.addWidget(self.btn_refresh_status)

        main_layout.addLayout(header_layout)

        # 2. Scrollable Chat / Activity Feed
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(8, 8, 8, 8)
        self.chat_layout.setSpacing(14)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.chat_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # Add Welcome Card
        self._add_welcome_card()

        # 3. Live Status & Progress Row
        self.status_row = QHBoxLayout()
        self.lbl_live_status = QLabel("")
        self.lbl_live_status.setStyleSheet("font-size: 12px; color: #60A5FA; font-weight: 500;")
        self.status_row.addWidget(self.lbl_live_status)
        self.status_row.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedWidth(120)
        self.progress_bar.setVisible(False)
        self.status_row.addWidget(self.progress_bar)

        main_layout.addLayout(self.status_row)

        # 4. Prompt Input Bar (Bottom)
        input_container = QFrame()
        input_container.setStyleSheet("background-color: #0B1728; border: 1px solid #162B4A; border-radius: 12px; padding: 6px;")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(6, 4, 6, 4)
        input_layout.setSpacing(10)

        self.input_prompt = QLineEdit()
        self.input_prompt.setObjectName("promptInput")
        self.input_prompt.setPlaceholderText("Ask Vault AI (e.g. 'Find duplicate files in Downloads', 'Organize my college documents')...")
        self.input_prompt.returnPressed.connect(self._send_prompt)
        input_layout.addWidget(self.input_prompt)

        self.btn_send = QPushButton("Ask Vault AI ➔")
        self.btn_send.setMinimumWidth(140)
        self.btn_send.clicked.connect(self._send_prompt)
        input_layout.addWidget(self.btn_send)

        main_layout.addWidget(input_container)

    def _add_welcome_card(self):
        welcome_card = QFrame()
        welcome_card.setObjectName("welcomeCard")
        w_layout = QVBoxLayout(welcome_card)
        w_layout.setSpacing(10)

        w_title = QLabel("👋 Welcome to Vault AI!")
        w_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #FFFFFF;")
        w_layout.addWidget(w_title)

        w_desc = QLabel("I am your local AI Desktop Guardian. Simply type a natural-language request below to inspect, analyze, or organize your local files.")
        w_desc.setStyleSheet("font-size: 13px; color: #94A3B8; line-height: 1.4;")
        w_layout.addWidget(w_desc)

        chips_label = QLabel("Try these prompt examples:")
        chips_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #CBD7E1; margin-top: 4px;")
        w_layout.addWidget(chips_label)

        chips_layout = QHBoxLayout()
        example_prompts = [
            "Find duplicate files in Downloads",
            "Organize my documents and suggest a plan",
            "Where are my resume and invoices?",
            "Find all PDF files",
        ]

        for p in example_prompts:
            btn = QPushButton(p)
            btn.setObjectName("chipButton")
            btn.clicked.connect(lambda _, prompt=p: self._run_prompt(prompt))
            chips_layout.addWidget(btn)

        chips_layout.addStretch()
        w_layout.addLayout(chips_layout)

        # Insert at top
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, welcome_card)

    def _check_ollama_status(self):
        self.status_badge.update_status(False, "Checking Ollama...")
        self.checker_worker = OllamaCheckWorker()
        self.checker_worker.result_signal.connect(self._on_ollama_status_result)
        self.checker_worker.start()

    def _on_ollama_status_result(self, is_online: bool, status_text: str):
        self.status_badge.update_status(is_online, status_text)

    def _send_prompt(self):
        text = self.input_prompt.text().strip()
        if not text:
            return
        self.input_prompt.clear()
        self._run_prompt(text)

    def _run_prompt(self, prompt: str):
        # 1. Append user bubble
        user_bubble = ChatBubble(prompt, is_user=True)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, user_bubble)

        # 2. Update UI state to busy
        self.input_prompt.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_live_status.setText("Processing request with Vault AI...")

        # Scroll to bottom
        QTimer.singleShot(50, self._scroll_to_bottom)

        # 3. Launch background worker
        self.prompt_worker = AgentPromptWorker(prompt)
        self.prompt_worker.status_signal.connect(self._on_agent_status)
        self.prompt_worker.finished_signal.connect(self._on_agent_finished)
        self.prompt_worker.error_signal.connect(self._on_agent_error)
        self.prompt_worker.start()

    def _on_agent_status(self, status: str):
        self.lbl_live_status.setText(status)

    def _on_agent_finished(self, result: dict):
        self.input_prompt.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_live_status.setText("")

        ai_response_text = result.get("ai_response", "Analysis complete.")

        # Append assistant response bubble with extra data
        assistant_bubble = ChatBubble(
            text=ai_response_text,
            is_user=False,
            extra_data=result,
        )
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, assistant_bubble)
        self.input_prompt.setFocus()

        QTimer.singleShot(50, self._scroll_to_bottom)

    def _on_agent_error(self, error: str):
        self.input_prompt.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_live_status.setText("")

        error_bubble = ChatBubble(
            text=f"⚠️ Error: {error}",
            is_user=False,
        )
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, error_bubble)
        self.input_prompt.setFocus()

        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        vbar = self.scroll_area.verticalScrollBar()
        vbar.setValue(vbar.maximum())