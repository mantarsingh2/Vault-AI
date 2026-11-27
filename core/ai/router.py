"""User intent classification and query routing for Vault AI."""

from __future__ import annotations

import re
from enum import Enum


class Intent(str, Enum):
    SYSTEM_STATUS   = "system_status"
    FILE_OPERATION  = "file_operation"
    SECURITY_CHECK  = "security_check"
    CASUAL_CHAT     = "casual_chat"
    COMPLEX_TASK    = "complex_task"
    GENERAL_QUERY   = "general_query"
    CONFIRM_ACTION  = "confirm_action"


# ---------------------------------------------------------------------------
# Pattern groups — ordered by priority inside classify_intent()
# ---------------------------------------------------------------------------

_CONFIRM_PATTERNS = [
    r"^(yes|yep|yeah|do it|proceed|go ahead|kardo|kar do|sure|ok|okay|move them|organize them)\b",
]

_SECURITY_PATTERNS = [
    r"\b(tpm|device security|cryptographic key|device key|security status|device identity|fingerprint)\b",
    r"\b(audit|verify|check|inspect|test|implement)\b.*?\b(security|antivirus|defender|firewall|bitlocker|encryption|protection)\b",
    r"\b(can you do it and check|check (it )?w(h)?ether it (is )?already implemented|is security (implemented|enabled|active))\b",
    r"\b(scan\s+(for\s+)?(malware|virus|threats?)|(malware|virus|defender)\s+scan)\b",
    r"\b(run (a )?(malware|virus|security|defender) scan|scan (my )?(laptop|pc|computer|system) for (malware|viruses))\b",
    r"\b(check firewall|firewall status|firewall profile|antivirus status|defender status|bitlocker status)\b",
    # Emergency Kill-Switch & Air-Gap Containment
    r"\b(disconnect|cut|block|stop|kill|disable|shut(?:down)?)\b.*?\b(wireless|wifi|wi-fi|bluetooth|network|connections?|air[- ]?gap)\b",
    r"\b(air[- ]?gap\s+(my\s+)?(laptop|pc|computer|system)|kill[- ]?switch|emergency\s+stop)\b",
    r"\b(restore|re-?enable|reconnect|enable|bring back)\b.*?\b(wireless|wifi|wi-fi|bluetooth|network|connections?)\b",
    # Attack Detection, Threat Hunting & SOC Analyst
    r"\b(detect|hunt|check|stop|handle|triage)\b.*?\b(attacks?|intrusions?|hackers?|threats?|c2|reverse\s+shell|payload|suspicious\s+activity)\b",
    r"\b(is\s+(an\s+)?attacker\s+attacking|handle\s+attack|stop\s+all\s+wireless|cut\s+off\s+wireless)\b",
    r"\b(threat\s+hunt|threat\s+hunting|attack\s+detection|intrusion\s+detection|soc\s+analyst)\b",
]

_SYSTEM_PATTERNS = [
    r"\b(cpu|ram|memory|disk|storage|hardware|battery|specs|system status|pc status|load|processes)\b",
    r"\b(how('?s| is) my (laptop|pc|computer|system))\b",
    r"\b(check (system|hardware|specs|performance))\b",
]

# Direct filesystem action patterns — checked BEFORE complex to avoid mis-routing
# "create a folder", "make a file", "delete the folder", "move X to Y", etc.
_FILE_ACTION_PATTERNS = [
    # create
    r"\b(create|make|mkdir|new|add|touch)\s+(a\s+)?(new\s+)?(folder|directory|dir|file)\b",
    r"\b(folder|directory|file)\s+(named?|called?|at|in|to)\b",
    # delete / remove
    r"\b(delete|remove|trash|erase|wipe)\s+(the\s+)?(folder|directory|file|dir)\b",
    r"\b(delete|remove|trash|erase|wipe)\s+[A-Za-z]:[/\\]",   # direct path
    # move / cut-paste
    r"\b(move|cut|transfer|relocate|mv)\s+.{2,50}\s+to\b",
    r"\bcut\s+and\s+paste\b",
    # copy / paste
    r"\b(copy|cp|clone|duplicate)\s+.{2,50}\s+to\b",
    r"\bcopy\s+and\s+paste\b",
    r"\bpaste\s+(a\s+)?copy\b",
    # rename
    r"\b(rename|rn)\b",
    r"\bchange\s+(the\s+)?name\b",
    # list / open
    r"\b(list|show|display|ls|dir)\s+(files?|folders?|contents?|everything)\b",
    r"\bshow\s+in\s+explorer\b",
    r"\bopen\s+(the\s+)?(folder|directory|file)\b",
    # search / find
    r"\b(find|search|locate|look\s+for)\s+(files?|folders?|a\s+file)\b",
    r"\bwhere\s+is\b",
]

# Heavier file-related patterns (scan, organize, duplicates)
_FILE_PATTERNS = [
    r"\b(duplicate|duplicates|wasted space)\b",
    r"\b(organize|organization|cleanup|clean up|sort|categorize)\b",
    r"\b(list|show|find|search|scan|display|which|where)\s+.*?\b(file|files|folder|folders|directory|directories|dir)\b",
    r"\b(which file|which files|list files|show files|find files|search files|scan files)\b",
    r"\b(delete|remove|move|copy|rename)\s+.*?\b(file|files|folder|folders)\b",
    r"\b(file|files|folder|folders|directory|directories|dir)\b",
]

_COMPLEX_PATTERNS = [
    r"\b(plan|create a plan|make a plan|step[- ]by[- ]step|roadmap|architecture|workflow"
    r"|design|multi[- ]step|develop|setup|install|configure|build|deploy|environment)\b",
]

_CASUAL_PATTERNS = [
    r"^(hi|hello|hey|hlo|heya|hola|howdy|yo|sup|greetings|good morning|good evening|good afternoon)\b",
    r"\b(who are you|what are you|what can you do|help me|introduce yourself)\b",
    r"^(thanks|thank you|cool|awesome|great)\b",
]


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def classify_intent(text: str) -> Intent:
    """Classify user query into the primary intent category."""
    query = text.strip().lower()
    if not query:
        return Intent.CASUAL_CHAT

    # 0 — confirmation shorthand
    for pat in _CONFIRM_PATTERNS:
        if re.search(pat, query):
            return Intent.CONFIRM_ACTION

    # 1 — casual / greeting
    for pat in _CASUAL_PATTERNS:
        if re.search(pat, query):
            return Intent.CASUAL_CHAT

    # 2 — security / TPM
    for pat in _SECURITY_PATTERNS:
        if re.search(pat, query):
            return Intent.SECURITY_CHECK

    # 3 — system hardware stats
    for pat in _SYSTEM_PATTERNS:
        if re.search(pat, query):
            return Intent.SYSTEM_STATUS

    # 4 — direct filesystem ACTIONS (create/delete/move/copy/rename/list/search/open)
    #     Must come before COMPLEX so "create a folder" is never mis-routed
    for pat in _FILE_ACTION_PATTERNS:
        if re.search(pat, query):
            return Intent.FILE_OPERATION

    # 5 — complex multi-step planning
    for pat in _COMPLEX_PATTERNS:
        if re.search(pat, query):
            # Organize/duplicate queries are still file ops
            if any(re.search(fp, query) for fp in [
                r"\b(duplicate|duplicates)\b",
                r"\b(organize|cleanup|clean up|sort)\b",
            ]):
                return Intent.FILE_OPERATION
            return Intent.COMPLEX_TASK

    # 6 — general file scan / browse
    for pat in _FILE_PATTERNS:
        if re.search(pat, query):
            return Intent.FILE_OPERATION

    return Intent.GENERAL_QUERY
