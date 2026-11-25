"""Small HTTP client for Vault AI's local Ollama model."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Callable


OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"
DEFAULT_LOCAL_MODEL = "qwen3:8b"
REQUEST_TIMEOUT_SECONDS = 180
MAX_RESPONSE_TOKENS = 8192

ENABLE_THINKING = True

SYSTEM_PROMPT = """You are Vault AI — a secure, offline-first desktop AI assistant powered by Qwen3 8B running locally via Ollama.

Identity (always accurate):
- You are Qwen3 8B by Alibaba's Tongyi Lab, running 100% locally — no cloud, no internet.
- Vault AI is built with Python + PySide6 (Qt). It uses TPM/ECDSA P-256 for device identity.
- Qwen3 IS active and fully working right now. Never say it is "not implemented".

Capabilities routed by Vault AI's engine:
- General Q&A, reasoning, explanation → you (Qwen3 8B)
- CPU / RAM / system monitoring → Vault AI's system tools
- File search and organisation → Vault AI's file tools
- Device security / TPM checks → Vault AI's security backend
- Multi-step task planning → you assist, tools execute

Rules — follow strictly:
- Be concise for general questions (under 150 words), but provide comprehensive, step-by-step details when the user asks for planning, analysis, code, or structured tasks.
- Never bypass or weaken Vault AI's security or permission layer."""


class LocalModelError(Exception):
    """Safe, user-facing category for local model failures."""


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks that Qwen3 may embed in content.

    Even with think=False some Qwen3 builds still emit reasoning inside the
    visible content field wrapped in <think> tags. Strip them so the user only
    sees the final answer.
    """
    # Remove complete <think>...</think> blocks (greedy=False so we don't
    # eat content between two separate think blocks)
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Also strip any dangling opening/closing tags
    cleaned = re.sub(r"</?think>", "", cleaned)
    return cleaned.strip()


class OllamaService:
    """Talk to the local Ollama REST API without adding a runtime dependency."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = DEFAULT_LOCAL_MODEL,
                 timeout: float = REQUEST_TIMEOUT_SECONDS) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            request = urllib.request.Request(f"{self.base_url}/api/tags", headers={"User-Agent": "VaultAI"})
            with urllib.request.urlopen(request, timeout=min(self.timeout, 2)) as response:
                if response.status != 200:
                    return False
                tags = json.loads(response.read().decode("utf-8"))
            models = [item.get("name") for item in tags.get("models", [])]
            if self.model in models:
                return True
            for m in models:
                if m and "qwen" in str(m).lower():
                    self.model = m
                    return True
            return False
        except (OSError, ValueError, urllib.error.URLError):
            return False

    def chat(self, messages: list[dict[str, str]], on_chunk: Callable[[str], None] | None = None) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
            "stream": on_chunk is not None,
            # ENABLE_THINKING=True: Qwen3's reasoning stays in message.thinking;
            # message.content contains only the final clean answer for the UI.
            "think": ENABLE_THINKING,
            "options": {"num_predict": MAX_RESPONSE_TOKENS},
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "VaultAI"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if on_chunk is not None:
                    pieces: list[str] = []
                    for line in response:
                        if line:
                            try:
                                chunk = json.loads(line.decode("utf-8"))
                                # With think=True, Ollama streams thinking tokens into
                                # message.thinking and answer tokens into message.content.
                                # Reading only message.content naturally skips all reasoning.
                                delta = chunk.get("message", {}).get("content", "")
                                if delta:
                                    pieces.append(delta)
                                    on_chunk(delta)
                            except Exception:
                                pass
                    content = _strip_thinking("".join(pieces))
                else:
                    result: dict[str, Any] = json.loads(response.read().decode("utf-8"))
                    # message.content holds only the final answer; message.thinking
                    # holds the reasoning — we deliberately ignore it.
                    raw = result.get("message", {}).get("content", "")
                    content = _strip_thinking(raw)
            if not content:
                raise LocalModelError("The local model returned an empty response.")
            return content
        except LocalModelError:
            raise
        except urllib.error.HTTPError as exc:
            # Do not pass Ollama's response body or implementation details to the UI.
            if exc.code == 404:
                raise LocalModelError(f"The local model {self.model} is unavailable. Pull it with `ollama pull {self.model}`.") from None
            raise LocalModelError("The local model service returned an error. Check that Ollama is running.") from None
        except (OSError, urllib.error.URLError, TimeoutError):
            raise LocalModelError("Could not connect to the local model service. Check that Ollama is running.") from None
        except (ValueError, TypeError, AttributeError):
            raise LocalModelError("The local model service returned an invalid response.") from None


local_model = OllamaService()
