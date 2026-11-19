"""Vault AI Assistant Orchestrator and Natural Language Intent Router."""

import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from typing import Any, Dict, List, Optional
import json
import re

from core.ai.ollama_client import OllamaClient
from core.ai.prompts import ORGANIZATION_SYSTEM_PROMPT
from core.file_manager.analyzer import FileAnalyzer
from core.file_manager.models import FileInfo, ScanReport
from core.file_manager.plan_generator import safe_parse_json
from core.file_manager.scanner import FileScanner
from core.file_manager.security import SecurityManager


class VaultAIAgent:
    """Orchestrates natural-language user prompts, deterministic filesystem tools, and Qwen3:8b reasoning."""

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        security_manager: Optional[SecurityManager] = None,
    ):
        self.client = ollama_client or OllamaClient()
        self.security = security_manager or SecurityManager()
        self.scanner = FileScanner()

    def _resolve_target_folders(self, prompt: str) -> List[Path]:
        """Detect which folder(s) the user is asking about using Windows registry for correct paths."""
        import os
        import sys
        prompt_lower = prompt.lower()
        home = Path.home()
        onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
        od_path = Path(onedrive) if onedrive else None

        # Read real Windows shell folder paths from registry
        known_folders: dict = {}
        if sys.platform == "win32":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
                )
                reg_map = {
                    "{374DE290-123F-4565-9164-39C4925E467B}": "downloads",
                    "Desktop": "desktop",
                    "Personal": "documents",
                    "My Pictures": "pictures",
                }
                for reg_name, key_name in reg_map.items():
                    try:
                        val, _ = winreg.QueryValueEx(key, reg_name)
                        val = os.path.expandvars(val)
                        known_folders[key_name] = Path(val)
                    except FileNotFoundError:
                        pass
                winreg.CloseKey(key)
            except Exception:
                pass

        def safe_exists(p: Optional[Path]) -> bool:
            if not p:
                return False
            try:
                return p.exists()
            except (PermissionError, OSError):
                return False

        def safe_is_dir(p: Optional[Path]) -> bool:
            if not p:
                return False
            try:
                return p.exists() and p.is_dir()
            except (PermissionError, OSError):
                return False

        def get_folder(name: str, fallback: Path) -> List[Path]:
            """Return registry path + OneDrive path if they exist."""
            results = []
            if name in known_folders and safe_exists(known_folders[name]):
                results.append(known_folders[name].resolve())
            if od_path:
                od_sub = od_path / name.capitalize()
                if safe_exists(od_sub):
                    results.append(od_sub.resolve())
            if not results and safe_exists(fallback):
                results.append(fallback.resolve())
            return results

        candidates: dict = {
            "download":  get_folder("downloads", home / "Downloads"),
            "downloads": get_folder("downloads", home / "Downloads"),
            "document":  get_folder("documents", home / "Documents"),
            "documents": get_folder("documents", home / "Documents"),
            "desktop":   get_folder("desktop",   home / "Desktop"),
            "picture":   get_folder("pictures",  home / "Pictures"),
            "pictures":  get_folder("pictures",  home / "Pictures"),
            "photo":     get_folder("pictures",  home / "Pictures"),
            "photos":    get_folder("pictures",  home / "Pictures"),
            "vault":     [Path.cwd().resolve()],
            "project":   [Path.cwd().resolve()],
        }

        resolved: List[Path] = []
        for kw, paths in candidates.items():
            if kw in prompt_lower:
                for p in paths:
                    if safe_is_dir(p):
                        resolved.append(p)

        # If no specific folder was detected, use all authorized roots from security manager
        if not resolved:
            resolved = self.security.get_authorized_roots()

        # If still empty, use current working directory
        if not resolved:
            resolved = [Path.cwd()]

        return list(dict.fromkeys(resolved))

    def process_prompt(
        self,
        user_prompt: str,
        status_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Process a natural language user prompt end-to-end."""

        # Step 1: Health check (fast, 2s timeout)
        if not self.client.check_connection(timeout=2.0):
            return {
                "success": False,
                "user_prompt": user_prompt,
                "ai_response": "⚠️ Cannot connect to local Ollama. Please ensure Ollama is running.",
                "error": "Ollama service offline",
            }

        if not self.client.is_model_available():
            return {
                "success": False,
                "user_prompt": user_prompt,
                "ai_response": f"⚠️ Model '{self.client.default_model}' was not found in Ollama.",
                "error": "Model missing",
            }

        # Step 2: Determine target folders
        target_folders = self._resolve_target_folders(user_prompt)
        folder_names = [f.name for f in target_folders]
        if status_callback:
            status_callback(f"🔍 Scanning {', '.join(folder_names)}...")

        # Step 3: Scan files - cap at 200 to keep it fast
        all_files: List[FileInfo] = []
        for folder in target_folders:
            if len(all_files) >= 200:
                break
            files = self.scanner.scan_path(str(folder))
            all_files.extend(files)
        all_files = all_files[:200]

        if not all_files:
            return {
                "success": True,
                "user_prompt": user_prompt,
                "ai_response": f"I scanned `{'`, `'.join(folder_names)}` but found no files to analyze.",
                "files_count": 0,
                "duplicates": [],
                "suggestions": [],
            }

        if status_callback:
            status_callback(f"📊 Found {len(all_files)} files. Analyzing...")

        # Step 4: Duplicate detection (only hash-based, skip related_groups to save time)
        duplicates = FileAnalyzer.find_duplicates(all_files)

        # Step 5: Find files matching search keywords in prompt
        prompt_words = re.findall(r"\b[a-zA-Z0-9_]{3,}\b", user_prompt.lower())
        stopwords = {
            "find", "where", "show", "tell", "which", "what", "files", "file",
            "folder", "folders", "duplicate", "duplicates", "organize", "suggest",
            "cleanup", "downloads", "documents", "desktop", "pictures", "the", "for",
            "all", "any", "list", "give", "are", "there",
        }
        search_keywords = [w for w in prompt_words if w not in stopwords]

        matched_files: List[FileInfo] = []
        if search_keywords:
            for f in all_files:
                if any(kw in f.name.lower() or kw in f.extension.lower() for kw in search_keywords):
                    matched_files.append(f)

        if status_callback:
            status_callback("🧠 Reasoning with local AI...")

        # Step 6: Build a tight, fast LLM prompt (fewer tokens = faster response)
        sample = matched_files[:15] if matched_files else all_files[:15]
        # Pass minimal info so LLM isn't overwhelmed by context size
        file_samples = [{"name": f.name, "path": str(f.path), "category": f.category} for f in sample]

        user_asked_organize = any(w in user_prompt.lower() for w in ["organize", "sort", "categorize", "cleanup", "clean up", "suggest"])

        if user_asked_organize:
            agent_prompt = (
                f"User asked: \"{user_prompt}\"\n"
                f"Scanned folders: {folder_names}\n"
                f"Total files: {len(all_files)}, Duplicates: {len(duplicates)}\n"
                f"Files to organize:\n{json.dumps(file_samples, indent=2)}\n\n"
                "Return ONLY a JSON object. Each suggestion MUST be a JSON object with these exact keys:\n"
                "  original_path: the full file path from the list above\n"
                "  suggested_destination: full path to the new location\n"
                "  category: category name like Documents, Images, Code, etc.\n"
                "  reason: why this file should be moved\n\n"
                "Example format:\n"
                '{"answer": "brief summary", "duplicate_summary": "", '
                '"suggestions": [{"original_path": "C:/Users/x/Downloads/report.pdf", '
                '"suggested_destination": "C:/Users/x/Downloads/Documents/report.pdf", '
                '"category": "Documents", "reason": "PDF document belongs in Documents"}]}\n'
            )
            num_predict = 600
        else:
            agent_prompt = (
                f"User asked: \"{user_prompt}\"\n"
                f"Scanned folders: {folder_names}\n"
                f"Total files: {len(all_files)}, Duplicates: {len(duplicates)}\n"
                f"Sample files: {json.dumps(file_samples, indent=2)}\n\n"
                "Return ONLY a JSON object (no markdown, no explanation outside JSON). "
                "If the user asks to list files, just write a brief summary sentence (e.g. 'Here are the files I found:'). DO NOT type out all the file names yourself.\n"
                '{"answer": "Direct 1-2 sentence answer to the user question", '
                '"duplicate_summary": "brief duplicate note or empty string", '
                '"suggestions": []}'
            )
            num_predict = 150

        # Step 7: Invoke Qwen3:8b with adaptive token limit
        gen_res = self.client.generate(
            prompt=agent_prompt,
            system_prompt=ORGANIZATION_SYSTEM_PROMPT,
            options={"num_predict": num_predict, "temperature": 0.1},
            think=False,
            timeout=120,
        )

        ai_answer = ""
        dup_summary = ""
        suggestions = []

        if gen_res.get("success"):
            parsed = safe_parse_json(gen_res.get("response", ""))
            if parsed and isinstance(parsed, dict):
                ai_answer = parsed.get("answer", "")
                dup_summary = parsed.get("duplicate_summary", "")
                raw_sugg = parsed.get("suggestions", [])
                for s in raw_sugg:
                    if not isinstance(s, dict):
                        continue
                    orig = str(s.get("original_path", "")).strip()
                    dest = str(s.get("suggested_destination", "")).strip()
                    cat = str(s.get("category", "General")).strip()
                    reason = str(s.get("reason", "")).strip()
                    if orig and dest and ".." not in dest:
                        suggestions.append({
                            "original_path": orig,
                            "suggested_destination": dest,
                            "category": cat,
                            "reason": reason,
                        })

        # Fallback if LLM failed or gave empty answer
        if not ai_answer:
            if matched_files:
                names_str = ", ".join([f"`{f.name}`" for f in matched_files[:6]])
                ai_answer = f"Found **{len(matched_files)} files** in `{'`, `'.join(folder_names)}`: {names_str}."
            else:
                ai_answer = f"Scanned **{len(all_files)} files** across `{'`, `'.join(folder_names)}`."
                if duplicates:
                    ai_answer += f" Found **{len(duplicates)} duplicate groups**."

        # Programmatically append file list if user asked for a list or all files
        prompt_l = user_prompt.lower()
        if any(word in prompt_l for word in ["list", "all files", "show me all", "every file", "what files"]):
            list_target = matched_files if matched_files else all_files
            if list_target:
                file_list_str = ", ".join([f"`{f.name}`" for f in list_target])
                ai_answer += f"\n\n**Complete File List ({len(list_target)} files):**\n{file_list_str}"

        return {
            "success": True,
            "user_prompt": user_prompt,
            "ai_response": ai_answer,
            "duplicate_summary": dup_summary,
            "total_files": len(all_files),
            "duplicates": [d.to_dict() for d in duplicates],
            "related_groups": [],
            "matched_files": [f.to_dict() for f in matched_files],
            "suggestions": suggestions,
            "scanned_folders": [str(f) for f in target_folders],
        }


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "List my documents"
    print(f"Testing VaultAIAgent with: '{prompt}'")
    agent = VaultAIAgent()
    res = agent.process_prompt(prompt)
    print("AI Response:\n", res.get("ai_response"))
