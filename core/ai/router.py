
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


# 1. Confirmation patterns
_CONFIRM_PATTERNS = [
    r"^(yes|yep|yeah|do it|proceed|go ahead|kardo|kar do|sure|ok|okay|move them|organize them)\b",
]


# 2. Security patterns
_SECURITY_PATTERNS = [
    r"\b(tpm|device security|cryptographic key|device key|security status|device identity|fingerprint)\b",
]


# 3. System monitoring patterns
_SYSTEM_PATTERNS = [
    r"\b(cpu|ram|memory|disk|storage|hardware|battery|specs|system status|pc status|load|processes)\b",
    r"\b(how('?s| is) my (laptop|pc|computer|system))\b",
    r"\b(check (system|hardware|specs|performance))\b",
]


# 4. Project creation and software development patterns
_PROJECT_PATTERNS = [
    r"\b(create|build|develop|implement|scaffold|generate|design)\b.{0,100}\b(project|application|app|software|program|codebase|website|calculator)\b",
    r"\b(project|application|app|software|program|codebase|website|calculator)\b.{0,100}\b(create|build|develop|implement|scaffold|generate|design)\b",
    r"\b(write|develop|implement|code)\b.{0,60}\b(python|java|javascript|c\+\+|application|program|module)\b",
    r"\b(generate|create|design)\b.{0,60}\b(execution plan|implementation plan|development plan|project plan)\b",
]


# 5. Complex multi-step task patterns
_COMPLEX_PATTERNS = [
    r"\b(setup|install|configure|plan|build|deploy|multi-step|develop|environment|integrate|automate)\b",
]


# 6. Existing file management patterns
_FILE_PATTERNS = [
    r"\b(file|files|folder|folders|directory|directories|dir)\b",
    r"\b(duplicate|duplicates|wasted space)\b",
    r"\b(organize|organization|cleanup|clean up|sort|categorize)\b",
    r"\b(which file|which files|list files|show files|find files|search files)\b",
    r"\b(pdf|docx?|xlsx?|txt|png|jpe?g|archive|zip)\b",
    r"\b(downloads?|documents?|pictures?)\b",
]


# 7. Casual conversation patterns
_CASUAL_PATTERNS = [
    r"^(hi|hello|hey|greetings|good morning|good evening|good afternoon|howdy)\b",
    r"\b(who are you|what are you|what can you do|help me|introduce yourself)\b",
    r"^(thanks|thank you|cool|awesome|great)\b",
]


def classify_intent(text: str) -> Intent:
    """
    Classify user queries into Vault AI intent categories.

    Project creation and software development requests are
    prioritized over existing file-management keywords.
    """

    query = text.strip().lower()

    if not query:
        return Intent.CASUAL_CHAT

    # 1. Confirm pending actions
    for pattern in _CONFIRM_PATTERNS:
        if re.search(pattern, query):
            return Intent.CONFIRM_ACTION

    # 2. Casual conversation
    for pattern in _CASUAL_PATTERNS:
        if re.search(pattern, query):
            return Intent.CASUAL_CHAT

    # 3. Security checks
    for pattern in _SECURITY_PATTERNS:
        if re.search(pattern, query):
            return Intent.SECURITY_CHECK

    # 4. System monitoring
    for pattern in _SYSTEM_PATTERNS:
        if re.search(pattern, query):
            return Intent.SYSTEM_STATUS

    # 5. Project creation and software development
    for pattern in _PROJECT_PATTERNS:
        if re.search(pattern, query):
            return Intent.COMPLEX_TASK

    # 6. Other complex tasks
    for pattern in _COMPLEX_PATTERNS:
        if re.search(pattern, query):
            return Intent.COMPLEX_TASK

    # 7. Existing file management
    for pattern in _FILE_PATTERNS:
        if re.search(pattern, query):
            return Intent.FILE_OPERATION

    # 8. General knowledge queries
    return Intent.GENERAL_QUERY
