"""Local Ollama client for Vault AI.

Handles direct communication with local Ollama service (http://localhost:11434)
using standard Python HTTP libraries (urllib.request).
"""

from typing import Any, Dict, List, Optional
import json
import urllib.error
import urllib.request


class OllamaClient:
    """Client for communicating with a local Ollama instance."""

    def __init__(self, base_url: str = "http://localhost:11434", default_model: str = "qwen3:8b"):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    def check_connection(self, timeout: float = 3.0) -> bool:
        """Check if local Ollama service is reachable.

        Args:
            timeout: Request timeout in seconds.

        Returns:
            bool: True if Ollama responded, False otherwise.
        """
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                headers={"User-Agent": "Vault-AI/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def list_models(self, timeout: float = 5.0) -> List[str]:
        """List all downloaded/available models in local Ollama.

        Returns:
            List[str]: Model names (e.g. ['qwen3:8b', ...])
        """
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                headers={"User-Agent": "Vault-AI/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    models = data.get("models", [])
                    return [m.get("name", "") for m in models if m.get("name")]
        except Exception:
            pass
        return []

    def is_model_available(self, model_name: Optional[str] = None, timeout: float = 5.0) -> bool:
        """Check if a specific model (e.g., 'qwen3:8b') is available locally.

        Args:
            model_name: Name of the model. Defaults to self.default_model.
            timeout: Request timeout in seconds.

        Returns:
            bool: True if model is available.
        """
        target = (model_name or self.default_model).lower()
        models = [m.lower() for m in self.list_models(timeout=timeout)]

        # Direct match or match without tag
        for m in models:
            if m == target or m.split(":")[0] == target.split(":")[0]:
                return True
        return False

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        response_format: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        think: Optional[bool] = False,
        timeout: int = 180,
    ) -> Dict[str, Any]:
        """Send a generation request to Ollama /api/generate.

        Args:
            prompt: User prompt.
            system_prompt: Optional system instructions.
            model: Model name. Defaults to self.default_model.
            response_format: Optional format specification ('json' for JSON output).
            options: Optional Ollama generation parameters (e.g. {'num_predict': 500, 'temperature': 0.2}).
            think: Optional boolean to enable/disable model's internal thinking mode (False = direct output).
            timeout: Timeout in seconds for generation.

        Returns:
            Dict[str, Any]: {
                "success": bool,
                "response": str,
                "error": Optional[str],
                "done": bool
            }
        """
        model_name = model or self.default_model

        payload: Dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
        }

        if think is not None:
            payload["think"] = think

        if system_prompt:
            payload["system"] = system_prompt

        if response_format:
            payload["format"] = response_format

        if options:
            payload["options"] = options

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Vault-AI/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    raw_response = resp_data.get("response", "")
                    return {
                        "success": True,
                        "response": raw_response,
                        "error": None,
                        "done": resp_data.get("done", True),
                    }
                else:
                    return {
                        "success": False,
                        "response": "",
                        "error": f"Ollama HTTP error {response.status}",
                        "done": False,
                    }
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            return {
                "success": False,
                "response": "",
                "error": f"HTTP {e.code}: {e.reason} ({error_body})",
                "done": False,
            }
        except urllib.error.URLError as e:
            return {
                "success": False,
                "response": "",
                "error": f"Cannot connect to Ollama at {self.base_url}. Is Ollama running? ({e.reason})",
                "done": False,
            }
        except TimeoutError:
            return {
                "success": False,
                "response": "",
                "error": f"Ollama request timed out after {timeout} seconds.",
                "done": False,
            }
        except Exception as e:
            return {
                "success": False,
                "response": "",
                "error": f"Unexpected error: {str(e)}",
                "done": False,
            }
