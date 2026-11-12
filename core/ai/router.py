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

_FILE_PATTERNS = [
    r"\b(file|files|folder|folders|directory|directories|dir)\b",
    r"\b(duplicate|duplicates|wasted space)\b",
    r"\b(organize|organization|cleanup|clean up|sort|categorize)\b",
    r"\b(which file|which files|list files|show files|find files|search files)\b",
    r"\b(pdf|docx?|xlsx?|txt|png|jpe?g|archive|zip)\b",
    r"\b(downloads?|documents?|pictures?)\b",
]

_CASUAL_PATTERNS = [
    r"^(hi|hello|hey|greetings|good morning|good evening|good afternoon|howdy)\b",
    r"\b(who are you|what are you|what can you do|help me|introduce yourself)\b",
    r"^(thanks|thank you|cool|awesome|great)\b",
]

_COMPLEX_PATTERNS = [
    r"\b(setup|install|configure|plan|build|deploy|multi-step|develop|environment)\b",
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

    # 4. File Operations (only when file-specific keywords are used)
    for pattern in _FILE_PATTERNS:
        if re.search(pattern, query):
            return Intent.FILE_OPERATION

    # 5. Complex Multi-Step Planning
    for pattern in _COMPLEX_PATTERNS:
        if re.search(pattern, query):
            return Intent.COMPLEX_TASK

    return Intent.GENERAL_QUERY
