"""Deterministic streaming file hasher for duplicate detection in Vault AI."""

import hashlib
from pathlib import Path
from typing import Optional


def calculate_file_hash(file_path: str, chunk_size: int = 65536) -> Optional[str]:
    """Calculate SHA-256 hash of a file using streaming chunks.

    Args:
        file_path: Absolute path to the file.
        chunk_size: Block size in bytes (default 64KB).

    Returns:
        Hexadecimal SHA-256 string, or None if the file cannot be read.
    """
    path = Path(file_path)
    if not path.is_file():
        return None

    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except (PermissionError, OSError, FileNotFoundError):
        return None
