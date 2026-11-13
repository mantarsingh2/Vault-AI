"""File execution engine for safely applying AI organization suggestions."""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Any


def execute_organization_plan(suggestions: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Safely executes a list of file organization suggestions by moving files to their suggested destinations.
    
    Args:
        suggestions: List of dicts with 'original_path' and 'suggested_destination'.
        
    Returns:
        Dict containing success/failure counts and a markdown summary of actions taken.
    """
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
        
        # Security checks
        if ".." in str(dest_path):
            log.append(f"❌ Skipped `{orig_path.name}` (Security warning: Destination contains '..')")
            failure_count += 1
            continue
            
        if not orig_path.exists() or not orig_path.is_file():
            log.append(f"❌ Skipped `{orig_path.name}` (File not found or not a file)")
            failure_count += 1
            continue
            
        # Ensure destination directory exists
        try:
            dest_dir = dest_path.parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Move the file
            shutil.move(str(orig_path), str(dest_path))
            success_count += 1
            log.append(f"✅ Moved `{orig_path.name}` ➔ `{dest_dir.name}`")
            
        except Exception as e:
            log.append(f"❌ Failed to move `{orig_path.name}`: {str(e)}")
            failure_count += 1
            
    summary_md = f"### 📂 **Organization Complete**\n\n"
    summary_md += f"**Successfully Moved:** {success_count} files\n"
    if failure_count > 0:
        summary_md += f"**Failed/Skipped:** {failure_count} files\n"
        
    summary_md += "\n" + "\n".join(log)
    
    return {
        "success": success_count > 0 or failure_count == 0,
        "success_count": success_count,
        "failure_count": failure_count,
        "summary": summary_md
    }
