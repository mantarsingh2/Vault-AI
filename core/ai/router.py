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
    r"\b(cpu|ram|memory|disk|storage|hardware|battery|specs?|system status|pc status|load|processes?|uptime|temperature|usage)\b",
    r"\b(how('?s| is) (my )?(laptop|pc|computer|system|machine))\b",
    r"\b(check (system|hardware|specs?|performance|health|resources?|stats?))\b",
    r"\b(show (me )?(cpu|ram|memory|disk|system|hardware|performance|stats?|resources?))\b",
    r"\b(system (stats?|health|info|information|monitor|report))\b",
    r"\b(resource (usage|status|monitor))\b",
    r"\b(what('?s| is) (running|using|consuming))\b",
    r"\b(is (my )?(system|pc|computer|laptop) (ok|healthy|running|working|fine))\b",
]

_FILE_PATTERNS = [
    r"\b(list files?|show files?|directory|dir|list dir|files? in|folder contents?|show folder)\b",
    r"\b(organize files?|find files?|search files?|locate files?)\b",
    r"\b(what files?|my files?|desktop files?|show desktop|desktop folder)\b",
    r"\b(show (me )?(the )?(files?|desktop|documents?|folder|directory))\b",
    r"\b(can you (show|list|display|check) (me )?(the )?(files?|folder|directory|desktop))\b",
    r"\b(what('?s| is) (in|on) (my )?(desktop|folder|directory|drive))\b",
    r"\b(files? (on|in|at) (my )?(desktop|home|documents?|project|folder))\b",
    r"\b(browse (files?|folder|directory|desktop))\b",
]

_SECURITY_PATTERNS = [
    r"\b(tpm|device security|cryptographic key|device key|security status|device identity|fingerprint)\b",
    r"\b(check (tpm|security|key|device|vault security))\b",
    r"\b(show (me )?(security|tpm|key|cryptographic))\b",
    r"\b(is (my )?(device|key|tpm|vault) (safe|secure|trusted|verified|ok|active|working))\b",
    r"\b(non.?exportable|key storage|ksp|cng|ecdsa|private key|public key)\b",
    r"\b(vault (security|key|identity|status))\b",
]

_CASUAL_PATTERNS = [
    r"^(hi|hello|hey|greetings|good morning|good evening|good afternoon|howdy|sup|yo)\b",
    r"\b(who are you|what are you|what can you do|help me|introduce yourself|about you)\b",
    r"^(thanks?|thank you|cool|awesome|great|ok|okay|nice|perfect|got it|sounds good)\b",
    r"^(bye|goodbye|see you|later)\b",
]

_COMPLEX_PATTERNS = [
    r"\b(setup|install|configure|plan|build|deploy|develop|implement)\b",
    r"\b(multi.?step|step by step|workflow|pipeline)\b",
    r"\b(help me (create|build|setup|install|configure|develop|make|implement))\b",
    r"\b(environment|scaffold|bootstrap|how to (create|build|setup|install))\b",
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
