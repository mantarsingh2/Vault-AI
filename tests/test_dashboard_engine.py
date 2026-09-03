"""Unit tests for Dashboard system monitoring, file management, AI engine, and database persistence."""

import tempfile
import unittest
from pathlib import Path

from core.ai import Intent, classify_intent, execute_agent_pipeline
from core.files import format_directory_listing, list_directory
from core.system import format_system_summary, get_system_metrics
from database import (
    add_message,
    create_session,
    delete_session,
    ensure_default_session,
    get_session_messages,
    get_sessions,
    initialize_database,
    update_session_title,
)


class DashboardEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_dashboard.db"
        initialize_database(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_system_monitoring_metrics(self) -> None:
        metrics = get_system_metrics()
        self.assertIn("cpu", metrics)
        self.assertIn("ram", metrics)
        self.assertIn("disk", metrics)
        self.assertIn("hostname", metrics)
        self.assertGreaterEqual(metrics["cpu"]["percent"], 0.0)
        self.assertGreaterEqual(metrics["ram"]["total_gb"], 0.1)

        summary = format_system_summary()
        self.assertIn("System Health", summary)
        self.assertIn("CPU", summary)
        self.assertIn("RAM", summary)

    def test_files_manager_listing(self) -> None:
        sub_dir = Path(self.temp_dir.name) / "isolated_test_dir"
        sub_dir.mkdir(parents=True, exist_ok=True)

        listing = list_directory(str(sub_dir))
        self.assertIn("items", listing)
        self.assertEqual(listing["total_items"], 0)

        # Create a test file inside the isolated directory
        test_file = sub_dir / "sample.txt"
        test_file.write_text("Hello Vault AI")

        listing2 = list_directory(str(sub_dir))
        self.assertEqual(listing2["total_items"], 1)
        self.assertEqual(listing2["items"][0]["name"], "sample.txt")

        fmt = format_directory_listing(str(sub_dir))
        self.assertIn("Directory Listing", fmt)
        self.assertIn("sample.txt", fmt)

    def test_intent_router_classification(self) -> None:
        self.assertEqual(classify_intent("Check CPU and RAM usage"), Intent.SYSTEM_STATUS)
        self.assertEqual(classify_intent("List files in folder"), Intent.FILE_OPERATION)
        self.assertEqual(classify_intent("Check TPM device security"), Intent.SECURITY_CHECK)
        self.assertEqual(classify_intent("Hello Vault AI"), Intent.CASUAL_CHAT)
        self.assertEqual(classify_intent("Plan to setup Python and VS Code"), Intent.COMPLEX_TASK)

    def test_agent_pipeline_execution(self) -> None:
        res_sys = execute_agent_pipeline("Show CPU and RAM status")
        self.assertEqual(res_sys["status"], "success")
        self.assertEqual(res_sys["intent"], Intent.SYSTEM_STATUS.value)
        self.assertIn("CPU", res_sys["content"])

        res_file = execute_agent_pipeline("List files")
        self.assertEqual(res_file["status"], "success")
        self.assertEqual(res_file["intent"], Intent.FILE_OPERATION.value)

        res_sec = execute_agent_pipeline("Check TPM device security status")
        self.assertEqual(res_sec["status"], "success")
        self.assertEqual(res_sec["intent"], Intent.SECURITY_CHECK.value)

    def test_database_chat_sessions_and_messages(self) -> None:
        session_id = create_session("Test Session", db_path=self.db_path)
        self.assertGreater(session_id, 0)

        sessions = get_sessions(db_path=self.db_path)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["title"], "Test Session")

        # Add messages
        msg_id1 = add_message(session_id, role="user", content="Check system status", db_path=self.db_path)
        msg_id2 = add_message(
            session_id,
            role="assistant",
            content="CPU: 10%, RAM: 50%",
            intent="system_status",
            db_path=self.db_path,
        )
        self.assertGreater(msg_id1, 0)
        self.assertGreater(msg_id2, 0)

        msgs = get_session_messages(session_id, db_path=self.db_path)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["role"], "assistant")

        # Update title
        update_session_title(session_id, "Updated Title", db_path=self.db_path)
        sessions2 = get_sessions(db_path=self.db_path)
        self.assertEqual(sessions2[0]["title"], "Updated Title")

        # Delete session
        delete_session(session_id, db_path=self.db_path)
        sessions3 = get_sessions(db_path=self.db_path)
        self.assertEqual(len(sessions3), 0)


if __name__ == "__main__":
    unittest.main()
