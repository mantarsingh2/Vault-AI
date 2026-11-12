"""Asynchronous Qt background workers for Vault AI."""

import time
from typing import List, Optional
from PySide6.QtCore import QObject, QThread, Signal

from core.ai.ollama_client import OllamaClient
from core.file_manager.analyzer import FileAnalyzer
from core.file_manager.models import FileInfo, ScanReport
from core.file_manager.plan_generator import PlanGenerator
from core.file_manager.scanner import FileScanner


class ScanWorker(QThread):
    """Background worker for scanning directories, calculating hashes, and detecting duplicates."""

    progress_signal = Signal(int, str)  # (file_count, current_file)
    status_signal = Signal(str)         # Status message
    finished_signal = Signal(object)    # ScanReport object
    error_signal = Signal(str)          # Error message

    def __init__(self, target_folders: List[str], parent: Optional[QObject] = None):
        super().__init__(parent)
        self.target_folders = target_folders
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        start_time = time.time()
        self.status_signal.emit("Initializing scanner...")

        scanner = FileScanner()
        all_files: List[FileInfo] = []

        total_scanned = 0
        def on_progress(count: int, filename: str):
            if not self._is_cancelled:
                self.progress_signal.emit(count, filename)

        for folder in self.target_folders:
            if self._is_cancelled:
                break
            self.status_signal.emit(f"Scanning folder: {folder}...")
            files = scanner.scan_path(folder, progress_callback=on_progress)
            all_files.extend(files)

        if self._is_cancelled:
            self.status_signal.emit("Scan cancelled.")
            return

        self.status_signal.emit("Analyzing duplicates and calculating content hashes...")
        duplicates = FileAnalyzer.find_duplicates(all_files)

        self.status_signal.emit("Identifying related project and topic clusters...")
        related_groups = FileAnalyzer.find_related_groups(all_files)

        total_bytes = sum(f.size_bytes for f in all_files)
        duration = time.time() - start_time

        report = ScanReport(
            scanned_folders=self.target_folders,
            files=all_files,
            duplicates=duplicates,
            related_groups=related_groups,
            total_size_bytes=total_bytes,
            scan_duration_seconds=duration,
        )

        self.status_signal.emit("Scan completed successfully.")
        self.finished_signal.emit(report)


class AIPlanWorker(QThread):
    """Background worker for generating AI organization recommendations using Qwen3:8b."""

    status_signal = Signal(str)
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, report: ScanReport, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.report = report

    def run(self):
        self.status_signal.emit("Connecting to local Ollama (qwen3:8b)...")
        generator = PlanGenerator()

        result = generator.generate_organization_plan(self.report)

        if result.get("success"):
            self.status_signal.emit("AI reasoning completed.")
            self.finished_signal.emit(result)
        else:
            err = result.get("error", "Unknown AI error occurred.")
            self.status_signal.emit(f"AI Error: {err}")
            self.error_signal.emit(err)


class OllamaCheckWorker(QThread):
    """Quick background worker to verify Ollama and model availability."""

    result_signal = Signal(bool, str)  # (is_ready, status_text)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

    def run(self):
        client = OllamaClient()
        if not client.check_connection(timeout=2.0):
            self.result_signal.emit(False, "Ollama: Offline (http://localhost:11434)")
            return

        if client.is_model_available("qwen3:8b", timeout=3.0):
            self.result_signal.emit(True, "Ollama: Online | qwen3:8b: Ready")
        else:
            self.result_signal.emit(False, "Ollama: Online | qwen3:8b: Not Found")


class AgentPromptWorker(QThread):
    """Background worker for executing end-to-end prompt queries with VaultAIAgent."""

    status_signal = Signal(str)
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, prompt: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.prompt = prompt

    def run(self):
        from core.ai.agent import VaultAIAgent

        agent = VaultAIAgent()
        try:
            result = agent.process_prompt(
                user_prompt=self.prompt,
                status_callback=lambda msg: self.status_signal.emit(msg),
            )
            self.finished_signal.emit(result)
        except Exception as e:
            self.error_signal.emit(str(e))
