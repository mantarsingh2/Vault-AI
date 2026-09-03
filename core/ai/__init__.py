"""AI routing, model management, and agent orchestration for Vault AI."""

from .engine import execute_agent_pipeline, is_ollama_available, query_ollama
from .router import Intent, classify_intent

__all__ = [
    "Intent",
    "classify_intent",
    "execute_agent_pipeline",
    "is_ollama_available",
    "query_ollama",
]
