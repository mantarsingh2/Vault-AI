"""Tests for Vault AI Step 4 — Persistent Conversation Memory.

Coverage
--------
1. Creating a conversation via ConversationManager.
2. Saving user and assistant messages.
3. Loading messages in correct chronological order.
4. Persistence after reopening the database connection (simulated by creating a
   second ConversationManager pointed at the same file).
5. Bounded history — only the tail up to history_limit is returned.
6. Qwen3 4B receives conversation history for general_query intent.
7. Existing tool intents (system_status, file_operation, security_check) do not
   call the language model.
8. ConversationManager interface: list, rename, delete conversations.
9. Full conversation flow: save user msg → bounded history → agent pipeline →
   save assistant response.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, call

from core.ai.conversation_manager import ConversationManager, DEFAULT_HISTORY_LIMIT
from core.ai.engine import execute_agent_pipeline
from core.ai.router import Intent, classify_intent
from database import initialize_database


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(tmp_path: Path, history_limit: int = DEFAULT_HISTORY_LIMIT) -> ConversationManager:
    """Return an isolated ConversationManager backed by a fresh temp database."""
    return ConversationManager(db_path=tmp_path, history_limit=history_limit)


# ---------------------------------------------------------------------------
# Test 1 — Creating a conversation
# ---------------------------------------------------------------------------

class TestCreateConversation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "vault_test.db"
        self.mgr = _make_manager(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_returns_positive_integer_id(self):
        session_id = self.mgr.create_conversation("My Session")
        self.assertIsInstance(session_id, int)
        self.assertGreater(session_id, 0)

    def test_created_session_appears_in_list(self):
        session_id = self.mgr.create_conversation("Alpha")
        conversations = self.mgr.list_conversations()
        ids = [c["id"] for c in conversations]
        self.assertIn(session_id, ids)

    def test_created_session_has_required_fields(self):
        session_id = self.mgr.create_conversation("Beta")
        conv = self.mgr.list_conversations()[0]
        self.assertIn("id", conv)
        self.assertIn("title", conv)
        self.assertIn("created_at", conv)
        self.assertIn("updated_at", conv)
        self.assertEqual(conv["title"], "Beta")

    def test_multiple_sessions_all_listed(self):
        ids = [self.mgr.create_conversation(f"Session {i}") for i in range(5)]
        listed = [c["id"] for c in self.mgr.list_conversations()]
        for sid in ids:
            self.assertIn(sid, listed)

    def test_get_or_create_default_without_existing_sessions(self):
        sid = self.mgr.get_or_create_default()
        self.assertGreater(sid, 0)
        self.assertEqual(len(self.mgr.list_conversations()), 1)

    def test_get_or_create_default_returns_existing_session(self):
        first = self.mgr.create_conversation("Existing")
        default = self.mgr.get_or_create_default()
        # Should return the existing session, not create a new one
        self.assertEqual(default, first)
        self.assertEqual(len(self.mgr.list_conversations()), 1)


# ---------------------------------------------------------------------------
# Test 2 — Saving user and assistant messages
# ---------------------------------------------------------------------------

class TestSaveMessages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "vault_test.db"
        self.mgr = _make_manager(self.db_path)
        self.session_id = self.mgr.create_conversation("Save Test")

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_user_message_returns_row_id(self):
        row_id = self.mgr.save_message(self.session_id, role="user", content="Hello")
        self.assertGreater(row_id, 0)

    def test_save_assistant_message_returns_row_id(self):
        row_id = self.mgr.save_message(
            self.session_id, role="assistant", content="Hi there!"
        )
        self.assertGreater(row_id, 0)

    def test_saved_message_has_correct_role_and_content(self):
        self.mgr.save_message(self.session_id, role="user", content="What is CPU?")
        messages = self.mgr.load_messages(self.session_id)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "What is CPU?")

    def test_save_both_roles_and_intent(self):
        self.mgr.save_message(
            self.session_id, role="user", content="Show system stats", intent="system_status"
        )
        self.mgr.save_message(
            self.session_id, role="assistant", content="CPU: 20%", intent="system_status"
        )
        messages = self.mgr.load_messages(self.session_id)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["intent"], "system_status")
        self.assertEqual(messages[1]["intent"], "system_status")

    def test_message_timestamps_are_present(self):
        self.mgr.save_message(self.session_id, role="user", content="Timestamp test")
        messages = self.mgr.load_messages(self.session_id)
        self.assertIn("created_at", messages[0])
        self.assertIsNotNone(messages[0]["created_at"])


# ---------------------------------------------------------------------------
# Test 3 — Loading messages in correct chronological order
# ---------------------------------------------------------------------------

class TestLoadMessagesOrder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "vault_test.db"
        self.mgr = _make_manager(self.db_path)
        self.session_id = self.mgr.create_conversation("Order Test")

    def tearDown(self):
        self.tmp.cleanup()

    def test_messages_returned_in_chronological_order(self):
        contents = ["first", "second", "third", "fourth"]
        for c in contents:
            self.mgr.save_message(self.session_id, role="user", content=c)

        messages = self.mgr.load_messages(self.session_id)
        self.assertEqual(len(messages), 4)
        for i, expected in enumerate(contents):
            self.assertEqual(messages[i]["content"], expected)

    def test_alternating_roles_preserved_in_order(self):
        pairs = [("user", "q1"), ("assistant", "a1"), ("user", "q2"), ("assistant", "a2")]
        for role, content in pairs:
            self.mgr.save_message(self.session_id, role=role, content=content)

        messages = self.mgr.load_messages(self.session_id)
        self.assertEqual(len(messages), 4)
        for i, (expected_role, expected_content) in enumerate(pairs):
            self.assertEqual(messages[i]["role"], expected_role)
            self.assertEqual(messages[i]["content"], expected_content)

    def test_ids_are_ascending(self):
        for i in range(5):
            self.mgr.save_message(self.session_id, role="user", content=f"msg {i}")
        messages = self.mgr.load_messages(self.session_id)
        ids = [m["id"] for m in messages]
        self.assertEqual(ids, sorted(ids))


# ---------------------------------------------------------------------------
# Test 4 — Persistence after reopening the database connection
# ---------------------------------------------------------------------------

class TestPersistenceAfterReopen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "vault_persist.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_session_persists_across_manager_instances(self):
        # First manager instance — write data
        mgr1 = _make_manager(self.db_path)
        session_id = mgr1.create_conversation("Persistent Session")
        mgr1.save_message(session_id, role="user", content="Remember me?")
        mgr1.save_message(session_id, role="assistant", content="Yes, I remember!")

        # Second manager instance — simulate app restart by creating a new object
        mgr2 = _make_manager(self.db_path)
        conversations = mgr2.list_conversations()

        self.assertEqual(len(conversations), 1)
        self.assertEqual(conversations[0]["title"], "Persistent Session")

        messages = mgr2.load_messages(session_id)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["content"], "Remember me?")
        self.assertEqual(messages[1]["content"], "Yes, I remember!")

    def test_messages_do_not_disappear_after_reopen(self):
        mgr1 = _make_manager(self.db_path)
        sid = mgr1.create_conversation("Don't Lose Me")
        for i in range(10):
            mgr1.save_message(sid, role="user" if i % 2 == 0 else "assistant",
                              content=f"message {i}")

        mgr2 = _make_manager(self.db_path)
        messages = mgr2.load_messages(sid)
        self.assertEqual(len(messages), 10)
        # Verify content integrity
        for i, msg in enumerate(messages):
            self.assertEqual(msg["content"], f"message {i}")

    def test_multiple_sessions_persist_across_reopen(self):
        mgr1 = _make_manager(self.db_path)
        ids = [mgr1.create_conversation(f"Session {i}") for i in range(3)]
        for sid in ids:
            mgr1.save_message(sid, role="user", content=f"message in {sid}")

        mgr2 = _make_manager(self.db_path)
        listed = mgr2.list_conversations()
        self.assertEqual(len(listed), 3)
        for sid in ids:
            msgs = mgr2.load_messages(sid)
            self.assertEqual(len(msgs), 1)


# ---------------------------------------------------------------------------
# Test 5 — Bounded history
# ---------------------------------------------------------------------------

class TestBoundedHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "vault_bound.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_bounded_history_returns_at_most_limit_messages(self):
        limit = 6
        mgr = _make_manager(self.db_path, history_limit=limit)
        sid = mgr.create_conversation("Bounded Test")

        # Write 20 messages — more than the limit
        for i in range(20):
            role = "user" if i % 2 == 0 else "assistant"
            mgr.save_message(sid, role=role, content=f"message {i}")

        history = mgr.get_bounded_history(sid)
        self.assertLessEqual(len(history), limit)

    def test_bounded_history_returns_most_recent_messages(self):
        limit = 4
        mgr = _make_manager(self.db_path, history_limit=limit)
        sid = mgr.create_conversation("Recency Test")

        messages_in = [("user", f"q{i}") if i % 2 == 0 else ("assistant", f"a{i}")
                       for i in range(10)]
        for role, content in messages_in:
            mgr.save_message(sid, role=role, content=content)

        history = mgr.get_bounded_history(sid)
        # Last 4 messages should be the tail
        expected_tail = [{"role": r, "content": c} for r, c in messages_in[-limit:]]
        self.assertEqual(history, expected_tail)

    def test_bounded_history_excludes_system_role(self):
        mgr = _make_manager(self.db_path, history_limit=20)
        sid = mgr.create_conversation("System Role Test")

        mgr.save_message(sid, role="system", content="System instruction")
        mgr.save_message(sid, role="user", content="User query")
        mgr.save_message(sid, role="assistant", content="AI answer")

        history = mgr.get_bounded_history(sid)
        roles_in_history = [m["role"] for m in history]
        self.assertNotIn("system", roles_in_history)
        self.assertEqual(len(history), 2)

    def test_bounded_history_with_fewer_messages_than_limit(self):
        mgr = _make_manager(self.db_path, history_limit=20)
        sid = mgr.create_conversation("Small Session")

        mgr.save_message(sid, role="user", content="Only message")
        history = mgr.get_bounded_history(sid)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["content"], "Only message")

    def test_bounded_history_empty_for_new_session(self):
        mgr = _make_manager(self.db_path)
        sid = mgr.create_conversation("Empty Session")
        history = mgr.get_bounded_history(sid)
        self.assertEqual(history, [])

    def test_default_history_limit_is_reasonable(self):
        # The constant itself should be at least 10 and at most 50
        self.assertGreaterEqual(DEFAULT_HISTORY_LIMIT, 10)
        self.assertLessEqual(DEFAULT_HISTORY_LIMIT, 50)

    def test_history_shape_is_role_content_dicts(self):
        mgr = _make_manager(self.db_path, history_limit=5)
        sid = mgr.create_conversation("Shape Test")
        mgr.save_message(sid, role="user", content="question")
        mgr.save_message(sid, role="assistant", content="answer")

        history = mgr.get_bounded_history(sid)
        for item in history:
            self.assertIn("role", item)
            self.assertIn("content", item)
            self.assertEqual(set(item.keys()), {"role", "content"})


# ---------------------------------------------------------------------------
# Test 6 — Qwen receives conversation history for general_query
# ---------------------------------------------------------------------------

class TestQwenReceivesHistoryForGeneralQuery(unittest.TestCase):
    """Verify that for GENERAL_QUERY intents, the bounded history is forwarded
    to the local model and that Qwen returns its response as the pipeline result.
    """

    @patch("core.ai.engine.local_model.chat", return_value="Qwen3 answer.")
    def test_general_query_forwards_conversation_history(self, mock_chat):
        history = [
            {"role": "user", "content": "Previous turn question"},
            {"role": "assistant", "content": "Previous turn answer"},
        ]
        result = execute_agent_pipeline(
            "Tell me about Python generators.",
            conversation_history=history,
        )
        self.assertEqual(result["intent"], Intent.GENERAL_QUERY.value)
        self.assertEqual(result["content"], "Qwen3 answer.")
        mock_chat.assert_called_once()

        # The history items should appear in the messages sent to the model
        sent_messages = mock_chat.call_args.args[0]
        sent_contents = [m["content"] for m in sent_messages]
        self.assertIn("Previous turn question", sent_contents)
        self.assertIn("Previous turn answer", sent_contents)
        # The new query should also be included
        self.assertIn("Tell me about Python generators.", sent_contents)

    @patch("core.ai.engine.local_model.chat", return_value="Answer with no prior history.")
    def test_general_query_works_with_empty_history(self, mock_chat):
        result = execute_agent_pipeline(
            "Explain recursion.",
            conversation_history=[],
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["content"], "Answer with no prior history.")
        mock_chat.assert_called_once()

    @patch("core.ai.engine.local_model.chat", return_value="Answer without history param.")
    def test_general_query_works_without_history_param(self, mock_chat):
        result = execute_agent_pipeline("What is a closure?")
        self.assertEqual(result["status"], "success")
        mock_chat.assert_called_once()

    @patch("core.ai.engine.local_model.chat", return_value="Complex plan result.")
    def test_complex_task_also_receives_history(self, mock_chat):
        history = [{"role": "user", "content": "I use Python 3.11"}]
        result = execute_agent_pipeline(
            "Setup a virtual environment for my project",
            conversation_history=history,
        )
        self.assertEqual(result["intent"], Intent.COMPLEX_TASK.value)
        mock_chat.assert_called_once()
        sent_messages = mock_chat.call_args.args[0]
        sent_contents = [m["content"] for m in sent_messages]
        self.assertIn("I use Python 3.11", sent_contents)


# ---------------------------------------------------------------------------
# Test 7 — Tool intents do NOT call the language model
# ---------------------------------------------------------------------------

class TestToolIntentsDoNotCallLLM(unittest.TestCase):
    """Existing tool-intent routing must remain completely unaffected.

    SYSTEM_STATUS, FILE_OPERATION, SECURITY_CHECK, and CASUAL_CHAT must all
    produce responses without touching the language model.
    """

    @patch("core.ai.engine.local_model.chat")
    def test_system_status_does_not_call_model(self, mock_chat):
        result = execute_agent_pipeline("Show CPU and RAM usage")
        self.assertEqual(result["intent"], Intent.SYSTEM_STATUS.value)
        self.assertEqual(result["status"], "success")
        mock_chat.assert_not_called()

    @patch("core.ai.engine.local_model.chat")
    def test_file_operation_does_not_call_model(self, mock_chat):
        result = execute_agent_pipeline("List files in the folder")
        self.assertEqual(result["intent"], Intent.FILE_OPERATION.value)
        self.assertEqual(result["status"], "success")
        mock_chat.assert_not_called()

    @patch("core.ai.engine.local_model.chat")
    def test_security_check_does_not_call_model(self, mock_chat):
        result = execute_agent_pipeline("Check TPM device security status")
        self.assertEqual(result["intent"], Intent.SECURITY_CHECK.value)
        self.assertEqual(result["status"], "success")
        mock_chat.assert_not_called()

    @patch("core.ai.engine.local_model.chat")
    def test_casual_chat_does_not_call_model(self, mock_chat):
        result = execute_agent_pipeline("Hello Vault AI")
        self.assertEqual(result["intent"], Intent.CASUAL_CHAT.value)
        self.assertEqual(result["status"], "success")
        mock_chat.assert_not_called()

    @patch("core.ai.engine.local_model.chat")
    def test_system_status_response_contains_cpu(self, mock_chat):
        result = execute_agent_pipeline("Show me system stats and hardware")
        self.assertIn("CPU", result["content"])
        mock_chat.assert_not_called()

    @patch("core.ai.engine.local_model.chat")
    def test_security_check_response_contains_key_info(self, mock_chat):
        result = execute_agent_pipeline("Check TPM security and device identity")
        self.assertIn("Key", result["content"])
        mock_chat.assert_not_called()


# ---------------------------------------------------------------------------
# Test 8 — ConversationManager CRUD interface
# ---------------------------------------------------------------------------

class TestConversationManagerCRUD(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "vault_crud.db"
        self.mgr = _make_manager(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_conversations_empty_on_fresh_db(self):
        self.assertEqual(self.mgr.list_conversations(), [])

    def test_list_conversations_sorted_by_updated_at_desc(self):
        import time
        sid1 = self.mgr.create_conversation("First")
        time.sleep(0.01)
        sid2 = self.mgr.create_conversation("Second")
        # Send a message in sid1 to bump its updated_at
        time.sleep(0.01)
        self.mgr.save_message(sid1, role="user", content="bump")

        listed = self.mgr.list_conversations()
        # sid1 was updated most recently, so it should come first
        self.assertEqual(listed[0]["id"], sid1)

    def test_rename_conversation_updates_title(self):
        sid = self.mgr.create_conversation("Original Title")
        self.mgr.rename_conversation(sid, "Renamed Title")
        conv = self.mgr.list_conversations()[0]
        self.assertEqual(conv["title"], "Renamed Title")

    def test_delete_conversation_removes_session(self):
        sid = self.mgr.create_conversation("To Delete")
        self.mgr.save_message(sid, role="user", content="message")
        self.mgr.delete_conversation(sid)
        self.assertEqual(self.mgr.list_conversations(), [])

    def test_delete_conversation_removes_its_messages(self):
        sid = self.mgr.create_conversation("Delete With Messages")
        self.mgr.save_message(sid, role="user", content="orphan message")
        self.mgr.delete_conversation(sid)
        # Messages for that session should now be gone
        messages = self.mgr.load_messages(sid)
        self.assertEqual(messages, [])

    def test_search_conversations_by_title(self):
        self.mgr.create_conversation("Python Help")
        self.mgr.create_conversation("System Check")
        self.mgr.create_conversation("Python Setup")

        results = self.mgr.list_conversations(search="Python")
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIn("Python", r["title"])


# ---------------------------------------------------------------------------
# Test 9 — Full conversation flow (save → bounded history → pipeline → save)
# ---------------------------------------------------------------------------

class TestFullConversationFlow(unittest.TestCase):
    """End-to-end simulation of the dashboard send_composer_message flow."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "vault_flow.db"
        self.mgr = _make_manager(self.db_path, history_limit=10)
        self.session_id = self.mgr.create_conversation("Flow Test")

    def tearDown(self):
        self.tmp.cleanup()

    @patch("core.ai.engine.local_model.chat", return_value="AI answered the question.")
    def test_full_flow_saves_both_messages(self, mock_chat):
        user_text = "What is machine learning?"

        # Step 1: Save user message
        self.mgr.save_message(self.session_id, role="user", content=user_text)

        # Step 2: Get bounded history for model
        bounded = self.mgr.get_bounded_history(self.session_id)

        # Step 3: Run agent pipeline
        result = execute_agent_pipeline(user_text, conversation_history=bounded)

        # Step 4: Save assistant response
        self.mgr.save_message(
            self.session_id,
            role=result.get("role", "assistant"),
            content=result.get("content", ""),
            intent=result.get("intent", "general"),
            status=result.get("status", "success"),
        )

        # Verify both messages are persisted
        messages = self.mgr.load_messages(self.session_id)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], user_text)
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], "AI answered the question.")

    @patch("core.ai.engine.local_model.chat", return_value="Qwen3 multi-turn answer.")
    def test_multi_turn_history_included_in_later_queries(self, mock_chat):
        # Simulate 3 previous turns
        for i in range(3):
            self.mgr.save_message(self.session_id, role="user", content=f"Turn {i} user")
            self.mgr.save_message(self.session_id, role="assistant", content=f"Turn {i} assistant")

        # New query
        new_query = "Continue the conversation."
        self.mgr.save_message(self.session_id, role="user", content=new_query)
        bounded = self.mgr.get_bounded_history(self.session_id)

        # All 7 messages (6 previous + 1 new) should be within the limit of 10
        self.assertEqual(len(bounded), 7)

        # Run pipeline with history
        execute_agent_pipeline(new_query, conversation_history=bounded)

        # Model should have received all 7 prior messages
        sent_messages = mock_chat.call_args.args[0]
        self.assertGreaterEqual(len(sent_messages), 7)

    @patch("core.ai.engine.local_model.chat")
    def test_tool_intent_in_flow_does_not_call_model(self, mock_chat):
        query = "Show CPU and RAM usage"
        self.mgr.save_message(self.session_id, role="user", content=query)
        bounded = self.mgr.get_bounded_history(self.session_id)
        result = execute_agent_pipeline(query, conversation_history=bounded)

        self.assertEqual(result["intent"], Intent.SYSTEM_STATUS.value)
        mock_chat.assert_not_called()

        # Still save the tool response to DB
        self.mgr.save_message(
            self.session_id,
            role="assistant",
            content=result["content"],
            intent=result["intent"],
        )
        messages = self.mgr.load_messages(self.session_id)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[1]["intent"], "system_status")


if __name__ == "__main__":
    unittest.main()
