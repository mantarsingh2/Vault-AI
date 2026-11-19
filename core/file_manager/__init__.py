"""File Management package for Vault AI."""

from .analyzer import FileAnalyzer
from .executor import (
    create_folder,
    delete_item,
    execute_organization_plan,
    move_item,
    parse_and_execute_file_action,
    parse_file_action,
    rename_item,
)
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
    "create_folder",
    "rename_item",
    "delete_item",
    "move_item",
    "parse_file_action",
    "parse_and_execute_file_action",
    "execute_organization_plan",
]
