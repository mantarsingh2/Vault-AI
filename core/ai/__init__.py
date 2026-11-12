"""AI integration package for Vault AI."""

from .agent import VaultAIAgent
from .engine import execute_agent_pipeline, is_ollama_available, query_ollama
from .ollama_client import OllamaClient
from .router import Intent, classify_intent

__all__ = [
    "OllamaClient",
    "VaultAIAgent",
    "execute_agent_pipeline",
    "is_ollama_available",
    "query_ollama",
    "Intent",
    "classify_intent",
]
