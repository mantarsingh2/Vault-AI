"""Safe filesystem scanner for discovering files and metadata in Vault AI."""

from pathlib import Path
from typing import Callable, Dict, Generator, List, Optional, Set
import os
import time

from .models import FileInfo


# Categorization map
EXTENSION_CATEGORIES: Dict[str, str] = {
    # Documents
    ".pdf": "Document",
    ".docx": "Document",
    ".doc": "Document",
    ".txt": "Document",
    ".rtf": "Document",
    ".odt": "Document",
    ".xlsx": "Spreadsheet",
    ".xls": "Spreadsheet",
    ".csv": "Spreadsheet",
    ".pptx": "Presentation",
    ".ppt": "Presentation",
    # Images
    ".png": "Image",
    ".jpg": "Image",
    ".jpeg": "Image",
    ".gif": "Image",
    ".svg": "Image",
    ".webp": "Image",
    ".bmp": "Image",
    ".ico": "Image",
    # Code & Development
    ".py": "Code",
    ".js": "Code",
    ".ts": "Code",
    ".html": "Code",
    ".css": "Code",
    ".json": "Data/Code",
    ".xml": "Data/Code",
    ".yaml": "Data/Code",
    ".yml": "Data/Code",
    ".sql": "Data/Code",
    ".cpp": "Code",
    ".c": "Code",
    ".java": "Code",
    ".rs": "Code",
    # Archives
    ".zip": "Archive",
    ".tar": "Archive",
    ".gz": "Archive",
    ".rar": "Archive",
    ".7z": "Archive",
    # Audio & Video
    ".mp3": "Audio",
    ".wav": "Audio",
    ".m4a": "Audio",
    ".mp4": "Video",
    ".mkv": "Video",
    ".mov": "Video",
    ".avi": "Video",
    # Executables / Installers
    ".exe": "Executable",
    ".msi": "Executable",
}

# Directories to skip to protect system files and avoid bloat
IGNORED_DIR_NAMES: Set[str] = {
    ".git",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".env",
    "AppData",
    ".cache",
    "$RECYCLE.BIN",
    "System Volume Information",
}


def get_file_category(extension: str) -> str:
    """Classify file by extension."""
    return EXTENSION_CATEGORIES.get(extension.lower(), "Other")


class FileScanner:
    """Scans authorized directory paths safely and extracts deterministic metadata."""

    def __init__(self, max_depth: int = 10):
        self.max_depth = max_depth

    def scan_path(
        self,
        folder_path: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> List[FileInfo]:
        """Scan a folder recursively and collect FileInfo objects.

        Args:
            folder_path: Root folder path to scan.
            progress_callback: Optional callback(file_count, current_file_name).

        Returns:
            List[FileInfo]: Discovered files.
        """
        root = Path(folder_path).resolve()
        if not root.exists() or not root.is_dir():
            return []

        results: List[FileInfo] = []
        count = 0

        for root_dir, dirs, files in os.walk(str(root), followlinks=False):
            # Exclude ignored directory names in-place to prevent traversing them
            dirs[:] = [d for d in dirs if d not in IGNORED_DIR_NAMES and not d.startswith(".")]

            for filename in files:
                # Skip temporary / hidden files
                if filename.startswith("~$") or filename.startswith("."):
                    continue

                full_path = Path(root_dir) / filename

                try:
                    stat = full_path.stat()
                    # Skip symlinks if they point outside or are broken
                    if full_path.is_symlink():
                        continue

                    ext = full_path.suffix.lower()
                    category = get_file_category(ext)

                    info = FileInfo(
                        path=str(full_path),
                        name=filename,
                        extension=ext,
                        size_bytes=stat.st_size,
                        modified_time=stat.st_mtime,
                        created_time=stat.st_ctime,
                        category=category,
                    )
                    results.append(info)
                    count += 1

                    if progress_callback and (count % 10 == 0 or count == 1):
                        progress_callback(count, filename)

                except (PermissionError, OSError, FileNotFoundError):
                    # Gracefully ignore locked, inaccessible or rapidly deleted files
                    continue

        if progress_callback:
            progress_callback(count, "Scan complete")

        return results
