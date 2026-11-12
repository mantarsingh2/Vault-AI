"""AI Organization Plan generator and response validator for Vault AI."""

from typing import Any, Dict, List, Optional
import json
import re

from core.ai.ollama_client import OllamaClient
from core.ai.prompts import ORGANIZATION_SYSTEM_PROMPT, build_organization_prompt
from .models import OrganizationSuggestion, ScanReport
from .security import SecurityManager


def safe_parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """Robustly parse JSON object from LLM output with markdown, escape, trailing comma, and cutoff handling."""
    if not raw_text:
        return None

    # 1. Strip thinking tags
    clean_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

    # 2. Extract JSON from markdown fence if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
    if fence_match:
        clean_text = fence_match.group(1).strip()
    else:
        # Strip standalone code fences
        clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
        clean_text = re.sub(r"\s*```$", "", clean_text).strip()

    # 3. Fix common LLM syntax anomalies
    clean_text = re.sub(r'\{"original,"original_path"', '{"original_path"', clean_text)

    # 4. Normalize single Windows backslashes inside JSON strings to forward slashes
    clean_text = re.sub(r'\\(?![/u"\\bfnrt])', r'/', clean_text)

    # 5. Remove trailing commas before closing braces/brackets
    clean_text = re.sub(r",\s*([\]}])", r"\1", clean_text)

    # 6. Direct parse
    try:
        return json.loads(clean_text, strict=False)
    except Exception:
        pass

    # 7. Extract outer { ... }
    json_match = re.search(r"\{.*\}", clean_text, re.DOTALL)
    if json_match:
        candidate = json_match.group(0)
        candidate = re.sub(r",\s*([\]}])", r"\1", candidate)
        try:
            return json.loads(candidate, strict=False)
        except Exception:
            pass

    # 8. Fallback repair for truncated JSON
    if "{" in clean_text:
        start_idx = clean_text.find("{")
        fragment = clean_text[start_idx:]
        fragment = re.sub(r",\s*([\]}])", r"\1", fragment)
        for suffix in ["}", '"]}', '}]}', '"}]}', '"]}}', '"}}', '"]}']:
            try:
                candidate = re.sub(r",\s*([\]}])", r"\1", fragment + suffix)
                return json.loads(candidate, strict=False)
            except Exception:
                continue

    return None


class PlanGenerator:
    """Coordinates with Ollama to generate and validate file organization suggestions."""

    def __init__(self, ollama_client: Optional[OllamaClient] = None, security_manager: Optional[SecurityManager] = None):
        self.client = ollama_client or OllamaClient()
        self.security = security_manager or SecurityManager()

    def generate_organization_plan(self, report: ScanReport) -> Dict[str, Any]:
        """Generate organization recommendations using local Ollama and Qwen3:8b.

        Args:
            report: ScanReport containing discovered files and deterministic groupings.

        Returns:
            Dict[str, Any]: {
                "success": bool,
                "summary": str,
                "duplicate_advice": str,
                "suggestions": List[OrganizationSuggestion],
                "project_clusters": List[Dict[str, Any]],
                "raw_response": str,
                "error": Optional[str],
            }
        """
        # Step 1: Verify Ollama is ready
        if not self.client.check_connection():
            return {
                "success": False,
                "summary": "",
                "duplicate_advice": "",
                "suggestions": [],
                "project_clusters": [],
                "raw_response": "",
                "error": "Ollama service is not reachable. Please start Ollama.",
            }

        if not self.client.is_model_available():
            return {
                "success": False,
                "summary": "",
                "duplicate_advice": "",
                "suggestions": [],
                "project_clusters": [],
                "raw_response": "",
                "error": f"Model '{self.client.default_model}' is not installed in Ollama.",
            }

        # Step 2: Prepare bounded structured payload
        file_samples = [f.to_dict() for f in report.files[:50]]
        dup_samples = [d.to_dict() for d in report.duplicates[:10]]
        rel_samples = [r.to_dict() for r in report.related_groups[:10]]

        prompt = build_organization_prompt(
            scanned_folders=report.scanned_folders,
            file_summaries=file_samples,
            duplicate_groups=dup_samples,
            related_groups=rel_samples,
        )

        # Step 3: Invoke Qwen3:8b with direct output mode (think=False for speed & direct formatting)
        res = self.client.generate(
            prompt=prompt,
            system_prompt=ORGANIZATION_SYSTEM_PROMPT,
            response_format=None,
            options={"num_predict": 400, "temperature": 0.1},
            think=False,
            timeout=300,
        )

        if not res["success"]:
            return {
                "success": False,
                "summary": "",
                "duplicate_advice": "",
                "suggestions": [],
                "project_clusters": [],
                "raw_response": "",
                "error": res["error"],
            }

        raw_text = res["response"].strip()

        # Step 4: Parse & validate JSON response
        parsed = safe_parse_json(raw_text)
        if not parsed or not isinstance(parsed, dict):
            return {
                "success": False,
                "summary": "AI generated a response but it could not be decoded as a valid JSON object.",
                "duplicate_advice": "",
                "suggestions": [],
                "project_clusters": [],
                "raw_response": raw_text,
                "error": "Failed to parse structured JSON from AI output.",
            }

        summary = parsed.get("summary", "Organization analysis complete.")
        duplicate_advice = parsed.get("duplicate_advice", "")
        raw_suggestions = parsed.get("suggestions", [])
        project_clusters = parsed.get("project_clusters", [])

        # Step 5: Validate suggestions against security constraints
        validated_suggestions: List[OrganizationSuggestion] = []
        for s in raw_suggestions:
            orig = str(s.get("original_path", "")).strip()
            dest = str(s.get("suggested_destination", "")).strip()
            cat = str(s.get("category", "General")).strip()
            reason = str(s.get("reason", "")).strip()

            if orig and dest:
                # Security rule: ensure no path traversal escape
                if ".." in dest or ("\\" in dest and ".." in dest):
                    continue
                validated_suggestions.append(
                    OrganizationSuggestion(
                        original_path=orig,
                        suggested_destination=dest,
                        category=cat,
                        reason=reason,
                    )
                )

        return {
            "success": True,
            "summary": summary,
            "duplicate_advice": duplicate_advice,
            "suggestions": validated_suggestions,
            "project_clusters": project_clusters,
            "raw_response": raw_text,
            "error": None,
        }
