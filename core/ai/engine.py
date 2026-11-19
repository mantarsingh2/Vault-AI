"""Local AI reasoning engine and execution pipeline for Vault AI."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.ai.ollama_client import OllamaClient
from core.ai.orchestration.graph import vault_graph
from core.ai.orchestration.nodes import PENDING_ACTIONS


def is_ollama_available() -> bool:
    """Check if local Ollama service is reachable and running."""
    client = OllamaClient()
    return client.check_connection(timeout=2.0)


def query_ollama(prompt: str, system_prompt: str = "") -> Optional[str]:
    """Query local Ollama with default model using direct output mode (think=False)."""
    client = OllamaClient()
    if not system_prompt:
        system_prompt = (
            "You are Vault AI, a helpful and concise assistant. "
            "Answer questions directly and accurately in 1-3 sentences. "
            "Do not repeat the question. Do not add unnecessary padding or disclaimers."
        )
    res = client.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        think=False,
        options={"num_predict": 100, "temperature": 0.2},
        timeout=120,
    )
    if res.get("success") and res.get("response"):
        return res["response"].strip()
    return None


def execute_agent_pipeline(user_query: str, session_id: str = "default") -> Dict[str, Any]:
    """Execute the full agent loop orchestrated by LangGraph.

    Args:
        user_query: The natural language prompt from the user.
        session_id: Active session identifier.

    Returns:
        Dict[str, Any]: Formatted response for the UI and downstream consumers.
    """
    try:
        graph_result = vault_graph.invoke({
            "user_query": user_query,
            "session_id": session_id,
            "status": "new",
            "steps": [],
        })

        content = graph_result.get("response", "LangGraph completed without a response.")
        status = graph_result.get("status", "success")
        intent = graph_result.get("intent", "general_query")
        plan = graph_result.get("plan", [])

        return {
            "role": "assistant",
            "content": content,
            "intent": intent,
            "status": status,
            "steps": graph_result.get("steps", []),
            "plan": plan,
            "plan_hash": graph_result.get("plan_hash"),
            "approval_required": graph_result.get("approval_required", False),
            "approval_status": graph_result.get("approval_status", "not_required"),
            "resource_assessment": graph_result.get("resource_assessment", {}),
            "model_assessment": graph_result.get("model_assessment", {}),
            "error": graph_result.get("error"),
        }
    except Exception as exc:
        return {
            "role": "assistant",
            "content": f"LangGraph encountered an unexpected error: {exc}",
            "intent": "general_query",
            "status": "failed",
            "steps": ["LangGraph execution error"],
            "error": str(exc),
            "approval_required": False,
            "approval_status": "not_required",
        }
