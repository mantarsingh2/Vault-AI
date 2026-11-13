"""Tests for Ollama client integration in Vault AI."""

import unittest
from core.ai.ollama_client import OllamaClient


class TestOllamaClient(unittest.TestCase):

    def setUp(self):
        self.client = OllamaClient(base_url="http://localhost:11434", default_model="qwen3:8b")

    def test_01_ollama_connection(self):
        """Test whether local Ollama is reachable."""
        is_connected = self.client.check_connection(timeout=3.0)
        self.assertTrue(is_connected, "Ollama service is not reachable at http://localhost:11434")

    def test_02_model_availability(self):
        """Test whether qwen3:8b model is installed and detected."""
        models = self.client.list_models(timeout=3.0)
        self.assertGreater(len(models), 0, "No models found in local Ollama.")
        is_qwen_available = self.client.is_model_available("qwen3:8b")
        self.assertTrue(is_qwen_available, f"'qwen3:8b' was not found in available models: {models}")

    def test_03_simple_generation(self):
        """Test real text generation using local qwen3:8b."""
        result = self.client.generate(
            prompt="Reply with exactly the word 'PONG' and nothing else.",
            options={"num_predict": 20},
            think=False,
            timeout=60,
        )
        self.assertTrue(result["success"], f"Generation failed with error: {result.get('error')}")
        self.assertIn("PONG", result["response"].strip().upper())

    def test_04_offline_handling(self):
        """Test that client handles invalid/offline URL without raising unhandled exceptions."""
        offline_client = OllamaClient(base_url="http://localhost:99999")
        self.assertFalse(offline_client.check_connection(timeout=1.0))
        self.assertEqual(offline_client.list_models(timeout=1.0), [])
        result = offline_client.generate("Test prompt", timeout=1)
        self.assertFalse(result["success"])
        self.assertIsNotNone(result["error"])


if __name__ == "__main__":
    unittest.main()
