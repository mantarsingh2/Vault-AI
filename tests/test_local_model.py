"""Mocked REST API tests for the local Ollama model service."""

import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from core.ai.local_model import (
    MAX_RESPONSE_TOKENS,
    LocalModelError,
    OllamaService,
    SYSTEM_PROMPT,
)
from core.ai.engine import execute_agent_pipeline
from core.ai.router import Intent


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


class FakeStreamResponse:
    def __init__(self, lines):
        self.lines = lines

    def __enter__(self):
        return self.lines

    def __exit__(self, *_args):
        return False


class LocalModelTests(unittest.TestCase):
    def setUp(self):
        self.service = OllamaService(base_url="http://ollama.test", model="qwen3:4b")

    @patch("core.ai.local_model.urllib.request.urlopen")
    def test_availability_checks_requested_model(self, urlopen):
        urlopen.return_value = FakeResponse({"models": [{"name": "qwen3:4b"}]})
        self.assertTrue(self.service.is_available())
        self.assertIn("/api/tags", urlopen.call_args.args[0].full_url)

    @patch("core.ai.local_model.urllib.request.urlopen")
    def test_chat_sends_messages_and_vault_policy(self, urlopen):
        urlopen.return_value = FakeResponse({
            "message": {
                "role": "assistant",
                "content": "Hello.",
                "thinking": "Internal reasoning is kept out of the UI.",
            }
        })
        result = self.service.chat([{"role": "user", "content": "Hi"}])
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(result, "Hello.")
        self.assertEqual(payload["model"], "qwen3:4b")
        self.assertFalse(payload["stream"])
        self.assertTrue(payload["think"])
        self.assertEqual(payload["options"]["num_predict"], MAX_RESPONSE_TOKENS)
        self.assertEqual(payload["messages"][1], {"role": "user", "content": "Hi"})
        self.assertIn("Never bypass", payload["messages"][0]["content"])
        self.assertEqual(payload["messages"][0]["content"], SYSTEM_PROMPT)

    @patch("core.ai.local_model.urllib.request.urlopen")
    def test_model_errors_are_safe_and_actionable(self, urlopen):
        urlopen.side_effect = HTTPError("url", 404, "raw private detail", {}, None)
        with self.assertRaisesRegex(LocalModelError, "ollama pull qwen3:4b") as raised:
            self.service.chat([{"role": "user", "content": "Hi"}])
        self.assertNotIn("raw private detail", str(raised.exception))

    @patch("core.ai.local_model.urllib.request.urlopen")
    def test_chat_streams_tokens_via_callback(self, urlopen):
        stream_lines = [
            json.dumps({"message": {"content": "Hello "}}).encode("utf-8"),
            json.dumps({"message": {"content": "World!"}}).encode("utf-8"),
        ]
        urlopen.return_value = FakeStreamResponse(stream_lines)
        collected = []
        result = self.service.chat([{"role": "user", "content": "Hi"}], on_chunk=collected.append)
        self.assertEqual(result, "Hello World!")
        self.assertEqual(collected, ["Hello ", "World!"])

    @patch("core.ai.engine.local_model.chat", return_value="Qwen3 generated answer.")
    def test_general_query_reaches_local_model_and_returns_its_response(self, chat):
        result = execute_agent_pipeline(
            "Explain how a local-first AI assistant works.",
            conversation_history=[{"role": "user", "content": "Earlier question"}],
        )
        self.assertEqual(result["intent"], Intent.GENERAL_QUERY.value)
        self.assertEqual(result["content"], "Qwen3 generated answer.")
        self.assertEqual(result["steps"], ["Routed to Local Qwen3 4B", "Inference Completed"])
        chat.assert_called_once()
        self.assertEqual(chat.call_args.args[0][0]["content"], "Earlier question")
        self.assertEqual(
            chat.call_args.args[0][1]["content"],
            "Explain how a local-first AI assistant works.",
        )

    @patch("core.ai.engine.local_model.chat")
    def test_tool_intents_do_not_call_language_model(self, chat):
        result = execute_agent_pipeline("Show CPU and RAM status")
        self.assertEqual(result["intent"], Intent.SYSTEM_STATUS.value)
        chat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
