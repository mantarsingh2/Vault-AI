"""User intent classification and query routing for Vault AI."""

from __future__ import annotations

import re
from enum import Enum


class Intent(str, Enum):
    SYSTEM_STATUS = "system_status"
    FILE_OPERATION = "file_operation"
    SECURITY_CHECK = "security_check"
    CASUAL_CHAT = "casual_chat"
    COMPLEX_TASK = "complex_task"
    GENERAL_QUERY = "general_query"
    CONFIRM_ACTION = "confirm_action"


# Keyword / Regex patterns for rule-based fast classification
_CONFIRM_PATTERNS = [
    r"^(yes|yep|yeah|do it|proceed|go ahead|kardo|kar do|sure|ok|okay|move them|organize them)\b",
]

_SECURITY_PATTERNS = [
    r"\b(tpm|device security|cryptographic key|device key|security status|device identity|fingerprint)\b",
]

_SYSTEM_PATTERNS = [
    r"\b(cpu|ram|memory|disk|storage|hardware|battery|specs|system status|pc status|load|processes)\b",
    r"\b(how('?s| is) my (laptop|pc|computer|system))\b",
    r"\b(check (system|hardware|specs|performance))\b",
]

_COMPLEX_PATTERNS = [
    r"\b(plan|create a plan|make a plan|step[- ]by[- ]step|roadmap|architecture|workflow|design|multi-step|develop|setup|install|configure|build|deploy|environment)\b",
]

# Actions that directly manipulate the filesystem — always FILE_OPERATION
_FILE_ACTION_PATTERNS = [
    r"\b(create|make|mkdir|new)\s+(a\s+)?(folder|directory|dir|file)\b",
    r"\b(create|make|new)\s+(folder|directory|dir|file)\s+(at|in|to|named?|called?)\b",
    r"\b(folder|directory)\s+(to|at|in|path)\b",
    r"\b(delete|remove|rename|move|copy)\s+(the\s+)?(folder|directory|file|files)\b",
    r"\bdelete\s+file\b",
    r"\bmove\s+files?\b",
]

_FILE_PATTERNS = [
    r"\b(duplicate|duplicates|wasted space)\b",
    r"\b(organize|organization|cleanup|clean up|sort|categorize)\b",
    r"\b(list|show|find|search|scan|display|which|where)\s+.*?\b(file|files|folder|folders|directory|directories|dir)\b",
    r"\b(which file|which files|list files|show files|find files|search files|scan files)\b",
    r"\b(delete|remove|move|copy|rename)\s+.*?\b(file|files|folder|folders)\b",
    r"\b(file|files|folder|folders|directory|directories|dir)\b",
]

_CASUAL_PATTERNS = [
    r"^(hi|hello|hey|hlo|heya|hola|howdy|yo|sup|greetings|good morning|good evening|good afternoon)\b",
    r"\b(who are you|what are you|what can you do|help me|introduce yourself)\b",
    r"^(thanks|thank you|cool|awesome|great)\b",
]


def classify_intent(text: str) -> Intent:
    """Classify user query into primary intent category."""
    query = text.strip().lower()
    if not query:
        return Intent.CASUAL_CHAT

    # 0. Check for confirmations first
    for pattern in _CONFIRM_PATTERNS:
        if re.search(pattern, query):
            return Intent.CONFIRM_ACTION

    # 1. Casual Greetings / Introduction
    for pattern in _CASUAL_PATTERNS:
        if re.search(pattern, query):
            return Intent.CASUAL_CHAT

    # 2. Security Check
    for pattern in _SECURITY_PATTERNS:
        if re.search(pattern, query):
            return Intent.SECURITY_CHECK

    # 3. System Monitoring
    for pattern in _SYSTEM_PATTERNS:
        if re.search(pattern, query):
            return Intent.SYSTEM_STATUS

    # 4a. Direct filesystem actions — always FILE_OPERATION (before complex check)
    for pattern in _FILE_ACTION_PATTERNS:
        if re.search(pattern, query):
            return Intent.FILE_OPERATION

    # 4b. Complex Multi-Step Planning (e.g. "plan to build ...", "step-by-step ...")
    for pattern in _COMPLEX_PATTERNS:
        if re.search(pattern, query):
            # If the user specifically asks to organize/clean up files on disk, prefer file operation
            if any(re.search(fp, query) for fp in [r"\b(duplicate|duplicates)\b", r"\b(organize|cleanup|clean up|sort)\b"]):
                return Intent.FILE_OPERATION
            return Intent.COMPLEX_TASK

    # 5. General File Operations (listing, scanning, etc.)
    for pattern in _FILE_PATTERNS:
        if re.search(pattern, query):
            return Intent.FILE_OPERATION

    return Intent.GENERAL_QUERY
