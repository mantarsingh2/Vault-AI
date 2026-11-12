"""File Management package for Vault AI."""

from .analyzer import FileAnalyzer
from .hasher import calculate_file_hash
from .models import (
    DuplicateGroup,
    FileInfo,
    OrganizationSuggestion,
    RelatedFileGroup,
    ScanReport,
)
from .plan_generator import PlanGenerator
from .scanner import FileScanner, get_file_category
from .security import SecurityManager

__all__ = [
    "FileInfo",
    "DuplicateGroup",
    "RelatedFileGroup",
    "OrganizationSuggestion",
    "ScanReport",
    "SecurityManager",
    "calculate_file_hash",
    "FileScanner",
    "FileAnalyzer",
    "PlanGenerator",
    "get_file_category",
]
