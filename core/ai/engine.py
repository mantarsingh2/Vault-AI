"""Local AI reasoning engine and execution pipeline for Vault AI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import os

from core.ai.local_model import LocalModelError, local_model
from core.ai.ollama_client import OllamaClient
from core.ai.router import Intent, classify_intent

# Global in-memory state for pending file operations
PENDING_ACTIONS: Dict[str, List[Dict[str, Any]]] = {}

# LangGraph agent (imported lazily to keep startup fast and avoid circulars)
_agent_graph = None


def _get_agent_graph():
    """Return the compiled LangGraph agent (lazy singleton)."""
    global _agent_graph
    if _agent_graph is None:
        from core.ai.graph import agent_graph  # noqa: PLC0415
        _agent_graph = agent_graph
    return _agent_graph

def is_ollama_available() -> bool:
    """Check if local Ollama service is reachable and running."""
    return local_model.is_available() or OllamaClient().check_connection(timeout=2.0)


def query_ollama(prompt: str, system_prompt: str = "") -> Optional[str]:
    """Compatibility wrapper that queries the configured local chat model."""
    try:
        messages = ([{"role": "system", "content": system_prompt}] if system_prompt else [])
        messages.append({"role": "user", "content": prompt})
        return local_model.chat(messages)
    except LocalModelError:
        return None


def _query_local_model(
    user_query: str,
    conversation_history: list[dict[str, str]] | None = None,
    instruction: str | None = None,
    on_chunk: Callable[[str], None] | None = None,
) -> str | None:
    """Ask Ollama using caller-owned conversation history."""
    messages = [
        {"role": message["role"], "content": message["content"]}
        for message in (conversation_history or [])
        if message.get("role") in {"user", "assistant"} and message.get("content")
    ]
    if instruction:
        messages.append({"role": "user", "content": f"{instruction}\n\nRequest: {user_query}"})
    else:
        messages.append({"role": "user", "content": user_query})
    try:
        return local_model.chat(messages, on_chunk=on_chunk)
    except LocalModelError:
        return None


def execute_agent_pipeline(
    user_query: str,
    session_id: str = "default",
    conversation_history: list[dict[str, str]] | None = None,
    on_chunk: Callable[[str], None] | None = None,
) -> Dict[str, Any]:
    """Execute the full agent loop via LangGraph orchestration."""
    # Backwards-compat shim: older callers passed history as second positional arg
    if isinstance(session_id, list) and conversation_history is None:
        conversation_history = session_id
        session_id = "default"

    initial_state: Dict[str, Any] = {
        "user_query": user_query,
        "session_id": session_id,
        "conversation_history": conversation_history or [],
        "on_chunk": on_chunk,
    }

    result = _get_agent_graph().invoke(initial_state)
    return result["response"]
