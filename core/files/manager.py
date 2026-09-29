"""Controlled filesystem operations for Vault AI."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any


def list_directory(target_path: str | Path | None = None, max_items: int = 50) -> dict[str, Any]:
    """Safely list contents of a directory with file sizes and timestamps."""
    path = Path(target_path).resolve() if target_path else Path.cwd()
    if not path.exists():
        return {"error": f"Path does not exist: {path}", "items": []}
    if not path.is_dir():
        return {"error": f"Path is not a directory: {path}", "items": []}

    items = []
    try:
        entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        for entry in entries[:max_items]:
            try:
                stat = entry.stat()
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size_bytes": stat.st_size if not entry.is_dir() else None,
                    "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
                })
            except Exception:
                items.append({"name": entry.name, "is_dir": entry.is_dir()})
    except PermissionError:
        return {"error": "Permission denied reading directory.", "items": []}
    except Exception as e:
        return {"error": str(e), "items": []}

    return {
        "path": str(path),
        "total_items": len(items),
        "items": items,
    }


def format_directory_listing(target_path: str | Path | None = None) -> str:
    """Return a Markdown formatted table of the directory contents."""
    res = list_directory(target_path)
    if "error" in res and res.get("error"):
        return f"⚠️ **Error:** {res['error']}"

    lines = [
        f"### 📁 **Directory Listing:** `{res['path']}`",
        f"",
        f"| Name | Type | Size | Modified |",
        f"| :--- | :--- | :--- | :--- |",
    ]

    for item in res.get("items", []):
        icon = "📁" if item["is_dir"] else "📄"
        item_type = "Folder" if item["is_dir"] else "File"
        size = f"{item['size_bytes']:,} B" if item.get("size_bytes") is not None else "—"
        mod = item.get("modified", "—")
        lines.append(f"| {icon} **{item['name']}** | {item_type} | {size} | {mod} |")

    return "\n".join(lines)
