"""File execution engine for safely applying real filesystem operations in Vault AI.

Supports creating folders, renaming files/folders, deleting files/folders,
and moving items within authorized filesystem roots.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.file_manager.security import SecurityManager


def _sanitize_name(name: str) -> str:
    """Strip quotes and invalid filesystem characters from a name."""
    clean = name.strip().strip("'\"`")
    # Remove Windows forbidden characters: < > : " / \ | ? *
    clean = re.sub(r'[<>:"/\\|?*]', "", clean).strip()
    return clean


def resolve_target_directory(location_hint: Optional[str] = None) -> Path:
    """Resolve a target parent directory based on user location hint."""
    sec = SecurityManager()
    roots = sec.get_authorized_roots()

    if location_hint:
        hint_lower = location_hint.lower().strip()
        for root in roots:
            if hint_lower in root.name.lower():
                return root
        if "project" in hint_lower or "vault" in hint_lower:
            return Path.cwd().resolve()

    # Default order: Documents -> Desktop -> Workspace -> Downloads
    preferred_order = ["documents", "desktop", "downloads"]
    for pref in preferred_order:
        for root in roots:
            if pref in root.name.lower():
                return root

    if roots:
        return roots[0]
    return Path.cwd().resolve()


def find_item_in_authorized_roots(
    target_name: str,
    location_hint: Optional[str] = None,
) -> Optional[Path]:
    """Search for a file or folder across authorized roots."""
    sec = SecurityManager()
    roots = sec.get_authorized_roots()

    clean_target = _sanitize_name(target_name).lower()
    if not clean_target:
        return None

    # 1. If location hint given, search there first
    if location_hint:
        target_dir = resolve_target_directory(location_hint)
        candidates = [target_dir / target_name]
        try:
            for child in target_dir.iterdir():
                if child.name.lower() == clean_target:
                    return child.resolve()
        except (PermissionError, OSError):
            pass

    # 2. Search all authorized roots
    for root in roots:
        try:
            direct = root / target_name
            if direct.exists():
                return direct.resolve()
            for child in root.iterdir():
                if child.name.lower() == clean_target:
                    return child.resolve()
        except (PermissionError, OSError):
            continue

    # 3. Check current workspace directory
    cwd = Path.cwd().resolve()
    try:
        direct = cwd / target_name
        if direct.exists():
            return direct.resolve()
        for child in cwd.iterdir():
            if child.name.lower() == clean_target:
                return child.resolve()
    except (PermissionError, OSError):
        pass

    return None


def create_folder(
    folder_name: str,
    location_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new directory on the real filesystem."""
    clean_name = _sanitize_name(folder_name)
    if not clean_name:
        return {
            "success": False,
            "action": "create_folder",
            "summary": "❌ Invalid folder name provided.",
        }

    target_dir = resolve_target_directory(location_hint)
    target_path = (target_dir / clean_name).resolve()

    sec = SecurityManager()
    if not sec.is_path_authorized(str(target_path)):
        return {
            "success": False,
            "action": "create_folder",
            "summary": f"❌ Security Error: `{target_path}` is outside authorized user directories.",
        }

    try:
        target_path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # If target location has restricted access (e.g. sandbox permissions), fallback to active workspace
        target_dir = Path.cwd().resolve()
        target_path = (target_dir / clean_name).resolve()
        target_path.mkdir(parents=True, exist_ok=True)

    try:
        if target_path.exists() and target_path.is_dir():
            return {
                "success": True,
                "action": "create_folder",
                "name": clean_name,
                "path": str(target_path),
                "summary": (
                    f"### 📁 **Folder Created Successfully**\n\n"
                    f"* **Folder Name:** `{clean_name}`\n"
                    f"* **Location:** `{target_path.parent.name}`\n"
                    f"* **Full Path:** `{target_path}`\n"
                    f"* **Status:** ✅ Active and ready for use\n\n"
                    f"The folder is created and available in your filesystem."
                ),
            }
        else:
            return {
                "success": False,
                "action": "create_folder",
                "summary": f"❌ Could not verify folder creation at `{target_path}`.",
            }
    except Exception as exc:
        return {
            "success": False,
            "action": "create_folder",
            "summary": f"❌ Failed to create folder `{clean_name}`: {exc}",
        }


def rename_item(
    target_name: str,
    new_name: str,
    location_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Rename an existing file or directory on the real filesystem."""
    clean_new_name = _sanitize_name(new_name)
    if not clean_new_name:
        return {
            "success": False,
            "action": "rename_item",
            "summary": "❌ Invalid new name provided.",
        }

    item = find_item_in_authorized_roots(target_name, location_hint)
    if not item or not item.exists():
        return {
            "success": False,
            "action": "rename_item",
            "summary": f"❌ Could not find `{target_name}` in your documents, desktop, or workspace.",
        }

    # Security check: cannot rename authorized root directories themselves
    sec = SecurityManager()
    roots = [r.resolve() for r in sec.get_authorized_roots()]
    if item.resolve() in roots:
        return {
            "success": False,
            "action": "rename_item",
            "summary": f"❌ Security Error: Root directory `{item.name}` cannot be renamed.",
        }

    new_path = item.parent / clean_new_name
    if new_path.exists():
        return {
            "success": False,
            "action": "rename_item",
            "summary": f"❌ An item named `{clean_new_name}` already exists in `{item.parent.name}`.",
        }

    try:
        item.rename(new_path)
        return {
            "success": True,
            "action": "rename_item",
            "old_name": item.name,
            "new_name": clean_new_name,
            "new_path": str(new_path),
            "summary": (
                f"### ✏️ **Renamed Successfully**\n\n"
                f"* **Previous Name:** `{item.name}`\n"
                f"* **New Name:** `{clean_new_name}`\n"
                f"* **Updated Path:** `{new_path}`\n"
                f"* **Status:** ✅ Name updated successfully"
            ),
        }
    except Exception as exc:
        return {
            "success": False,
            "action": "rename_item",
            "summary": f"❌ Failed to rename `{item.name}`: {exc}",
        }


def delete_item(
    target_name: str,
    location_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Delete a file or directory from the real filesystem."""
    item = find_item_in_authorized_roots(target_name, location_hint)
    if not item or not item.exists():
        return {
            "success": False,
            "action": "delete_item",
            "summary": f"❌ Could not find `{target_name}` in your documents, desktop, or workspace.",
        }

    # Critical security guard: never delete root directories or drive roots
    sec = SecurityManager()
    roots = [r.resolve() for r in sec.get_authorized_roots()]
    if item.resolve() in roots or len(item.parts) <= 2:
        return {
            "success": False,
            "action": "delete_item",
            "summary": f"🔒 Security Block: Critical system or root directory `{item.name}` cannot be deleted.",
        }

    try:
        name = item.name
        parent_name = item.parent.name
        if item.is_dir():
            shutil.rmtree(str(item))
        else:
            item.unlink()

        return {
            "success": True,
            "action": "delete_item",
            "target_name": name,
            "summary": (
                f"### 🗑️ **Item Deleted Successfully**\n\n"
                f"* **Deleted Item:** `{name}`\n"
                f"* **Removed From:** `{parent_name}`\n"
                f"* **Status:** 🗑️ Removed from file system"
            ),
        }
    except Exception as exc:
        return {
            "success": False,
            "action": "delete_item",
            "summary": f"❌ Failed to delete `{item.name}`: {exc}",
        }


def move_item(
    target_name: str,
    destination_hint: str,
) -> Dict[str, Any]:
    """Move a file or directory to a different authorized location."""
    item = find_item_in_authorized_roots(target_name)
    if not item or not item.exists():
        return {
            "success": False,
            "action": "move_item",
            "summary": f"❌ Could not find `{target_name}` to move.",
        }

    dest_dir = resolve_target_directory(destination_hint)
    dest_path = dest_dir / item.name

    try:
        shutil.move(str(item), str(dest_path))
        return {
            "success": True,
            "action": "move_item",
            "name": item.name,
            "new_path": str(dest_path),
            "summary": (
                f"### 📦 **Item Moved Successfully**\n\n"
                f"* **Item:** `{item.name}`\n"
                f"* **New Location:** `{dest_dir.name}`\n"
                f"* **Full Path:** `{dest_path}`\n"
                f"* **Status:** ✅ Relocated successfully"
            ),
        }
    except Exception as exc:
        return {
            "success": False,
            "action": "move_item",
            "summary": f"❌ Failed to move `{item.name}`: {exc}",
        }


def parse_file_action(query: str) -> Optional[Dict[str, Any]]:
    """Parse user query for direct file/folder creation, rename, delete, or move."""
    q = query.strip()

    # 1. Create Folder
    m_create = re.search(
        r"\b(?:create|make|build|add|new)\s+(?:a\s+)?(?:new\s+)?(?:directory|folder|dir)\s*(?:named|with\s+(?:the\s+)?name|called)?\s*[\"']?([a-zA-Z0-9_\-\.\s]+?)[\"']?(?:\s+(?:in|on|at|inside)\s+([a-zA-Z0-9_\-\s]+))?$",
        q,
        re.IGNORECASE,
    )
    if m_create:
        name = m_create.group(1).strip()
        loc = m_create.group(2).strip() if m_create.group(2) else None
        name = re.sub(r"^(?:named|with\s+the\s+name|with\s+name|called)\s+", "", name, flags=re.IGNORECASE).strip()
        name = re.sub(r"^(?:directory|folder|dir)\s+", "", name, flags=re.IGNORECASE).strip()
        if name:
            return {"action": "create_folder", "target": name, "location": loc}

    # 2. Rename item
    m_rename = re.search(
        r"\b(?:rename|change\s+(?:the\s+)?name\s+of)\s+(?:the\s+)?(?:directory|folder|file|dir)?\s*(?:named|called)?\s*[\"']?([a-zA-Z0-9_\-\.\s]+?)[\"']?\s+(?:to|as)\s+[\"']?([a-zA-Z0-9_\-\.\s]+?)[\"']?$",
        q,
        re.IGNORECASE,
    )
    if m_rename:
        old_name = m_rename.group(1).strip()
        new_name = m_rename.group(2).strip()
        old_name = re.sub(r"^(?:named|called)\s+", "", old_name, flags=re.IGNORECASE).strip()
        old_name = re.sub(r"^(?:directory|folder|dir|file)\s+", "", old_name, flags=re.IGNORECASE).strip()
        new_name = re.sub(r"^(?:directory|folder|dir|file)\s+", "", new_name, flags=re.IGNORECASE).strip()
        if old_name and new_name:
            return {"action": "rename_item", "target": old_name, "new_name": new_name}

    # 3. Delete item
    m_del = re.search(
        r"\b(?:delete|remove|erase|destroy|rm)\s+(?:the\s+)?(?:directory|folder|file|dir)\s*(?:named|called)?\s*[\"']?([a-zA-Z0-9_\-\.\s]+?)[\"']?(?:\s+(?:from|in|on|at)\s+([a-zA-Z0-9_\-\s]+))?$",
        q,
        re.IGNORECASE,
    )
    if m_del:
        name = m_del.group(1).strip()
        loc = m_del.group(2).strip() if m_del.group(2) else None
        name = re.sub(r"^(?:named|called)\s+", "", name, flags=re.IGNORECASE).strip()
        name = re.sub(r"^(?:directory|folder|dir|file)\s+", "", name, flags=re.IGNORECASE).strip()
        if name:
            return {"action": "delete_item", "target": name, "location": loc}

    # 4. Move item
    m_move = re.search(
        r"\b(?:move|transfer|relocate)\s+(?:the\s+)?(?:directory|folder|file|dir)?\s*[\"']?([a-zA-Z0-9_\-\.\s]+?)[\"']?\s+(?:to|into|in)\s+([a-zA-Z0-9_\-\s]+)$",
        q,
        re.IGNORECASE,
    )
    if m_move:
        src = m_move.group(1).strip()
        dest = m_move.group(2).strip()
        src = re.sub(r"^(?:directory|folder|dir|file)\s+", "", src, flags=re.IGNORECASE).strip()
        if src and dest:
            return {"action": "move_item", "target": src, "location": dest}

    return None


def parse_and_execute_file_action(user_query: str) -> Optional[Dict[str, Any]]:
    """Parse user query and execute the corresponding real filesystem operation."""
    parsed = parse_file_action(user_query)
    if not parsed:
        return None

    action = parsed.get("action")
    target = parsed.get("target", "")
    location = parsed.get("location")
    new_name = parsed.get("new_name", "")

    if action == "create_folder":
        return create_folder(target, location)
    elif action == "rename_item":
        return rename_item(target, new_name, location)
    elif action == "delete_item":
        return delete_item(target, location)
    elif action == "move_item":
        return move_item(target, location or "documents")

    return None


def execute_organization_plan(suggestions: List[Dict[str, str]]) -> Dict[str, Any]:
    """Safely execute a list of file organization suggestions."""
    success_count = 0
    failure_count = 0
    log = []

    for s in suggestions:
        orig = s.get("original_path", "").strip()
        dest = s.get("suggested_destination", "").strip()

        if not orig or not dest:
            continue

        orig_path = Path(orig)
        dest_path = Path(dest)

        if ".." in str(dest_path):
            log.append(f"❌ Skipped `{orig_path.name}` (Security warning: Destination contains '..')")
            failure_count += 1
            continue

        if not orig_path.exists() or not orig_path.is_file():
            log.append(f"❌ Skipped `{orig_path.name}` (File not found or not a file)")
            failure_count += 1
            continue

        try:
            dest_dir = dest_path.parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(orig_path), str(dest_path))
            success_count += 1
            log.append(f"✅ Moved `{orig_path.name}` ➔ `{dest_dir.name}`")
        except Exception as e:
            log.append(f"❌ Failed to move `{orig_path.name}`: {str(e)}")
            failure_count += 1

    summary_md = f"### 📂 **Organization Complete**\n\n"
    summary_md += f"* **Successfully Moved:** {success_count} files\n"
    if failure_count > 0:
        summary_md += f"* **Failed/Skipped:** {failure_count} files\n"

    summary_md += "\n" + "\n".join(log)

    return {
        "success": success_count > 0 or failure_count == 0,
        "success_count": success_count,
        "failure_count": failure_count,
        "summary": summary_md,
    }
