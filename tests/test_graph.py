"""Tests for the LangGraph orchestration layer (core/ai/graph.py).

All tests are fully mocked — no live Ollama connection needed.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(content="ok", intent="general_query", status="success", steps=None):
    return {
        "role": "assistant",
        "content": content,
        "intent": intent,
        "status": status,
        "steps": steps or [],
    }


# ---------------------------------------------------------------------------
# Tests for individual graph nodes (unit-tested in isolation)
# ---------------------------------------------------------------------------

class TestClassifyNode(unittest.TestCase):
    """classify_node must set state['intent'] correctly."""

    def _run(self, query):
        from core.ai.graph import classify_node
        return classify_node({"user_query": query, "session_id": "s1"})

    def test_system_intent(self):
        result = self._run("show me CPU usage")
        self.assertEqual(result["intent"], "system_status")

    def test_file_intent(self):
        result = self._run("find duplicate files")
        self.assertEqual(result["intent"], "file_operation")

    def test_security_intent(self):
        result = self._run("check TPM security")
        self.assertEqual(result["intent"], "security_check")

    def test_casual_intent(self):
        result = self._run("hello")
        self.assertEqual(result["intent"], "casual_chat")

    def test_complex_intent(self):
        result = self._run("setup a python development environment")
        self.assertEqual(result["intent"], "complex_task")

    def test_general_intent(self):
        result = self._run("what is quantum computing")
        self.assertEqual(result["intent"], "general_query")

    def test_confirm_intent(self):
        result = self._run("yes go ahead")
        self.assertEqual(result["intent"], "confirm_action")


class TestRouterNode(unittest.TestCase):
    """router_node must return the correct node name for each intent."""

    def _route(self, intent_value):
        from core.ai.graph import router_node
        return router_node({"user_query": "x", "intent": intent_value})

    def test_system_routes(self):
        self.assertEqual(self._route("system_status"), "system_node")

    def test_file_routes(self):
        self.assertEqual(self._route("file_operation"), "file_node")

    def test_security_routes(self):
        self.assertEqual(self._route("security_check"), "security_node")

    def test_casual_routes(self):
        self.assertEqual(self._route("casual_chat"), "chat_node")

    def test_complex_routes(self):
        self.assertEqual(self._route("complex_task"), "complex_node")

    def test_general_routes(self):
        self.assertEqual(self._route("general_query"), "general_node")

    def test_confirm_routes(self):
        self.assertEqual(self._route("confirm_action"), "confirm_node")

    def test_unknown_routes_to_general(self):
        self.assertEqual(self._route("does_not_exist"), "general_node")


class TestChatNode(unittest.TestCase):
    def test_greeting_response(self):
        from core.ai.graph import chat_node
        result = chat_node({"user_query": "hello", "intent": "casual_chat"})
        self.assertIn("Vault AI", result["response"]["content"])
        self.assertEqual(result["response"]["status"], "success")

    def test_capability_response(self):
        from core.ai.graph import chat_node
        result = chat_node({"user_query": "who are you", "intent": "casual_chat"})
        self.assertIn("File Management", result["response"]["content"])


class TestSystemNode(unittest.TestCase):
    @patch("core.system.monitor.format_system_summary", return_value="## System\nCPU: 10%")
    def test_system_summary_included(self, _mock):
        from core.ai.graph import system_node
        result = system_node({"user_query": "show cpu", "intent": "system_status"})
        self.assertIn("CPU", result["response"]["content"])
        self.assertEqual(result["response"]["status"], "success")


class TestSecurityNode(unittest.TestCase):
    @patch("core.device.get_key_storage_info", return_value={"hardware_backed": True})
    @patch(
        "core.device.get_hardware_identifiers",
        return_value={"mac_address": "AA:BB:CC:DD:EE:FF", "hostname": "TestHost"},
    )
    def test_security_response(self, _mock_hw, _mock_key):
        from core.ai.graph import security_node
        result = security_node({"user_query": "check tpm", "intent": "security_check"})
        self.assertIn("TPM", result["response"]["content"])
        self.assertEqual(result["response"]["status"], "success")


class TestGeneralNode(unittest.TestCase):
    @patch("core.ai.engine._query_local_model", return_value="Quantum computing uses qubits.")
    def test_llm_response_returned(self, _mock):
        from core.ai.graph import general_node
        result = general_node({
            "user_query": "what is quantum computing",
            "intent": "general_query",
            "conversation_history": [],
            "on_chunk": None,
        })
        self.assertEqual(result["response"]["content"], "Quantum computing uses qubits.")

    @patch("core.ai.engine._query_local_model", return_value=None)
    def test_fallback_when_ollama_unavailable(self, _mock):
        from core.ai.graph import general_node
        result = general_node({
            "user_query": "tell me something",
            "intent": "general_query",
            "conversation_history": [],
            "on_chunk": None,
        })
        self.assertIn("tell me something", result["response"]["content"])


class TestComplexNode(unittest.TestCase):
    @patch("core.ai.engine._query_local_model", return_value="Step 1: Do X\nStep 2: Do Y")
    def test_plan_from_llm(self, _mock):
        from core.ai.graph import complex_node
        result = complex_node({
            "user_query": "setup python env",
            "intent": "complex_task",
            "conversation_history": [],
            "on_chunk": None,
        })
        self.assertIn("Step 1", result["response"]["content"])

    @patch("core.ai.engine._query_local_model", return_value=None)
    def test_fallback_plan(self, _mock):
        from core.ai.graph import complex_node
        result = complex_node({
            "user_query": "deploy my app",
            "intent": "complex_task",
            "conversation_history": [],
            "on_chunk": None,
        })
        self.assertIn("Execution Plan", result["response"]["content"])


class TestConfirmNode(unittest.TestCase):
    def test_no_pending_actions(self):
        # Patch PENDING_ACTIONS to be empty
        with patch("core.ai.engine.PENDING_ACTIONS", {}):
            from core.ai.graph import confirm_node
            result = confirm_node({"user_query": "yes", "session_id": "s1", "intent": "confirm_action"})
            self.assertIn("no pending actions", result["response"]["content"])

    def test_executes_pending_action(self):
        fake_pending = [{"original_path": "/a/b.txt", "suggested_destination": "/c/"}]
        fake_exec_result = {"summary": "Moved 1 file", "success_count": 1}
        with (
            patch("core.ai.engine.PENDING_ACTIONS", {"s1": fake_pending}),
            patch("core.file_manager.executor.execute_organization_plan", return_value=fake_exec_result),
        ):
            from core.ai.graph import confirm_node
            result = confirm_node({"user_query": "yes", "session_id": "s1", "intent": "confirm_action"})
            self.assertIn("Moved 1 file", result["response"]["content"])


# ---------------------------------------------------------------------------
# End-to-end graph invocation tests
# ---------------------------------------------------------------------------

class TestAgentGraphEndToEnd(unittest.TestCase):
    """Invoke agent_graph.invoke() end-to-end with mocked leaf handlers."""

    def _invoke(self, query, extra_patches=None):
        from core.ai.graph import agent_graph
        state = {
            "user_query": query,
            "session_id": "test",
            "conversation_history": [],
            "on_chunk": None,
        }
        return agent_graph.invoke(state)

    @patch("core.system.monitor.format_system_summary", return_value="## System\nAll good.")
    def test_system_intent_end_to_end(self, _mock):
        result = self._invoke("show my CPU and RAM usage")
        self.assertEqual(result["response"]["intent"], "system_status")
        self.assertEqual(result["response"]["status"], "success")

    def test_casual_intent_end_to_end(self):
        result = self._invoke("hello there")
        self.assertEqual(result["response"]["intent"], "casual_chat")

    @patch("core.ai.engine._query_local_model", return_value="42 is the answer.")
    def test_general_intent_end_to_end(self, _mock):
        result = self._invoke("what is the answer to everything")
        self.assertEqual(result["response"]["intent"], "general_query")
        self.assertIn("42", result["response"]["content"])

    @patch("core.device.get_key_storage_info", return_value={"hardware_backed": False})
    @patch("core.device.get_hardware_identifiers", return_value={"mac_address": "00:11:22", "hostname": "PC"})
    def test_security_intent_end_to_end(self, _mock1, _mock2):
        result = self._invoke("check my device security and TPM status")
        self.assertEqual(result["response"]["intent"], "security_check")

    @patch("core.ai.engine._query_local_model", return_value="Step 1...\nStep 2...")
    def test_complex_intent_end_to_end(self, _mock):
        result = self._invoke("setup a python development environment for me")
        self.assertEqual(result["response"]["intent"], "complex_task")


if __name__ == "__main__":
    unittest.main()

