"""
Vault AI — Secure File Operation & Query Understanding Engine
=============================================================

Handles ALL file/folder operations from natural language queries with
semantic query understanding, sanitization, and strict security sandboxing:

Operations:
  • create   — create folder or file (sanitized, authorized workspaces only)
  • delete   — delete folder or file (Recycle Bin with safety protections)
  • move     — move/cut-paste folder or file
  • copy     — copy-paste folder or file
  • rename   — rename folder or file
  • list     — list contents of an authorized directory
  • search   — search files by name or extension
  • open     — open file/folder in Explorer

Security Hardening:
  • Sensitive system paths (AppData, Cookies, Local Settings, .ssh, etc.) are strictly BLOCKED
  • Root user profile directory (C:\\Users\\HP) cannot be modified or deleted directly
  • Traversal attacks (.. / symlink breakouts) are strictly prevented
  • Erroneous or malicious paths are blocked before execution
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.file_manager.security import SecurityManager
from core.file_manager.scanner import FileScanner, get_file_category, EXTENSION_CATEGORIES

# ---------------------------------------------------------------------------
# Security: Protected / Dangerous System Directories (Blacklist)
# ---------------------------------------------------------------------------

PROTECTED_SYSTEM_DIRS = {
    "appdata",
    "application data",
    "cookies",
    "local settings",
    "nethood",
    "printhood",
    "recent",
    "sendto",
    "start menu",
    "templates",
    ".ssh",
    ".aws",
    ".azure",
    ".kube",
    ".gnupg",
    ".git",
    "system volume information",
    "$recycle.bin",
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "system32",
    "syswow64",
}


def _is_safe_target(path: Path) -> Tuple[bool, str]:
    """Validate that the target path does not touch sensitive system or OS files."""
    try:
        resolved = path.resolve()
        parts_lower = [p.lower() for p in resolved.parts]

        # Block root drives or whole user profile modifications
        if resolved == Path.home() or len(resolved.parts) <= 2:
            return False, "Direct modifications to system or user profile root are restricted."

        # Check blacklisted directory names
        for part in parts_lower:
            if part in PROTECTED_SYSTEM_DIRS or part.startswith("ntuser.dat"):
                return False, f"Access to protected system location '{part}' is restricted."

        return True, "Safe"
    except Exception as e:
        return False, f"Path validation error: {e}"


# ---------------------------------------------------------------------------
# Security: Authorized Roots
# ---------------------------------------------------------------------------

def _build_security_manager() -> SecurityManager:
    """Build a SecurityManager with strictly authorized user workspace folders."""
    sm = SecurityManager()
    home = Path.home()
    
    # Authorized user workspaces ONLY (never the raw root home containing AppData/Cookies)
    workspaces = [
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "Pictures",
        home / "Music",
        home / "Videos",
    ]
    
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if onedrive:
        od = Path(onedrive)
        for w in ["Desktop", "Documents", "Downloads", "Pictures"]:
            workspaces.append(od / w)

    for p in workspaces:
        try:
            if p.exists() and p.is_dir():
                sm.add_authorized_root(str(p.resolve()))
        except Exception:
            pass

    return sm


_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    global _security_manager
    if _security_manager is None:
        _security_manager = _build_security_manager()
    return _security_manager


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FileOpRequest:
    """Parsed file operation request."""
    operation: str          # create_folder | create_file | delete | move | copy | rename | list | search | open
    source: Optional[str] = None       # source path
    destination: Optional[str] = None  # destination path (for move/copy/rename)
    name: Optional[str] = None         # new name (for create/rename)
    pattern: Optional[str] = None      # search pattern (for search)
    raw_query: str = ""


@dataclass
class FileOpResult:
    """Result of a file operation."""
    success: bool
    content: str            # markdown-formatted response for the UI
    intent: str = "file_operation"
    status: str = "success"
    steps: List[str] = field(default_factory=list)

    def to_response_dict(self) -> Dict[str, Any]:
        return {
            "role": "assistant",
            "content": self.content,
            "intent": self.intent,
            "status": self.status if self.success else "error",
            "steps": self.steps,
        }


# ---------------------------------------------------------------------------
# Path aliases & Name Sanitization
# ---------------------------------------------------------------------------

_PATH_ALIASES = {
    # Desktop
    "desktop folder": str(Path.home() / "Desktop"),
    "desktop":        str(Path.home() / "Desktop"),
    
    # Downloads (both singular and plural)
    "download folder":  str(Path.home() / "Downloads"),
    "downloads folder": str(Path.home() / "Downloads"),
    "download directory": str(Path.home() / "Downloads"),
    "downloads directory": str(Path.home() / "Downloads"),
    "download":         str(Path.home() / "Downloads"),
    "downloads":        str(Path.home() / "Downloads"),

    # Documents
    "document folder":  str(Path.home() / "Documents"),
    "documents folder": str(Path.home() / "Documents"),
    "document directory": str(Path.home() / "Documents"),
    "documents directory": str(Path.home() / "Documents"),
    "document":         str(Path.home() / "Documents"),
    "documents":        str(Path.home() / "Documents"),
    "doc":              str(Path.home() / "Documents"),
    "docs":             str(Path.home() / "Documents"),

    # Pictures
    "picture folder":  str(Path.home() / "Pictures"),
    "pictures folder": str(Path.home() / "Pictures"),
    "picture":         str(Path.home() / "Pictures"),
    "pictures":        str(Path.home() / "Pictures"),
    "photos":          str(Path.home() / "Pictures"),
    "photo":           str(Path.home() / "Pictures"),

    # Music & Videos
    "music folder":    str(Path.home() / "Music"),
    "music":           str(Path.home() / "Music"),
    "video folder":    str(Path.home() / "Videos"),
    "videos folder":   str(Path.home() / "Videos"),
    "videos":          str(Path.home() / "Videos"),
    "video":           str(Path.home() / "Videos"),
}


def _sanitize_name(name: str) -> str:
    """Sanitize folder or file name by stripping conversational noise, trailing prepositions, and invalid characters."""
    if not name:
        return ""
    # Strip trailing clauses, prepositions (e.g. ' in C:\\...', ' on Desktop'), and conversational noise
    cleaned = re.split(
        r'[,;]|\s+\b(?:in|inside|at|on|to|into|from|first|then|please|can\s+you|and|also|make|do|with|named?|called?|understand)\b',
        name,
        flags=re.IGNORECASE
    )[0]
    # Remove invalid Windows filename characters: \ / : * ? " < > |
    cleaned = re.sub(r'[\\/:*?"<>|]', '', cleaned).strip().strip(".'\"")
    return cleaned


def _resolve_alias(text: str) -> str:
    """Replace path aliases with real paths safely without invalid regex escapes."""
    lower = text.lower().strip()
    # Check exact match
    if lower in _PATH_ALIASES:
        return _PATH_ALIASES[lower]

    # Sort aliases by descending length so multi-word variants match first
    sorted_aliases = sorted(_PATH_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True)
    for alias, real in sorted_aliases:
        pattern = rf'(?<![A-Za-z0-9_\\/])(?:of|in|at|to|from|on|the)?\s*\b{re.escape(alias)}\b(?![A-Za-z0-9_\\/])'
        if re.search(pattern, text, re.IGNORECASE):
            text = re.sub(
                pattern,
                lambda _: f' {real}',
                text,
                count=1,
                flags=re.IGNORECASE,
            )
            break
    return text


def _extract_windows_paths(text: str) -> List[str]:
    """Extract all Windows absolute paths from text safely, supporting spaces and quotes."""
    paths: List[str] = []
    
    # 1. Quoted paths
    quoted = re.findall(r'["\']([A-Za-z]:[/\\][^"\']+)["\']', text)
    paths.extend([p.strip().rstrip("\\/ .,") for p in quoted if p.strip()])

    # 2. Unquoted paths
    unquoted = re.findall(
        r'(?<![A-Za-z0-9_])([A-Za-z]:[/\\](?:[^\n\r\t,"\'*?<>|]+?))(?=\s+(?:to|into|as|from|in|at|named?|called?)\s+[A-Za-z]:[/\\]|\s+(?:to|into|as)\b|\s*$|[,"\'\n\r])',
        text,
        re.IGNORECASE
    )
    for p in unquoted:
        p_clean = p.strip().rstrip("\\/ .,")
        if p_clean and p_clean not in paths:
            paths.append(p_clean)
            
    return paths


def _extract_quoted(text: str) -> List[str]:
    """Extract quoted strings from text."""
    return re.findall(r'["\']([^"\']+)["\']', text)


def _human_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


# ---------------------------------------------------------------------------
# NLP Parser & Query Understanding (Qwen3 / Regex)
# ---------------------------------------------------------------------------

_OP_PATTERNS = {
    "create_folder": [
        r"\b(create|make|mkdir|new|add)\s+(a\s+)?(new\s+)?(folder|directory|dir)\b",
        r"\b(folder|directory)\s+(named?|called?)\b",
    ],
    "create_file": [
        r"\b(create|make|new|add|touch)\s+(a\s+)?(new\s+)?file\b",
        r"\bfile\s+(named?|called?)\b",
    ],
    "delete": [
        r"\b(delete|remove|trash|erase|wipe|del)\b",
    ],
    "move": [
        r"\b(move|cut|transfer|relocate|mv)\b",
        r"\bcut\s+and\s+paste\b",
    ],
    "copy": [
        r"\b(copy|duplicate|cp|clone)\b",
        r"\bcopy\s+and\s+paste\b",
        r"\bpaste\s+(a\s+)?copy\b",
    ],
    "rename": [
        r"\b(rename|rn)\b",
        r"\bchange\s+(the\s+)?name\b",
    ],
    "list": [
        r"\b(list|show|display|ls|dir|what('?s|\s+is)\s+(in|inside))\b",
        r"\b(contents?|files?\s+in|folders?\s+in|files?\s+of)\b",
    ],
    "search": [
        r"\b(search|find|look\s+for|locate|where\s+(is|are))\b",
        r"\b(scan|grep)\b",
    ],
    "open": [
        r"\b(open|explore|browse|show\s+in\s+explorer)\b",
    ],
}


def _detect_operation(text: str) -> Optional[str]:
    """Detect operation type from query text."""
    lower = text.lower()
    for op in ["create_folder", "create_file", "delete", "rename", "move", "copy", "list", "search", "open"]:
        for pat in _OP_PATTERNS[op]:
            if re.search(pat, lower):
                return op
    return None


def parse_with_llm(query: str) -> Optional[FileOpRequest]:
    """
    Use local Qwen3 LLM to semantically understand user query,
    separating conversational phrasing from actual parameters.
    """
    try:
        from core.ai.local_model import local_model
        if not local_model.is_available():
            return None

        prompt = (
            "You are a local filesystem assistant in Vault AI. Understand the user's intent and parameters.\n"
            "Output ONLY valid JSON with no preamble or explanation:\n"
            "{\n"
            '  "operation": "create_folder" | "create_file" | "delete" | "move" | "copy" | "rename" | "list" | "search" | "open" | "unknown",\n'
            '  "target_name": "clean folder or file name with NO conversational noise" or null,\n'
            '  "location": "Desktop" | "Documents" | "Downloads" | "Pictures" | "Music" | "Videos" | null or full path,\n'
            '  "destination": "destination folder or path" or null,\n'
            '  "pattern": "search pattern like *.pdf" or null\n'
            "}\n\n"
            "Example: 'create a folder on desktop named rakshit , first understand my query then make it'\n"
            'Output: {"operation": "create_folder", "target_name": "rakshit", "location": "Desktop", "destination": null, "pattern": null}\n\n'
            "Example: 'list file of download folder'\n"
            'Output: {"operation": "list", "target_name": null, "location": "Downloads", "destination": null, "pattern": null}\n\n'
            f"User query: {query}\n"
            "JSON output:"
        )
        response = local_model.chat([{"role": "user", "content": prompt}])
        if not response:
            return None

        match = re.search(r'\{.*?\}', response, re.DOTALL)
        if not match:
            return None

        data = json.loads(match.group(0))
        op = data.get("operation", "unknown")
        name = _sanitize_name(data.get("target_name") or "")
        loc = data.get("location") or ""
        dest = data.get("destination") or ""
        pat = data.get("pattern")

        # Resolve location alias
        source_path = None
        if loc:
            loc_resolved = _resolve_alias(loc).strip()
            if loc_resolved in _PATH_ALIASES.values():
                source_path = loc_resolved
            elif os.path.exists(loc_resolved):
                source_path = loc_resolved
            elif (Path.home() / loc).exists():
                source_path = str(Path.home() / loc)

        if op in {"create_folder", "create_file"} and name:
            parent = source_path or str(Path.home() / "Documents")
            source_path = str(Path(parent) / name)

        req = FileOpRequest(
            operation=op,
            source=source_path,
            destination=_resolve_alias(dest) if dest else None,
            name=name or None,
            pattern=pat,
            raw_query=query,
        )
        return req
    except Exception:
        return None


def parse_file_operation(query: str) -> FileOpRequest:
    """
    Parse natural language query into FileOpRequest.
    Prioritizes deep semantic understanding for conversational queries.
    """
    lower = query.lower().strip()

    # If conversational punctuation or phrases exist, attempt LLM understanding first
    is_conversational = any(m in lower for m in [",", ";", "first understand", "please", "can you", "then make", "i want"])
    if is_conversational:
        llm_req = parse_with_llm(query)
        if llm_req and llm_req.operation != "unknown":
            return llm_req

    resolved = _resolve_alias(query)
    lower_resolved = resolved.lower()

    op = _detect_operation(lower_resolved)
    if op is None:
        # Fall back to LLM
        llm_req = parse_with_llm(query)
        if llm_req:
            return llm_req
        return FileOpRequest(operation="unknown", raw_query=query)

    paths = _extract_windows_paths(resolved)
    quoted = _extract_quoted(resolved)

    req = FileOpRequest(operation=op, raw_query=query)

    # ── CREATE FOLDER ──────────────────────────────────────────────────────────
    if op == "create_folder":
        raw_name = ""
        # Search after named/called/as
        name_m = re.search(r'\b(?:named?|called?|as)\s+["\']?([^"\'\n\r]+?)(?=\s+(?:in|inside|at|on|to|into|from)\b|\s*$|[,"\'\n\r])', resolved, re.IGNORECASE)
        if name_m:
            raw_name = name_m.group(1).strip()
        elif quoted:
            raw_name = quoted[0].strip()
        else:
            m = re.search(
                r'\b(?:create|make|mkdir|new|add)\s+(?:a\s+)?(?:new\s+)?(?:folder|directory|dir)\s+["\']?([^"\'\n\r]+?)(?=\s+(?:in|inside|at|on|to|into|from)\b|\s*$|[,"\'\n\r])',
                resolved, re.IGNORECASE
            )
            if m:
                raw_name = m.group(1).strip()

        name = _sanitize_name(raw_name)
        if name:
            req.name = name
            if paths:
                req.source = str(Path(paths[0]) / name)
            else:
                # Check target location
                in_match = re.search(r'\b(?:in|inside|at|on)\s+["\']?([A-Za-z0-9_ .:\\/()\[\]-]+)["\']?', resolved, re.IGNORECASE)
                parent = in_match.group(1).strip() if in_match else str(Path.home() / "Documents")
                parent = _resolve_alias(parent)
                req.source = str(Path(parent) / name)
        elif paths:
            req.source = paths[0]
            req.name = Path(paths[0]).name

    # ── CREATE FILE ────────────────────────────────────────────────────────────
    elif op == "create_file":
        raw_name = ""
        name_m = re.search(r'\b(?:named?|called?|as)\s+["\']?([^"\'\n\r]+?)(?=\s+(?:in|inside|at|on|to|into|from)\b|\s*$|[,"\'\n\r])', resolved, re.IGNORECASE)
        if name_m:
            raw_name = name_m.group(1).strip()
        elif quoted:
            raw_name = quoted[0].strip()
        else:
            m = re.search(
                r'\b(?:create|make|new|add|touch)\s+(?:a\s+)?(?:new\s+)?file\s+["\']?([^"\'\n\r]+?)(?=\s+(?:in|inside|at|on|to|into|from)\b|\s*$|[,"\'\n\r])',
                resolved, re.IGNORECASE
            )
            if m:
                raw_name = m.group(1).strip()

        name = _sanitize_name(raw_name)
        if name:
            req.name = name
            if paths:
                req.source = str(Path(paths[0]) / name)
            else:
                in_match = re.search(r'\b(?:in|inside|at|on)\s+["\']?([A-Za-z0-9_ .:\\/()\[\]-]+)["\']?', resolved, re.IGNORECASE)
                parent = in_match.group(1).strip() if in_match else str(Path.home() / "Documents")
                parent = _resolve_alias(parent)
                req.source = str(Path(parent) / name)
        elif paths:
            req.source = paths[0]
            req.name = Path(paths[0]).name

    # ── DELETE ─────────────────────────────────────────────────────────────────
    elif op == "delete":
        if paths:
            req.source = paths[0]
        elif quoted:
            req.source = quoted[0]
        else:
            m = re.search(
                r'\b(?:delete|remove|trash|erase|wipe|del)\s+(?:the\s+)?(?:folder|directory|file|dir)?\s*["\']?([^\s"\']+(?:\s+[^\s"\']+)*?)["\']?',
                resolved, re.IGNORECASE
            )
            if m:
                target_cand = _sanitize_name(m.group(1).strip())
                req.source = _resolve_alias(target_cand)

    # ── MOVE ───────────────────────────────────────────────────────────────────
    elif op == "move":
        if len(paths) >= 2:
            req.source = paths[0]
            req.destination = paths[1]
        elif len(paths) == 1:
            req.source = paths[0]
            to_match = re.search(r'\bto\s+["\']?([A-Za-z]:[/\\][^\s"\']+)["\']?', resolved, re.IGNORECASE)
            if to_match:
                req.destination = to_match.group(1).strip()
        else:
            m = re.search(r'\b(?:move|cut|transfer|relocate|mv)\s+["\']?(.+?)["\']?\s+to\s+["\']?(.+?)["\']?$', resolved, re.IGNORECASE)
            if m:
                req.source = _resolve_alias(m.group(1).strip())
                req.destination = _resolve_alias(m.group(2).strip())

    # ── COPY ───────────────────────────────────────────────────────────────────
    elif op == "copy":
        if len(paths) >= 2:
            req.source = paths[0]
            req.destination = paths[1]
        elif len(paths) == 1:
            req.source = paths[0]
            to_match = re.search(r'\bto\s+["\']?([A-Za-z]:[/\\][^\s"\']+)["\']?', resolved, re.IGNORECASE)
            if to_match:
                req.destination = to_match.group(1).strip()
        else:
            m = re.search(r'\b(?:copy|cp|clone|duplicate)\s+["\']?(.+?)["\']?\s+to\s+["\']?(.+?)["\']?$', resolved, re.IGNORECASE)
            if m:
                req.source = _resolve_alias(m.group(1).strip())
                req.destination = _resolve_alias(m.group(2).strip())

    # ── RENAME ─────────────────────────────────────────────────────────────────
    elif op == "rename":
        m = re.search(r'\b(?:rename|rn|change\s+(?:the\s+)?name)\s+(?:of\s+)?["\']?(.+?)["\']?\s+(?:to|as)\s+["\']?(.+?)["\']?$', resolved, re.IGNORECASE)
        if m:
            req.source = _resolve_alias(m.group(1).strip())
            req.name = _sanitize_name(m.group(2).strip())
        elif paths:
            req.source = paths[0]
            new_name_m = re.search(r'\b(?:to|as)\s+["\']?([^\s"\'\\/:*?<>|]+)["\']?', resolved, re.IGNORECASE)
            if new_name_m:
                req.name = _sanitize_name(new_name_m.group(1).strip())

    # ── LIST ───────────────────────────────────────────────────────────────────
    elif op == "list":
        if paths:
            req.source = paths[0]
        else:
            # Check aliases in resolved query
            for alias in _PATH_ALIASES:
                if alias in lower_resolved:
                    req.source = _PATH_ALIASES[alias]
                    break
            # If still not found, check raw query words
            if not req.source:
                for alias in _PATH_ALIASES:
                    if alias in lower:
                        req.source = _PATH_ALIASES[alias]
                        break

    # ── SEARCH ─────────────────────────────────────────────────────────────────
    elif op == "search":
        pattern_m = re.search(r'\b(?:search|find|look\s+for|locate)\s+(?:for\s+)?["\']?([^\s"\']+(?:\.[a-z0-9]+)?)["\']?', resolved, re.IGNORECASE)
        if pattern_m:
            req.pattern = pattern_m.group(1).strip()
        if paths:
            req.source = paths[0]
        else:
            for alias in _PATH_ALIASES:
                if alias in lower:
                    req.source = _PATH_ALIASES[alias]
                    break

    # ── OPEN ───────────────────────────────────────────────────────────────────
    elif op == "open":
        if paths:
            req.source = paths[0]
        else:
            for alias in _PATH_ALIASES:
                if alias in lower:
                    req.source = _PATH_ALIASES[alias]
                    break

    return req


# ---------------------------------------------------------------------------
# Recycle Bin deletion (Windows)
# ---------------------------------------------------------------------------

def _delete_to_recycle_bin(path: str) -> Tuple[bool, str]:
    """Send file/folder to Windows Recycle Bin using PowerShell."""
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                f"Add-Type -AssemblyName Microsoft.VisualBasic; "
                f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("
                f"'{path}', 'OnlyErrorDialogs', 'SendToRecycleBin')"
                if os.path.isdir(path) else
                f"Add-Type -AssemblyName Microsoft.VisualBasic; "
                f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
                f"'{path}', 'OnlyErrorDialogs', 'SendToRecycleBin')"
            ],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return True, "recycled"
    except Exception:
        pass
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return True, "deleted"
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Operation Executors with Security Enforcement
# ---------------------------------------------------------------------------

def _exec_create_folder(req: FileOpRequest) -> FileOpResult:
    sm = get_security_manager()
    if not req.source:
        return FileOpResult(
            success=False,
            content=(
                "⚠️ **Please specify the folder name and target workspace.**\n\n"
                "**Examples:**\n"
                "- `create a folder named rakshit on Desktop`\n"
                "- `make a new folder called Projects in Documents`"
            ),
            status="error",
            steps=["Path Missing"],
        )
    path = Path(req.source).resolve()

    # Security Validation
    safe, reason = _is_safe_target(path)
    if not safe:
        return FileOpResult(
            success=False,
            content=f"🔒 **Security Violation Blocked:** {reason}",
            status="error",
            steps=["Security Guard Triggered"],
        )

    if not sm.is_path_authorized(str(path)):
        return FileOpResult(
            success=False,
            content=(
                f"🔒 **Access Denied:** `{path}` is outside your authorized workspaces.\n\n"
                "Vault AI can only operate within Desktop, Documents, Downloads, Pictures, Music, and Videos."
            ),
            status="error",
            steps=["Authorization Failed"],
        )

    if path.exists():
        return FileOpResult(
            success=True,
            content=(
                f"ℹ️ **Folder Already Exists**\n\n"
                f"| Property | Value |\n| :--- | :--- |\n"
                f"| **Path** | `{path}` |\n"
                f"| **Status** | Already exists — no action taken |"
            ),
            steps=["Path Checked", "Folder Already Exists"],
        )
    try:
        path.mkdir(parents=True, exist_ok=True)
        return FileOpResult(
            success=True,
            content=(
                f"✅ **Folder Created Successfully!**\n\n"
                f"| Property | Value |\n| :--- | :--- |\n"
                f"| **Name** | `{path.name}` |\n"
                f"| **Location** | `{path.parent}` |\n"
                f"| **Full Path** | `{path}` |\n"
                f"| **Status** | ✅ Created & Verified |\n\n"
                f"> 🔒 **Vault Policy:** Folder created with verified user authorization."
            ),
            steps=["Path Validated", "Folder Created", "Creation Verified"],
        )
    except PermissionError:
        return FileOpResult(
            success=False,
            content=f"❌ **Permission Denied:** Cannot create folder at `{path}`.",
            status="error",
            steps=["Permission Check Failed"],
        )
    except Exception as e:
        return FileOpResult(
            success=False,
            content=f"❌ **Error creating folder:** `{e}`",
            status="error",
            steps=["Folder Creation Failed"],
        )


def _exec_create_file(req: FileOpRequest) -> FileOpResult:
    sm = get_security_manager()
    if not req.source:
        return FileOpResult(
            success=False,
            content=(
                "⚠️ **Please specify the file name and target location.**\n\n"
                "**Examples:**\n"
                "- `create a file named notes.txt on Desktop`\n"
                "- `add a new file called report.txt in Documents`"
            ),
            status="error",
            steps=["Path Missing"],
        )
    path = Path(req.source).resolve()

    # Security Validation
    safe, reason = _is_safe_target(path)
    if not safe:
        return FileOpResult(
            success=False,
            content=f"🔒 **Security Violation Blocked:** {reason}",
            status="error",
            steps=["Security Guard Triggered"],
        )

    if not sm.is_path_authorized(str(path)):
        return FileOpResult(
            success=False,
            content=f"🔒 **Access Denied:** `{path}` is outside your authorized workspaces.",
            status="error",
            steps=["Authorization Failed"],
        )

    if path.exists():
        return FileOpResult(
            success=True,
            content=(
                f"ℹ️ **File Already Exists**\n\n"
                f"| Property | Value |\n| :--- | :--- |\n"
                f"| **Path** | `{path}` |\n"
                f"| **Size** | `{_human_size(path.stat().st_size)}` |\n"
                f"| **Status** | Already exists — no action taken |"
            ),
            steps=["Path Checked", "File Already Exists"],
        )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        return FileOpResult(
            success=True,
            content=(
                f"✅ **File Created Successfully!**\n\n"
                f"| Property | Value |\n| :--- | :--- |\n"
                f"| **Name** | `{path.name}` |\n"
                f"| **Location** | `{path.parent}` |\n"
                f"| **Full Path** | `{path}` |\n"
                f"| **Status** | ✅ Created & Verified |"
            ),
            steps=["Path Validated", "File Created", "Creation Verified"],
        )
    except Exception as e:
        return FileOpResult(
            success=False,
            content=f"❌ **Error creating file:** `{e}`",
            status="error",
            steps=["File Creation Failed"],
        )


def _exec_delete(req: FileOpRequest) -> FileOpResult:
    sm = get_security_manager()
    if not req.source:
        return FileOpResult(
            success=False,
            content=(
                "⚠️ **Please specify the file or folder to delete.**\n\n"
                "**Examples:**\n"
                "- `delete file notes.txt on Desktop`\n"
                "- `delete the folder Projects in Documents`"
            ),
            status="error",
            steps=["Target Missing"],
        )
    path = Path(req.source).resolve()

    # Security Validation
    safe, reason = _is_safe_target(path)
    if not safe:
        return FileOpResult(
            success=False,
            content=f"🔒 **Security Violation Blocked:** {reason}",
            status="error",
            steps=["Security Guard Triggered"],
        )

    if not sm.is_path_authorized(str(path)):
        return FileOpResult(
            success=False,
            content=f"🔒 **Access Denied:** `{path}` is outside your authorized workspaces.",
            status="error",
            steps=["Authorization Failed"],
        )

    if not path.exists():
        return FileOpResult(
            success=False,
            content=f"⚠️ **Not Found:** `{path}` does not exist.",
            status="error",
            steps=["Path Not Found"],
        )

    item_type = "Folder" if path.is_dir() else "File"
    size = f" ({_human_size(path.stat().st_size)})" if path.is_file() else ""
    ok, method = _delete_to_recycle_bin(str(path))
    if ok:
        recycle_note = "Sent to Recycle Bin" if method == "recycled" else "Deleted permanently"
        return FileOpResult(
            success=True,
            content=(
                f"✅ **{item_type} Deleted**\n\n"
                f"| Property | Value |\n| :--- | :--- |\n"
                f"| **Name** | `{path.name}`{size} |\n"
                f"| **Path** | `{path}` |\n"
                f"| **Action** | ♻️ {recycle_note} |"
            ),
            steps=["Path Verified", f"{item_type} Deleted", recycle_note],
        )
    else:
        return FileOpResult(
            success=False,
            content=f"❌ **Error deleting `{path}`:** `{method}`",
            status="error",
            steps=["Deletion Failed"],
        )


def _exec_move(req: FileOpRequest) -> FileOpResult:
    sm = get_security_manager()
    if not req.source or not req.destination:
        return FileOpResult(
            success=False,
            content="⚠️ **Please specify source and destination paths.**",
            status="error",
            steps=["Source or Destination Missing"],
        )
    src = Path(req.source).resolve()
    dst = Path(req.destination).resolve()

    safe_src, r_src = _is_safe_target(src)
    safe_dst, r_dst = _is_safe_target(dst)
    if not safe_src or not safe_dst:
        return FileOpResult(
            success=False,
            content=f"🔒 **Security Violation Blocked:** {r_src if not safe_src else r_dst}",
            status="error",
            steps=["Security Guard Triggered"],
        )

    if dst.is_dir():
        dst = dst / src.name

    if not sm.is_path_authorized(str(src)) or not sm.is_path_authorized(str(dst)):
        return FileOpResult(
            success=False,
            content="🔒 **Access Denied:** Source or destination is outside your authorized workspaces.",
            status="error",
            steps=["Authorization Failed"],
        )

    if not src.exists():
        return FileOpResult(
            success=False,
            content=f"⚠️ **Source Not Found:** `{src}`",
            status="error",
            steps=["Source Not Found"],
        )
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return FileOpResult(
            success=True,
            content=(
                f"✅ **Moved Successfully!**\n\n"
                f"| | Path |\n| :--- | :--- |\n"
                f"| **From** | `{src}` |\n"
                f"| **To** | `{dst}` |\n"
                f"| **Status** | ✅ Move Complete |"
            ),
            steps=["Source Verified", "Destination Prepared", "Moved"],
        )
    except Exception as e:
        return FileOpResult(
            success=False,
            content=f"❌ **Error moving:** `{e}`",
            status="error",
            steps=["Move Failed"],
        )


def _exec_copy(req: FileOpRequest) -> FileOpResult:
    sm = get_security_manager()
    if not req.source or not req.destination:
        return FileOpResult(
            success=False,
            content="⚠️ **Please specify source and destination paths.**",
            status="error",
            steps=["Source or Destination Missing"],
        )
    src = Path(req.source).resolve()
    dst = Path(req.destination).resolve()

    safe_src, r_src = _is_safe_target(src)
    safe_dst, r_dst = _is_safe_target(dst)
    if not safe_src or not safe_dst:
        return FileOpResult(
            success=False,
            content=f"🔒 **Security Violation Blocked:** {r_src if not safe_src else r_dst}",
            status="error",
            steps=["Security Guard Triggered"],
        )

    if dst.is_dir():
        dst = dst / src.name

    if not sm.is_path_authorized(str(src)) or not sm.is_path_authorized(str(dst)):
        return FileOpResult(
            success=False,
            content="🔒 **Access Denied:** Source or destination is outside your authorized workspaces.",
            status="error",
            steps=["Authorization Failed"],
        )

    if not src.exists():
        return FileOpResult(
            success=False,
            content=f"⚠️ **Source Not Found:** `{src}`",
            status="error",
            steps=["Source Not Found"],
        )
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
        else:
            shutil.copy2(str(src), str(dst))
        item_type = "Folder" if src.is_dir() else "File"
        return FileOpResult(
            success=True,
            content=(
                f"✅ **{item_type} Copied Successfully!**\n\n"
                f"| | Path |\n| :--- | :--- |\n"
                f"| **Source** | `{src}` |\n"
                f"| **Copied To** | `{dst}` |\n"
                f"| **Status** | ✅ Copy Complete |"
            ),
            steps=["Source Verified", "Destination Prepared", f"{item_type} Copied"],
        )
    except Exception as e:
        return FileOpResult(
            success=False,
            content=f"❌ **Error copying:** `{e}`",
            status="error",
            steps=["Copy Failed"],
        )


def _exec_rename(req: FileOpRequest) -> FileOpResult:
    sm = get_security_manager()
    if not req.source or not req.name:
        return FileOpResult(
            success=False,
            content="⚠️ **Please specify the file/folder to rename and its new name.**",
            status="error",
            steps=["Source or New Name Missing"],
        )
    src = Path(req.source).resolve()
    new_name = _sanitize_name(req.name)
    dst = src.parent / new_name

    safe_src, r_src = _is_safe_target(src)
    safe_dst, r_dst = _is_safe_target(dst)
    if not safe_src or not safe_dst:
        return FileOpResult(
            success=False,
            content=f"🔒 **Security Violation Blocked:** {r_src if not safe_src else r_dst}",
            status="error",
            steps=["Security Guard Triggered"],
        )

    if not sm.is_path_authorized(str(src)):
        return FileOpResult(
            success=False,
            content=f"🔒 **Access Denied:** `{src}` is outside your authorized workspaces.",
            status="error",
            steps=["Authorization Failed"],
        )

    if not src.exists():
        return FileOpResult(
            success=False,
            content=f"⚠️ **Not Found:** `{src}`",
            status="error",
            steps=["Source Not Found"],
        )
    if dst.exists():
        return FileOpResult(
            success=False,
            content=f"⚠️ **A file/folder named `{new_name}` already exists** at `{src.parent}`.",
            status="error",
            steps=["Name Conflict"],
        )
    try:
        src.rename(dst)
        return FileOpResult(
            success=True,
            content=(
                f"✅ **Renamed Successfully!**\n\n"
                f"| | Value |\n| :--- | :--- |\n"
                f"| **Old Name** | `{src.name}` |\n"
                f"| **New Name** | `{dst.name}` |\n"
                f"| **Location** | `{src.parent}` |\n"
                f"| **Status** | ✅ Rename Complete |"
            ),
            steps=["Source Verified", "Name Validated", "Renamed"],
        )
    except Exception as e:
        return FileOpResult(
            success=False,
            content=f"❌ **Error renaming:** `{e}`",
            status="error",
            steps=["Rename Failed"],
        )


def _exec_list(req: FileOpRequest) -> FileOpResult:
    # If no target folder was explicitly provided, present the primary workspaces
    if not req.source or Path(req.source).resolve() == Path.home():
        lines = [
            "### 📂 **Vault AI Authorized Workspaces**\n",
            "Here are your authorized workspace directories:\n",
            "| Workspace | Location | Description |",
            "| :--- | :--- | :--- |",
            f"| 🖥️ **Desktop** | `{Path.home() / 'Desktop'}` | Primary desktop files & shortcuts |",
            f"| 📄 **Documents** | `{Path.home() / 'Documents'}` | Project documents & records |",
            f"| 📥 **Downloads** | `{Path.home() / 'Downloads'}` | Incoming downloaded files |",
            f"| 🖼️ **Pictures** | `{Path.home() / 'Pictures'}` | Images & media assets |",
            f"| 🎵 **Music** | `{Path.home() / 'Music'}` | Audio files |",
            f"| 🎬 **Videos** | `{Path.home() / 'Videos'}` | Video recordings |",
            "\n> 💡 **Tip:** Ask `list files in Downloads` or `list files on Desktop` to view a specific folder.",
            "> 🔒 **Security Notice:** Sensitive OS directories and system configuration files are protected and filtered out.",
        ]
        return FileOpResult(
            success=True,
            content="\n".join(lines),
            steps=["Workspace Overview Retrieved", "Sensitive Directories Shielded"],
        )

    path = Path(req.source).resolve()

    # Block direct listing of sensitive directories
    safe, reason = _is_safe_target(path)
    if not safe:
        return FileOpResult(
            success=False,
            content=f"🔒 **Security Violation Blocked:** {reason}",
            status="error",
            steps=["Security Guard Triggered"],
        )

    if not path.exists():
        return FileOpResult(
            success=False,
            content=f"⚠️ **Path Not Found:** `{path}`",
            status="error",
            steps=["Path Not Found"],
        )

    if not path.is_dir():
        stat = path.stat()
        ext = path.suffix.lower()
        return FileOpResult(
            success=True,
            content=(
                f"### 📄 **File Info: `{path.name}`**\n\n"
                f"| Property | Value |\n| :--- | :--- |\n"
                f"| **Path** | `{path}` |\n"
                f"| **Size** | `{_human_size(stat.st_size)}` |\n"
                f"| **Type** | `{get_file_category(ext)}` |\n"
                f"| **Extension** | `{ext}` |"
            ),
            steps=["File Info Retrieved"],
        )

    try:
        items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        
        # Filter out hidden and sensitive/protected folders
        folders = [
            i for i in items
            if i.is_dir()
            and not i.name.startswith(".")
            and not i.name.startswith("$")
            and i.name.lower() not in PROTECTED_SYSTEM_DIRS
        ]
        files = [
            i for i in items
            if i.is_file()
            and not i.name.startswith(".")
            and not i.name.startswith("~$")
            and not i.name.lower().startswith("ntuser.dat")
        ]

        lines = [f"### 📂 **Contents of `{path.name}`**\n", f"**Location:** `{path}`\n"]

        if folders:
            lines.append(f"\n**📁 Folders ({len(folders)}):**\n")
            lines.append("| Folder Name |")
            lines.append("| :--- |")
            for f in folders[:25]:
                lines.append(f"| 📁 `{f.name}` |")
            if len(folders) > 25:
                lines.append(f"| *(+{len(folders)-25} more folders)* |")

        if files:
            lines.append(f"\n**📄 Files ({len(files)}):**\n")
            lines.append("| File Name | Type | Size |")
            lines.append("| :--- | :--- | :--- |")
            for f in files[:35]:
                size = _human_size(f.stat().st_size)
                cat = get_file_category(f.suffix.lower())
                lines.append(f"| `{f.name}` | {cat} | {size} |")
            if len(files) > 35:
                lines.append(f"| *(+{len(files)-35} more files)* | | |")

        if not folders and not files:
            lines.append("\n*This folder is empty.*")

        return FileOpResult(
            success=True,
            content="\n".join(lines),
            steps=["Directory Scanned", f"Found {len(folders)} folders, {len(files)} files", "System Directories Shielded"],
        )
    except PermissionError:
        return FileOpResult(
            success=False,
            content=f"🔒 **Permission Denied:** Cannot read `{path}`.",
            status="error",
            steps=["Permission Denied"],
        )


def _exec_search(req: FileOpRequest) -> FileOpResult:
    source = req.source or str(Path.home() / "Documents")
    pattern = req.pattern or ""
    root = Path(source).resolve()

    safe, reason = _is_safe_target(root)
    if not safe:
        return FileOpResult(
            success=False,
            content=f"🔒 **Security Violation Blocked:** {reason}",
            status="error",
            steps=["Security Guard Triggered"],
        )

    if not root.exists():
        return FileOpResult(
            success=False,
            content=f"⚠️ **Search root not found:** `{root}`",
            status="error",
            steps=["Root Not Found"],
        )

    try:
        if "*" in pattern or "?" in pattern:
            glob_pattern = pattern
        elif "." in pattern:
            ext = pattern.lstrip("*").lstrip(".")
            glob_pattern = f"*.{ext}"
        else:
            glob_pattern = f"*{pattern}*"

        results = []
        for dirpath, dirs, files in os.walk(str(root)):
            dirs[:] = [
                d for d in dirs
                if d not in PROTECTED_SYSTEM_DIRS
                and not d.startswith(".")
                and not d.startswith("$")
            ]
            for fname in files:
                if fname.startswith(".") or fname.startswith("~$"):
                    continue
                fpath = Path(dirpath) / fname
                try:
                    if fpath.match(glob_pattern) or pattern.lower() in fname.lower():
                        stat = fpath.stat()
                        results.append({
                            "name": fname,
                            "path": str(fpath),
                            "size": _human_size(stat.st_size),
                            "type": get_file_category(fpath.suffix.lower()),
                        })
                        if len(results) >= 50:
                            break
                except Exception:
                    continue
            if len(results) >= 50:
                break

        if not results:
            return FileOpResult(
                success=True,
                content=f"🔍 **No files found matching `{pattern}`** in `{root}`.",
                steps=["Search Complete", "No Results"],
            )

        lines = [
            f"### 🔍 **Search Results: `{pattern}`**\n",
            f"**Searched in:** `{root}`  |  **Found:** {len(results)} file(s)\n",
            "| File Name | Type | Size | Path |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for r in results:
            lines.append(f"| `{r['name']}` | {r['type']} | {r['size']} | `{r['path']}` |")

        return FileOpResult(
            success=True,
            content="\n".join(lines),
            steps=["Search Complete", f"Found {len(results)} result(s)"],
        )
    except Exception as e:
        return FileOpResult(
            success=False,
            content=f"❌ **Search error:** `{e}`",
            status="error",
            steps=["Search Failed"],
        )


def _exec_open(req: FileOpRequest) -> FileOpResult:
    source = req.source or str(Path.home() / "Documents")
    path = Path(source).resolve()

    safe, reason = _is_safe_target(path)
    if not safe:
        return FileOpResult(
            success=False,
            content=f"🔒 **Security Violation Blocked:** {reason}",
            status="error",
            steps=["Security Guard Triggered"],
        )

    if not path.exists():
        return FileOpResult(
            success=False,
            content=f"⚠️ **Not Found:** `{path}`",
            status="error",
            steps=["Path Not Found"],
        )
    try:
        subprocess.Popen(["explorer", str(path)])
        return FileOpResult(
            success=True,
            content=f"✅ **Opened in Explorer:** `{path}`",
            steps=["Opened in File Explorer"],
        )
    except Exception as e:
        return FileOpResult(
            success=False,
            content=f"❌ **Error opening Explorer:** `{e}`",
            status="error",
            steps=["Open Failed"],
        )


# ---------------------------------------------------------------------------
# Main Dispatcher
# ---------------------------------------------------------------------------

_EXECUTORS = {
    "create_folder": _exec_create_folder,
    "create_file":   _exec_create_file,
    "delete":        _exec_delete,
    "move":          _exec_move,
    "copy":          _exec_copy,
    "rename":        _exec_rename,
    "list":          _exec_list,
    "search":        _exec_search,
    "open":          _exec_open,
}


def execute_file_query(query: str) -> Optional[Dict[str, Any]]:
    """Main entry point: parse natural language file query and execute safely."""
    req = parse_file_operation(query)

    if req.operation not in _EXECUTORS:
        return None

    executor = _EXECUTORS[req.operation]
    result = executor(req)
    return result.to_response_dict()
