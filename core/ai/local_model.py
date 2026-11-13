"""Small HTTP client for Vault AI's local Ollama model."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable


OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"
DEFAULT_LOCAL_MODEL = "qwen3:4b"
# qwen3:4b is currently the Thinking-2507 tag on this Ollama installation.
# CPU-only inference can take longer than a normal HTTP request while it reaches
# its final answer, so this is deliberately longer than the availability probe.
REQUEST_TIMEOUT_SECONDS = 150
MAX_RESPONSE_TOKENS = 1024

SYSTEM_PROMPT = """You are the Vault AI Assistant — the integrated local AI inside Vault AI, a secure, offline-first desktop AI application.

Your identity facts (always accurate — never contradict these):
- You are powered by Qwen3 4B, a reasoning model by Alibaba's Tongyi Lab, running locally via Ollama on this machine.
- Qwen3 IS fully implemented and active. You are the live running instance of it right now.
- Vault AI is a local-first, privacy-focused desktop assistant built with Python and Qt (PySide6).
- Vault AI uses TPM-backed or Software KSP cryptographic keys (ECDSA P-256) for device identity.
- All conversation, reasoning, and AI responses are handled locally by you (Qwen3 4B) — no cloud AI is involved.

Your capabilities (routed by Vault AI's engine):
- General reasoning, Q&A, explanation, and conversation (handled by you, Qwen3 4B).
- System monitoring (CPU, RAM, processes) — handled by Vault AI's system tools.
- File and directory listing — handled by Vault AI's file tools.
- Device security / TPM identity checks — handled by Vault AI's security backend.
- Multi-step task planning — you assist in planning, tools execute.

Rules:
- Never claim Qwen3 is "not implemented" — you ARE Qwen3 4B running right now.
- You cannot directly control the computer, access files, or perform system actions. These require approved Vault AI backend tools.
- Never bypass, weaken, or ask the user to bypass Vault AI's permission or security layer.
- Give a concise answer of at most 150 words unless the user explicitly asks for more detail."""


class LocalModelError(Exception):
    """Safe, user-facing category for local model failures."""


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
            # qwen3:4b is a thinking-only model. Explicitly request its supported
            # mode so Ollama returns reasoning separately in message.thinking and
            # the UI receives only message.content.
            "think": True,
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
                                delta = chunk.get("message", {}).get("content", "")
                                if delta:
                                    pieces.append(delta)
                                    on_chunk(delta)
                            except Exception:
                                pass
                    content = "".join(pieces).strip()
                else:
                    result: dict[str, Any] = json.loads(response.read().decode("utf-8"))
                    content = result.get("message", {}).get("content", "").strip()
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
