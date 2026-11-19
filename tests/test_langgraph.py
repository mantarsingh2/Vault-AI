"""Unit tests for Vault AI LangGraph orchestration workflow."""

import unittest

from core.ai.engine import execute_agent_pipeline
from core.ai.orchestration.graph import vault_graph
from core.ai.orchestration.nodes import PENDING_ACTIONS
from core.ai.orchestration.resource_engine import ResourceEngine


class TestVaultLangGraph(unittest.TestCase):
    """Test suite covering the full LangGraph orchestration graph across all intents."""

    def test_01_casual_chat_greeting(self):
        """Test that casual greetings return conversational responses with proper state."""
        result = vault_graph.invoke({"user_query": "Hello"})
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("intent"), "casual_chat")
        self.assertIn("response", result)
        self.assertTrue(len(result["response"]) > 0)
        self.assertTrue(any("Vault AI" in result["response"] or "assist" in result["response"].lower() for _ in [1]))

    def test_02_casual_chat_capabilities(self):
        """Test that 'who are you' / capability queries return detailed feature list."""
        result = vault_graph.invoke({"user_query": "Who are you and what can you do?"})
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("intent"), "casual_chat")
        self.assertIn("File Management", result.get("response", ""))
        self.assertIn("System & Hardware Monitoring", result.get("response", ""))
        self.assertIn("Device Security", result.get("response", ""))

    def test_03_system_status(self):
        """Test system status queries route to system_status node and return CPU/RAM info."""
        result = vault_graph.invoke({"user_query": "Show CPU and RAM usage"})
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("intent"), "system_status")
        self.assertIn("CPU", result.get("response", ""))
        self.assertIn("RAM", result.get("response", ""))
        self.assertIn("Checked CPU & RAM", result.get("steps", []))

    def test_04_security_check(self):
        """Test security queries route to security_check node and return cryptographic status."""
        result = vault_graph.invoke({"user_query": "Check TPM device security status"})
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("intent"), "security_check")
        self.assertIn("Key Storage Provider", result.get("response", ""))
        self.assertIn("Non-Exportability", result.get("response", ""))
        self.assertIn("Hardware Fingerprint", result.get("response", ""))

    def test_05_complex_task_planning(self):
        """Test complex tasks route through resource check and generate structured plans."""
        result = vault_graph.invoke({"user_query": "Plan setup for Python project"})
        self.assertEqual(result.get("intent"), "complex_task")
        self.assertEqual(result.get("status"), "awaiting_approval")
        self.assertTrue(result.get("approval_required"))
        self.assertIsInstance(result.get("plan"), list)
        self.assertGreater(len(result["plan"]), 0)
        self.assertIsNotNone(result.get("plan_hash"))
        self.assertIn("Execution Plan", result.get("response", ""))
        self.assertTrue(any("inspection" in item.get("type", "") or "setup" in item.get("type", "") for item in result["plan"]))

    def test_06_general_query(self):
        """Test general knowledge questions route to general_query node with valid response."""
        result = vault_graph.invoke({"user_query": "What is Python?"})
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("intent"), "general_query")
        self.assertIn("response", result)
        self.assertGreater(len(result["response"]), 10)

    def test_07_confirm_action_without_pending(self):
        """Test confirm action with no pending action returns clear message."""
        result = vault_graph.invoke({"user_query": "yes, proceed", "session_id": "test_empty_session"})
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("intent"), "confirm_action")
        self.assertIn("no pending actions", result.get("response", "").lower())

    def test_08_confirm_action_with_pending(self):
        """Test confirm action executes pending file moves when staged."""
        session_id = "test_confirm_session"
        PENDING_ACTIONS[session_id] = [
            {
                "original_path": "non_existent_file_test.txt",
                "suggested_destination": "dummy_dest/test.txt",
                "category": "Test",
                "reason": "Unit test staging",
            }
        ]
        result = vault_graph.invoke({"user_query": "do it", "session_id": session_id})
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("intent"), "confirm_action")
        self.assertNotIn(session_id, PENDING_ACTIONS)

    def test_09_resource_engine_assessment(self):
        """Test resource engine correctly detects hardware resources and recommends execution."""
        engine = ResourceEngine()
        report = engine.get_resource_report()
        self.assertIn("cpu", report)
        self.assertIn("memory", report)
        self.assertIn("gpu", report)

        assessment = engine.assess_model_resources(model_name="qwen3:8b", report=report)
        self.assertIn("recommended", assessment)
        self.assertIn("execution_mode", assessment)
        self.assertIn(assessment["execution_mode"], ["gpu", "hybrid", "cpu", "defer"])

    def test_10_execute_agent_pipeline_integration(self):
        """Test execute_agent_pipeline wraps LangGraph cleanly with assistant role."""
        pipeline_res = execute_agent_pipeline("Help me with my computer")
        self.assertEqual(pipeline_res.get("role"), "assistant")
        self.assertEqual(pipeline_res.get("status"), "success")
        self.assertEqual(pipeline_res.get("intent"), "casual_chat")
        self.assertIn("content", pipeline_res)
        self.assertGreater(len(pipeline_res["content"]), 0)

    def test_11_real_folder_lifecycle(self):
        """Test real filesystem operations: create folder, rename, and delete."""
        from pathlib import Path
        
        # 1. Create folder
        create_res = vault_graph.invoke({"user_query": "create a folder with the name vault_test_dir"})
        self.assertEqual(create_res.get("status"), "success")
        self.assertIn("Folder Created Successfully", create_res.get("response", ""))
        
        # 2. Rename folder
        rename_res = vault_graph.invoke({"user_query": "rename folder vault_test_dir to vault_renamed_dir"})
        self.assertEqual(rename_res.get("status"), "success")
        self.assertIn("Renamed Successfully", rename_res.get("response", ""))
        
        # 3. Delete folder
        delete_res = vault_graph.invoke({"user_query": "delete folder vault_renamed_dir"})
        self.assertEqual(delete_res.get("status"), "success")
        self.assertIn("Deleted Successfully", delete_res.get("response", ""))


if __name__ == "__main__":
    unittest.main()

