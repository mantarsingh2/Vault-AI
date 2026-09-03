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


# Keyword / Regex patterns for rule-based fast classification
_SYSTEM_PATTERNS = [
    r"\b(cpu|ram|memory|disk|storage|hardware|battery|specs|system status|pc status|load|processes)\b",
    r"\b(how('?s| is) my (laptop|pc|computer|system))\b",
    r"\b(check (system|hardware|specs|performance))\b",
]

_FILE_PATTERNS = [
    r"\b(list files|show files|directory|dir|list dir|files in folder|folder contents|show folder)\b",
    r"\b(organize files|find files|search files)\b",
]

_SECURITY_PATTERNS = [
    r"\b(tpm|device security|cryptographic key|device key|security status|device identity|fingerprint)\b",
]

_CASUAL_PATTERNS = [
    r"^(hi|hello|hey|greetings|good morning|good evening|good afternoon|howdy)\b",
    r"\b(who are you|what are you|what can you do|help me|introduce yourself)\b",
    r"^(thanks|thank you|cool|awesome|great|ok|okay)\b",
]

_COMPLEX_PATTERNS = [
    r"\b(setup|install|configure|plan|build|deploy|multi-step|develop|environment)\b",
]


def classify_intent(text: str) -> Intent:
    """Classify user query into primary intent category."""
    query = text.strip().lower()
    if not query:
        return Intent.CASUAL_CHAT

    # 1. Security Check
    for pattern in _SECURITY_PATTERNS:
        if re.search(pattern, query):
            return Intent.SECURITY_CHECK

    # 2. System Monitoring
    for pattern in _SYSTEM_PATTERNS:
        if re.search(pattern, query):
            return Intent.SYSTEM_STATUS

    # 3. File Operations
    for pattern in _FILE_PATTERNS:
        if re.search(pattern, query):
            return Intent.FILE_OPERATION

    # 4. Casual Greetings / Introduction
    for pattern in _CASUAL_PATTERNS:
        if re.search(pattern, query):
            return Intent.CASUAL_CHAT

    # 5. Complex Multi-Step Planning
    for pattern in _COMPLEX_PATTERNS:
        if re.search(pattern, query):
            return Intent.COMPLEX_TASK

    return Intent.GENERAL_QUERY
