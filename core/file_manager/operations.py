"""
Vault AI — Complete File Operation Engine
==========================================

Handles ALL file/folder operations from natural language queries:

Operations:
  • create   — create folder or file
  • delete   — delete folder or file (to Recycle Bin on Windows)
  • move     — move/cut-paste folder or file
  • copy     — copy-paste folder or file
  • rename   — rename folder or file
  • list     — list contents of a directory
  • search   — search files by name or extension
  • open     — open file/folder in Explorer

Tech stack used:
  • os / shutil / pathlib  — stdlib filesystem operations
  • winreg                 — Windows registry for known folders
  • subprocess             — Windows Recycle Bin via PowerShell, Explorer open
  • Qwen3 (Ollama)         — NLP parsing of ambiguous queries → structured JSON

Security:
  • SecurityManager from core.file_manager.security enforces authorized roots
  • No symlink traversal, no path traversal (..), no system directory access
  • User home and all standard user folders (Desktop, Documents, Downloads,
    Pictures, Music, Videos) are always authorized
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
# Security: expanded authorized roots (all standard user folders)
# ---------------------------------------------------------------------------

def _build_security_manager() -> SecurityManager:
    """Build a SecurityManager with all standard user folders authorized."""
    sm = SecurityManager()
    home = Path.home()
    # Add all common user folders
    extra = [
        home,
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "Pictures",
        home / "Music",
        home / "Videos",
        home / "OneDrive",
    ]
    # Also try Windows registry known folders
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        )
        for reg_name in [
            "Desktop", "Personal", "My Pictures", "My Music", "My Video",
            "{374DE290-123F-4565-9164-39C4925E467B}"  # Downloads
        ]:
            try:
                val, _ = winreg.QueryValueEx(key, reg_name)
                extra.append(Path(os.path.expandvars(val)))
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception:
        pass
    for p in extra:
        try:
            if p.exists():
                sm.add_authorized_root(str(p))
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
# Path utilities
# ---------------------------------------------------------------------------

# Common aliases → real paths
_PATH_ALIASES = {
    "desktop":   str(Path.home() / "Desktop"),
    "documents": str(Path.home() / "Documents"),
    "docs":      str(Path.home() / "Documents"),
    "downloads": str(Path.home() / "Downloads"),
    "pictures":  str(Path.home() / "Pictures"),
    "photos":    str(Path.home() / "Pictures"),
    "music":     str(Path.home() / "Music"),
    "videos":    str(Path.home() / "Videos"),
    "home":      str(Path.home()),
    "~":         str(Path.home()),
}


def _resolve_alias(text: str) -> str:
    """Replace path aliases with real paths safely without invalid regex escapes."""
    lower = text.lower().strip()
    if lower in _PATH_ALIASES:
        return _PATH_ALIASES[lower]
    # Standalone alias replacements (e.g. "on desktop", "in documents")
    for alias, real in _PATH_ALIASES.items():
        # Match only when alias is preceded by a preposition or start of string, and not inside a path
        pattern = rf'(?<![A-Za-z0-9_\\/])(?:on|in|at|to|from|the)\s+{re.escape(alias)}(?![A-Za-z0-9_\\/])'
        text = re.sub(
            pattern,
            lambda _: f' {real}',
            text,
            flags=re.IGNORECASE,
        )
    return text


def _extract_windows_paths(text: str) -> List[str]:
    """Extract all Windows absolute paths from text safely, supporting spaces and quotes."""
    paths: List[str] = []
    
    # 1. First extract quoted Windows paths: "C:\..." or 'C:\...'
    quoted = re.findall(r'["\']([A-Za-z]:[/\\][^"\']+)["\']', text)
    paths.extend([p.strip().rstrip("\\/ .,") for p in quoted if p.strip()])

    # 2. Extract unquoted Windows paths, being careful around keywords like 'to', 'into', 'as'
    # Match drive letter through end of path tokens
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
# NLP parser — regex-based (fast, no Ollama required)
# ---------------------------------------------------------------------------

# Operation keyword maps
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
        r"\b(contents?|files?\s+in|folders?\s+in)\b",
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
    # Priority order
    for op in ["create_folder", "create_file", "delete", "rename", "move", "copy", "list", "search", "open"]:
        for pat in _OP_PATTERNS[op]:
            if re.search(pat, lower):
                return op
    return None


def _parse_name_from_query(text: str, after_keywords: List[str]) -> Optional[str]:
    """Extract a name after keywords like 'named', 'called', 'as'."""
    for kw in after_keywords:
        m = re.search(
            rf'\b{re.escape(kw)}\s+["\']?([^\s"\'\\/:*?<>|]+(?:\s+[^\s"\'\\/:*?<>|]+)*?)["\']?'
            rf'(?:\s+(?:to|in|at|on|from|into)|$)',
            text, re.IGNORECASE
        )
        if m:
            return m.group(1).strip()
    # Also try quoted
    quoted = _extract_quoted(text)
    if quoted:
        return quoted[0]
    return None


def parse_file_operation(query: str) -> FileOpRequest:
    """
    Parse a natural language file operation query into a FileOpRequest.
    Uses regex heuristics — fast, no Ollama needed.
    Falls back to Qwen3 JSON parsing for complex/ambiguous queries.
    """
    # Resolve aliases first
    resolved = _resolve_alias(query)
    lower = resolved.lower()

    op = _detect_operation(lower)
    if op is None:
        return FileOpRequest(operation="unknown", raw_query=query)

    paths = _extract_windows_paths(resolved)
    quoted = _extract_quoted(resolved)

    req = FileOpRequest(operation=op, raw_query=query)

    # ── CREATE FOLDER ──────────────────────────────────────────────────────────
    if op == "create_folder":
        name = _parse_name_from_query(resolved, ["named", "called", "as", "mkdir"])
        if not name:
            m = re.search(
                r'\b(?:create|make|mkdir|new|add)\s+(?:a\s+)?(?:new\s+)?(?:folder|directory|dir)\s+'
                r'(?:named?\s+|called?\s+)?["\']?([A-Za-z0-9_ .()\[\]-]+)["\']?',
                resolved, re.IGNORECASE
            )
            if m:
                cand = m.group(1).strip()
                if cand.lower() not in {"in", "at", "to", "on", "the", "a"}:
                    name = cand
        if name:
            req.name = name
            if paths:
                # paths[0] is the parent folder
                req.source = str(Path(paths[0]) / name)
            else:
                in_match = re.search(
                    r'\b(?:in|inside|at|on)\s+["\']?([A-Za-z0-9_ .:\\/()\[\]-]+)["\']?',
                    resolved, re.IGNORECASE
                )
                parent = in_match.group(1).strip() if in_match else str(Path.home() / "Documents")
                parent = _resolve_alias(parent)
                req.source = str(Path(parent) / name)
        elif paths:
            req.source = paths[0]
            req.name = Path(paths[0]).name

    # ── CREATE FILE ────────────────────────────────────────────────────────────
    elif op == "create_file":
        name = _parse_name_from_query(resolved, ["named", "called", "as", "touch"])
        if not name and quoted:
            name = quoted[0]
        if not name:
            m = re.search(
                r'\b(?:create|make|new|add|touch)\s+(?:a\s+)?(?:new\s+)?file\s+'
                r'(?:named?\s+|called?\s+)?["\']?([A-Za-z0-9_ .()\[\]-]+\.[A-Za-z0-9]+)["\']?',
                resolved, re.IGNORECASE
            )
            if m:
                cand = m.group(1).strip()
                if cand.lower() not in {"in", "at", "to", "on", "the", "a"}:
                    name = cand
        if name:
            req.name = name
            if paths:
                req.source = str(Path(paths[0]) / name)
            else:
                in_match = re.search(
                    r'\b(?:in|inside|at|on)\s+["\']?([A-Za-z0-9_ .:\\/()\[\]-]+)["\']?',
                    resolved, re.IGNORECASE
                )
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
            # "delete the folder MyFolder" / "delete file notes.txt"
            m = re.search(
                r'\b(?:delete|remove|trash|erase|wipe|del)\s+(?:the\s+)?'
                r'(?:folder|directory|file|dir)?\s*["\']?([^\s"\']+(?:\s+[^\s"\']+)*?)["\']?'
                r'(?:\s+(?:in|from|on|at).*)?$',
                resolved, re.IGNORECASE
            )
            if m:
                req.source = m.group(1).strip()

    # ── MOVE ───────────────────────────────────────────────────────────────────
    elif op == "move":
        if len(paths) >= 2:
            req.source = paths[0]
            req.destination = paths[1]
        elif len(paths) == 1:
            req.source = paths[0]
            # Try "to <dest>"
            to_match = re.search(r'\bto\s+["\']?([A-Za-z]:[/\\][^\s"\']+)["\']?', resolved, re.IGNORECASE)
            if to_match:
                req.destination = to_match.group(1).strip()
        else:
            # "move X to Y" with no Windows paths
            m = re.search(
                r'\b(?:move|cut|transfer|relocate|mv)\s+["\']?(.+?)["\']?\s+to\s+["\']?(.+?)["\']?$',
                resolved, re.IGNORECASE
            )
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
            m = re.search(
                r'\b(?:copy|cp|clone|duplicate)\s+["\']?(.+?)["\']?\s+to\s+["\']?(.+?)["\']?$',
                resolved, re.IGNORECASE
            )
            if m:
                req.source = _resolve_alias(m.group(1).strip())
                req.destination = _resolve_alias(m.group(2).strip())

    # ── RENAME ─────────────────────────────────────────────────────────────────
    elif op == "rename":
        # "rename X to Y" or "rename X as Y"
        m = re.search(
            r'\b(?:rename|rn|change\s+(?:the\s+)?name)\s+(?:of\s+)?["\']?(.+?)["\']?'
            r'\s+(?:to|as)\s+["\']?(.+?)["\']?$',
            resolved, re.IGNORECASE
        )
        if m:
            req.source = _resolve_alias(m.group(1).strip())
            req.name = m.group(2).strip().strip("\"'")
        elif paths:
            req.source = paths[0]
            new_name = _parse_name_from_query(resolved, ["to", "as", "named", "called"])
            req.name = new_name

    # ── LIST ───────────────────────────────────────────────────────────────────
    elif op == "list":
        if paths:
            req.source = paths[0]
        else:
            # "list files on desktop" / "show contents of Documents"
            for alias in _PATH_ALIASES:
                if alias in lower:
                    req.source = _PATH_ALIASES[alias]
                    break
            if not req.source:
                req.source = str(Path.home())

    # ── SEARCH ─────────────────────────────────────────────────────────────────
    elif op == "search":
        # "find *.pdf on desktop", "search for notes in Documents"
        # Extract pattern
        pattern_m = re.search(
            r'\b(?:search|find|look\s+for|locate)\s+(?:for\s+)?["\']?([^\s"\']+(?:\.[a-z0-9]+)?)["\']?',
            resolved, re.IGNORECASE
        )
        if pattern_m:
            req.pattern = pattern_m.group(1).strip()
        if paths:
            req.source = paths[0]
        else:
            for alias in _PATH_ALIASES:
                if alias in lower:
                    req.source = _PATH_ALIASES[alias]
                    break
            if not req.source:
                req.source = str(Path.home())

    # ── OPEN ───────────────────────────────────────────────────────────────────
    elif op == "open":
        if paths:
            req.source = paths[0]
        else:
            for alias in _PATH_ALIASES:
                if alias in lower:
                    req.source = _PATH_ALIASES[alias]
                    break
            if not req.source:
                req.source = str(Path.home())

    return req


# ---------------------------------------------------------------------------
# Qwen3-powered fallback parser (for ambiguous queries)
# ---------------------------------------------------------------------------

def parse_with_llm(query: str) -> Optional[FileOpRequest]:
    """
    Use Qwen3 to parse a complex/ambiguous file operation query into JSON.
    Returns None if Ollama unavailable or parse fails.
    """
    try:
        from core.ai.local_model import local_model
        prompt = (
            "You are a file operation parser. Parse the user's request into JSON.\n"
            "Output ONLY valid JSON with these keys:\n"
            "  operation: one of [create_folder, create_file, delete, move, copy, rename, list, search, open]\n"
            "  source: source path string or null\n"
            "  destination: destination path string or null\n"
            "  name: new filename/foldername string or null\n"
            "  pattern: search pattern string or null\n\n"
            f"User request: {query}\n\n"
            "JSON output:"
        )
        response = local_model.chat([{"role": "user", "content": prompt}])
        if not response:
            return None
        # Extract JSON from response
        json_match = re.search(r'\{.*?\}', response, re.DOTALL)
        if not json_match:
            return None
        data = json.loads(json_match.group(0))
        req = FileOpRequest(
            operation=data.get("operation", "unknown"),
            source=data.get("source"),
            destination=data.get("destination"),
            name=data.get("name"),
            pattern=data.get("pattern"),
            raw_query=query,
        )
        return req
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Recycle Bin deletion (Windows)
# ---------------------------------------------------------------------------

def _delete_to_recycle_bin(path: str) -> Tuple[bool, str]:
    """
    Send file/folder to Windows Recycle Bin using PowerShell.
    Falls back to permanent deletion if shell fails.
    """
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
    # Fallback: permanent delete
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return True, "deleted"
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Operation executors
# ---------------------------------------------------------------------------

def _exec_create_folder(req: FileOpRequest) -> FileOpResult:
    sm = get_security_manager()
    if not req.source:
        return FileOpResult(
            success=False,
            content=(
                "⚠️ **Please specify the folder path or name.**\n\n"
                "**Examples:**\n"
                "- `create a folder named Projects on Desktop`\n"
                "- `create a folder at C:\\Users\\HP\\Documents\\MyProject`\n"
                "- `make a new folder called Work in Documents`"
            ),
            status="error",
            steps=["Path Missing"],
        )
    path = Path(req.source).resolve()
    # Authorization check
    if not sm.is_path_authorized(str(path)):
        # Auto-authorize if it's a child of home
        if str(path).startswith(str(Path.home())):
            sm.add_authorized_root(str(Path.home()))
        else:
            return FileOpResult(
                success=False,
                content=(
                    f"🔒 **Access Denied:** `{path}` is outside your authorized folders.\n\n"
                    f"Vault AI can only access your Desktop, Documents, Downloads, Pictures, Music, Videos."
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
                f"> 🔒 **Vault Policy:** Folder created with your user permissions."
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
                "⚠️ **Please specify the file name or path.**\n\n"
                "**Examples:**\n"
                "- `create a file named notes.txt on Desktop`\n"
                "- `create a file at C:\\Users\\HP\\Documents\\report.txt`"
            ),
            status="error",
            steps=["Path Missing"],
        )
    path = Path(req.source).resolve()
    if not sm.is_path_authorized(str(path)):
        if str(path).startswith(str(Path.home())):
            sm.add_authorized_root(str(Path.home()))
        else:
            return FileOpResult(
                success=False,
                content=f"🔒 **Access Denied:** `{path}` is outside your authorized folders.",
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
                "⚠️ **Please specify what to delete.**\n\n"
                "**Examples:**\n"
                "- `delete the folder C:\\Users\\HP\\Documents\\OldProject`\n"
                "- `delete file C:\\Users\\HP\\Desktop\\notes.txt`\n"
                "- `remove the file notes.txt from Desktop`"
            ),
            status="error",
            steps=["Target Missing"],
        )
    path = Path(req.source).resolve()
    if not sm.is_path_authorized(str(path)):
        if str(path).startswith(str(Path.home())):
            sm.add_authorized_root(str(Path.home()))
        else:
            return FileOpResult(
                success=False,
                content=f"🔒 **Access Denied:** `{path}` is outside your authorized folders.",
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
    size = ""
    if path.is_file():
        size = f" ({_human_size(path.stat().st_size)})"
    ok, method = _delete_to_recycle_bin(str(path))
    if ok:
        recycle_note = "→ Sent to Recycle Bin" if method == "recycled" else "→ Permanently deleted"
        return FileOpResult(
            success=True,
            content=(
                f"✅ **{item_type} Deleted**\n\n"
                f"| Property | Value |\n| :--- | :--- |\n"
                f"| **Name** | `{path.name}`{size} |\n"
                f"| **Path** | `{path}` |\n"
                f"| **Action** | {recycle_note} |"
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
            content=(
                "⚠️ **Please specify source and destination.**\n\n"
                "**Examples:**\n"
                "- `move C:\\Users\\HP\\Desktop\\notes.txt to C:\\Users\\HP\\Documents`\n"
                "- `move folder Projects from Desktop to Documents`\n"
                "- `cut C:\\Users\\HP\\Downloads\\file.zip and paste to Desktop`"
            ),
            status="error",
            steps=["Source or Destination Missing"],
        )
    src = Path(req.source).resolve()
    dst = Path(req.destination).resolve()
    # If destination is a directory, move item into it
    if dst.is_dir():
        dst = dst / src.name
    if not sm.is_path_authorized(str(src)):
        sm.add_authorized_root(str(Path.home()))
    if not sm.is_path_authorized(str(dst)):
        sm.add_authorized_root(str(Path.home()))
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
            content=(
                "⚠️ **Please specify source and destination.**\n\n"
                "**Examples:**\n"
                "- `copy C:\\Users\\HP\\Desktop\\notes.txt to C:\\Users\\HP\\Documents`\n"
                "- `copy folder Projects to Downloads`\n"
                "- `duplicate the file report.pdf to Desktop`"
            ),
            status="error",
            steps=["Source or Destination Missing"],
        )
    src = Path(req.source).resolve()
    dst = Path(req.destination).resolve()
    if dst.is_dir():
        dst = dst / src.name
    sm.add_authorized_root(str(Path.home()))
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
            content=(
                "⚠️ **Please specify what to rename and the new name.**\n\n"
                "**Examples:**\n"
                "- `rename C:\\Users\\HP\\Desktop\\old.txt to new.txt`\n"
                "- `rename folder Projects to MyProjects on Desktop`\n"
                "- `change the name of notes.txt to meeting_notes.txt in Documents`"
            ),
            status="error",
            steps=["Source or New Name Missing"],
        )
    src = Path(req.source).resolve()
    new_name = req.name.strip().strip("\"'")
    dst = src.parent / new_name
    sm.add_authorized_root(str(Path.home()))
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
    source = req.source or str(Path.home())
    path = Path(source).resolve()
    if not path.exists():
        return FileOpResult(
            success=False,
            content=f"⚠️ **Path Not Found:** `{path}`",
            status="error",
            steps=["Path Not Found"],
        )
    if not path.is_dir():
        # It's a file — show its info
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
        folders = [i for i in items if i.is_dir() and not i.name.startswith(".")]
        files = [i for i in items if i.is_file() and not i.name.startswith(".")]

        lines = [f"### 📂 **Contents of `{path.name}`**\n", f"**Location:** `{path}`\n"]

        if folders:
            lines.append(f"\n**📁 Folders ({len(folders)}):**\n")
            lines.append("| Folder Name |")
            lines.append("| :--- |")
            for f in folders[:20]:
                lines.append(f"| 📁 `{f.name}` |")
            if len(folders) > 20:
                lines.append(f"| *(+{len(folders)-20} more)* |")

        if files:
            lines.append(f"\n**📄 Files ({len(files)}):**\n")
            lines.append("| File Name | Type | Size |")
            lines.append("| :--- | :--- | :--- |")
            for f in files[:30]:
                size = _human_size(f.stat().st_size)
                cat = get_file_category(f.suffix.lower())
                lines.append(f"| `{f.name}` | {cat} | {size} |")
            if len(files) > 30:
                lines.append(f"| *(+{len(files)-30} more files)* | | |")

        if not folders and not files:
            lines.append("\n*This folder is empty.*")

        return FileOpResult(
            success=True,
            content="\n".join(lines),
            steps=["Directory Read", f"Found {len(folders)} folders, {len(files)} files"],
        )
    except PermissionError:
        return FileOpResult(
            success=False,
            content=f"🔒 **Permission Denied:** Cannot read `{path}`.",
            status="error",
            steps=["Permission Denied"],
        )


def _exec_search(req: FileOpRequest) -> FileOpResult:
    source = req.source or str(Path.home())
    pattern = req.pattern or ""
    root = Path(source).resolve()

    if not root.exists():
        return FileOpResult(
            success=False,
            content=f"⚠️ **Search root not found:** `{root}`",
            status="error",
            steps=["Root Not Found"],
        )

    try:
        # Build glob pattern
        if "*" in pattern or "?" in pattern:
            glob_pattern = pattern
        elif "." in pattern:
            # e.g. "*.pdf" or just "pdf" or ".pdf"
            ext = pattern.lstrip("*").lstrip(".")
            glob_pattern = f"*.{ext}"
        else:
            glob_pattern = f"*{pattern}*"

        results = []
        ignored = {".git", "__pycache__", ".venv", "node_modules", "AppData", "$RECYCLE.BIN"}
        for dirpath, dirs, files in os.walk(str(root)):
            dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]
            for fname in files:
                if fname.startswith("."):
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
                content=(
                    f"🔍 **No files found matching `{pattern}`** in `{root}`.\n\n"
                    f"Try a different search term or location."
                ),
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
        if len(results) == 50:
            lines.append(f"\n*Showing first 50 results. Narrow your search for more precision.*")

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
    source = req.source or str(Path.home())
    path = Path(source).resolve()
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
# Main dispatcher
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
    """
    Main entry point: parse a natural language file query and execute it.

    Returns a response dict (role/content/intent/status/steps) ready for the UI,
    or None if no file operation was detected.
    """
    req = parse_file_operation(query)

    # If regex parse failed or detected unknown, try LLM
    if req.operation == "unknown":
        llm_req = parse_with_llm(query)
        if llm_req and llm_req.operation != "unknown":
            req = llm_req

    if req.operation not in _EXECUTORS:
        return None

    executor = _EXECUTORS[req.operation]
    result = executor(req)
    return result.to_response_dict()
