"""Data models for File Management in Vault AI."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FileInfo:
    """Represents metadata for a single discovered file."""
    path: str
    name: str
    extension: str
    size_bytes: int
    modified_time: float
    created_time: float
    category: str
    file_hash: Optional[str] = None

    @property
    def human_size(self) -> str:
        """Format byte size into human readable string."""
        size = float(self.size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0 or unit == "TB":
                return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024.0
        return f"{size:.2f} B"

    @property
    def modified_datetime_str(self) -> str:
        """Formatted modification timestamp."""
        try:
            return datetime.fromtimestamp(self.modified_time).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "Unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "human_size": self.human_size,
            "modified_time": self.modified_datetime_str,
            "category": self.category,
            "hash": self.file_hash,
        }


@dataclass
class DuplicateGroup:
    """Represents a set of duplicate files sharing identical content hash."""
    file_hash: str
    size_bytes: int
    files: List[FileInfo] = field(default_factory=list)

    @property
    def human_size(self) -> str:
        size = float(self.size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024.0
        return f"{size:.2f} GB"

    @property
    def potential_savings_bytes(self) -> int:
        """Bytes that can be saved if only 1 copy is kept."""
        if len(self.files) <= 1:
            return 0
        return self.size_bytes * (len(self.files) - 1)

    @property
    def potential_savings_human(self) -> str:
        savings = float(self.potential_savings_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if savings < 1024.0:
                return f"{savings:.2f} {unit}" if unit != "B" else f"{int(savings)} B"
            savings /= 1024.0
        return f"{savings:.2f} GB"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hash": self.file_hash,
            "size_bytes": self.size_bytes,
            "human_size": self.human_size,
            "count": len(self.files),
            "potential_savings": self.potential_savings_human,
            "files": [f.path for f in self.files],
        }


@dataclass
class RelatedFileGroup:
    """Represents a group of files sharing deterministic project/topic relationships."""
    group_name: str
    reason: str
    files: List[FileInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_name": self.group_name,
            "reason": self.reason,
            "count": len(self.files),
            "files": [f.name for f in self.files],
        }


@dataclass
class OrganizationSuggestion:
    """Represents an AI-generated organization recommendation."""
    original_path: str
    suggested_destination: str
    category: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_path": self.original_path,
            "suggested_destination": self.suggested_destination,
            "category": self.category,
            "reason": self.reason,
        }


@dataclass
class ScanReport:
    """Full summary report of a filesystem scan."""
    scanned_folders: List[str]
    files: List[FileInfo] = field(default_factory=list)
    duplicates: List[DuplicateGroup] = field(default_factory=list)
    related_groups: List[RelatedFileGroup] = field(default_factory=list)
    total_size_bytes: int = 0
    scan_duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def human_total_size(self) -> str:
        size = float(self.total_size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024.0
        return f"{size:.2f} TB"

    @property
    def total_potential_savings_bytes(self) -> int:
        return sum(dup.potential_savings_bytes for dup in self.duplicates)

    @property
    def total_potential_savings_human(self) -> str:
        savings = float(self.total_potential_savings_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if savings < 1024.0:
                return f"{savings:.2f} {unit}" if unit != "B" else f"{int(savings)} B"
            savings /= 1024.0
        return f"{savings:.2f} GB"
