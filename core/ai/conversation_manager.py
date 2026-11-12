"""Conversation Manager — persistent session & message lifecycle for Vault AI.

This module is the single authoritative service responsible for:
  - Creating chat sessions
  - Saving user/assistant messages to SQLite
  - Loading full conversation history for display
  - Retrieving a *bounded* recent-message slice safe to send to Qwen3 4B
  - Listing and deleting conversations

It intentionally reuses the existing database helpers from ``database.database``
so the SQLite schema is not duplicated or modified.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from database.database import (
    add_message as _db_add_message,
    create_session as _db_create_session,
    delete_session as _db_delete_session,
    ensure_default_session as _db_ensure_default_session,
    get_session_messages as _db_get_session_messages,
    get_sessions as _db_get_sessions,
    initialize_database as _db_initialize_database,
    update_session_title as _db_update_session_title,
)

# ---------------------------------------------------------------------------
# History-bounding constants
# ---------------------------------------------------------------------------
# Maximum number of past messages (user + assistant turns) forwarded to the
# local model per request.  This prevents unbounded context growth and keeps
# inference latency predictable on CPU-only hardware.
#
# A value of 20 corresponds to 10 full back-and-forth exchanges — adequate for
# conversational continuity without saturating the Qwen3 4B context window.
DEFAULT_HISTORY_LIMIT = 20


class ConversationManager:
    """Manage persistent chat sessions and bounded model history.

    Parameters
    ----------
    db_path:
        Optional path to the SQLite database file.  When *None* (default) the
        shared production database is used.  Pass a temporary path in tests to
        achieve full isolation.
    history_limit:
        Maximum number of messages (combined user + assistant) included in the
        bounded history slice sent to the local language model.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> None:
        self._db_path = db_path
        self.history_limit = history_limit
        # Ensure schema exists on first use.
        _db_initialize_database(self._db_path)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_conversation(self, title: str = "New Chat") -> int:
        """Create a new chat session and return its integer ID."""
        return _db_create_session(title, db_path=self._db_path)

    def get_or_create_default(self) -> int:
        """Return the most-recent session ID, creating one if none exist."""
        return _db_ensure_default_session(db_path=self._db_path)

    def list_conversations(self, search: str = "") -> list[dict[str, Any]]:
        """Return all sessions sorted by ``updated_at`` descending.

        Each entry is a dict with keys: ``id``, ``title``, ``created_at``,
        ``updated_at``.
        """
        return _db_get_sessions(search=search, db_path=self._db_path)

    def rename_conversation(self, session_id: int, title: str) -> None:
        """Update the display title of *session_id*."""
        _db_update_session_title(session_id, title, db_path=self._db_path)

    def delete_conversation(self, session_id: int) -> None:
        """Permanently delete *session_id* and all its messages."""
        _db_delete_session(session_id, db_path=self._db_path)

    # ------------------------------------------------------------------
    # Message persistence
    # ------------------------------------------------------------------

    def save_message(
        self,
        session_id: int,
        role: str,
        content: str,
        intent: str = "general",
        status: str = "success",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Persist a single message and bump the session ``updated_at`` stamp.

        Parameters
        ----------
        session_id:
            Target chat session.
        role:
            ``"user"``, ``"assistant"``, or ``"system"``.
        content:
            Plain-text message body.
        intent:
            Routing intent label (e.g. ``"general_query"``, ``"system_status"``).
        status:
            ``"success"`` or ``"error"``.
        metadata:
            Optional free-form JSON-serialisable dict stored alongside the row.

        Returns
        -------
        int
            The auto-assigned row ID of the new message.
        """
        return _db_add_message(
            session_id,
            role=role,
            content=content,
            intent=intent,
            status=status,
            metadata=metadata,
            db_path=self._db_path,
        )

    def load_messages(self, session_id: int) -> list[dict[str, Any]]:
        """Return *all* persisted messages for *session_id* in chronological order.

        Used by the UI to render the full conversation feed.
        """
        return _db_get_session_messages(session_id, db_path=self._db_path)

    # ------------------------------------------------------------------
    # Bounded history for the local model
    # ------------------------------------------------------------------

    def get_bounded_history(self, session_id: int) -> list[dict[str, str]]:
        """Return the most-recent ``history_limit`` messages as a simple list.

        Only ``user`` and ``assistant`` roles are included (system messages are
        injected separately by ``OllamaService.chat``).  The returned list is
        in chronological order so the model sees the conversation correctly.

        This is the slice that should be passed to
        ``execute_agent_pipeline(conversation_history=...)``.
        """
        all_messages = _db_get_session_messages(session_id, db_path=self._db_path)

        # Filter to roles the model understands and that carry conversational context.
        model_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in all_messages
            if msg.get("role") in {"user", "assistant"} and msg.get("content")
        ]

        # Take only the tail so older context doesn't inflate the prompt.
        return model_messages[-self.history_limit :]
