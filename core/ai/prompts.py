"""System prompts and payload builders for AI reasoning in Vault AI."""

import json
from typing import Any, Dict, List


ORGANIZATION_SYSTEM_PROMPT = """You are Vault AI's File Intelligence Engine.
Your job is to answer the user's question directly and concisely based on the file scan data provided.

RULES:
1. Return ONLY a valid JSON object. No markdown fences, no text outside JSON.
2. The "answer" field must directly address what the user asked in 1-3 sentences.
3. Only mention duplicates or organization if the user explicitly asked for them.
4. Keep "duplicate_summary" as an empty string if user did not ask about duplicates.
5. Keep "suggestions" as an empty array unless user asked for organization.
6. Be specific: mention actual file names, counts, and folder names from the data.
"""


def build_organization_prompt(
    scanned_folders: List[str],
    file_summaries: List[Dict[str, Any]],
    duplicate_groups: List[Dict[str, Any]],
    related_groups: List[Dict[str, Any]],
) -> str:
    """Build a structured prompt for Qwen to generate file organization recommendations.

    Args:
        scanned_folders: List of root folder paths scanned.
        file_summaries: Summary metadata of files (name, category, size, ext).
        duplicate_groups: Deterministic duplicate clusters.
        related_groups: Deterministic related file clusters.

    Returns:
        str: Prompt formatted with JSON instructions.
    """
    # Compact sample for fast prompt evaluation with forward-slash normalized paths
    compact_files = [
        {
            "name": f.get("name"),
            "category": f.get("category"),
            "size": f.get("human_size", ""),
            "path": str(f.get("path", "")).replace("\\", "/"),
        }
        for f in file_summaries[:40]
    ]

    payload = {
        "files": compact_files,
        "duplicates_count": len(duplicate_groups),
        "related_clusters_count": len(related_groups),
    }

    instructions = (
        "Analyze these files and return a JSON organization recommendation.\n\n"
        f"DATA:\n{json.dumps(payload, separators=(',', ':'))}\n\n"
        "Return ONLY a JSON object with this exact structure:\n"
        "{\n"
        '  "summary": "Brief summary",\n'
        '  "duplicate_advice": "Advice for duplicate files",\n'
        '  "suggestions": [\n'
        '    {"original_path": "path/to/file", "suggested_destination": "Documents/Category", "category": "Category", "reason": "Reason"}\n'
        "  ],\n"
        '  "project_clusters": [\n'
        '    {"name": "Cluster name", "files": ["filename"], "reason": "Reason"}\n'
        "  ]\n"
        "}"
    )

    return instructions
