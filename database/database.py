"""SQLite helpers for Vault AI's local application data."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "vault_ai.db"


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Return a connection to the Vault AI SQLite database."""
    path = Path(db_path) if db_path is not None else DEFAULT_DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(db_path: str | Path | None = None) -> None:
    """Create the schema required by Vault AI, if it does not exist."""
    connection = get_connection(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until REAL NOT NULL DEFAULT 0
            )
            """
        )
        columns = [row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()]
        if "failed_attempts" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0")
        if "locked_until" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN locked_until REAL NOT NULL DEFAULT 0")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                device_name TEXT NOT NULL,
                hardware_fingerprint TEXT NOT NULL,
                public_key TEXT NOT NULL,
                key_identifier TEXT NOT NULL DEFAULT '',
                key_provider TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'trusted',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_verified_at TEXT,
                FOREIGN KEY (username) REFERENCES users(username)
            )
            """
        )
        dev_columns = [row["name"] for row in connection.execute("PRAGMA table_info(devices)").fetchall()]
        if "key_identifier" not in dev_columns:
            connection.execute("ALTER TABLE devices ADD COLUMN key_identifier TEXT NOT NULL DEFAULT ''")
        if "key_provider" not in dev_columns:
            connection.execute("ALTER TABLE devices ADD COLUMN key_provider TEXT NOT NULL DEFAULT ''")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                intent TEXT NOT NULL DEFAULT 'general',
                status TEXT NOT NULL DEFAULT 'success',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            )
            """
        )

        connection.commit()
    finally:
        connection.close()


def create_session(title: str = "New Chat", db_path: str | Path | None = None) -> int:
    """Create a new chat session and return its id."""
    initialize_database(db_path)
    connection = get_connection(db_path)
    try:
        cur = connection.execute(
            "INSERT INTO chat_sessions (title, updated_at) VALUES (?, CURRENT_TIMESTAMP)",
            (title,),
        )
        connection.commit()
        return int(cur.lastrowid)
    finally:
        connection.close()


def get_sessions(search: str = "", db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Retrieve all chat sessions sorted by updated_at, optionally filtered by title."""
    initialize_database(db_path)
    connection = get_connection(db_path)
    try:
        if search:
            rows = connection.execute(
                "SELECT * FROM chat_sessions WHERE title LIKE ? ORDER BY updated_at DESC",
                (f"%{search}%",),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM chat_sessions ORDER BY updated_at DESC"
            ).fetchall()

        return [
            {
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
    finally:
        connection.close()


def get_session_messages(session_id: int, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Retrieve all messages for a given session."""
    initialize_database(db_path)
    connection = get_connection(db_path)
    try:
        rows = connection.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()

        messages = []
        for row in rows:
            try:
                meta = json.loads(row["metadata_json"])
            except Exception:
                meta = {}

            messages.append({
                "id": row["id"],
                "session_id": row["session_id"],
                "role": row["role"],
                "content": row["content"],
                "intent": row["intent"],
                "status": row["status"],
                "metadata": meta,
                "created_at": row["created_at"],
            })
        return messages
    finally:
        connection.close()


def add_message(
    session_id: int,
    role: str,
    content: str,
    intent: str = "general",
    status: str = "success",
    metadata: dict[str, Any] | None = None,
    db_path: str | Path | None = None,
) -> int:
    """Add a message to a session and update the session timestamp."""
    initialize_database(db_path)
    meta_json = json.dumps(metadata or {})
    connection = get_connection(db_path)
    try:
        cur = connection.execute(
            """
            INSERT INTO chat_messages (session_id, role, content, intent, status, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (session_id, role, content, intent, status, meta_json),
        )
        connection.execute(
            "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )
        connection.commit()
        return int(cur.lastrowid)
    finally:
        connection.close()


def update_session_title(session_id: int, title: str, db_path: str | Path | None = None) -> None:
    """Update title for a session."""
    initialize_database(db_path)
    connection = get_connection(db_path)
    try:
        connection.execute(
            "UPDATE chat_sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, session_id),
        )
        connection.commit()
    finally:
        connection.close()


def delete_session(session_id: int, db_path: str | Path | None = None) -> None:
    """Delete a chat session and all its messages."""
    initialize_database(db_path)
    connection = get_connection(db_path)
    try:
        connection.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        connection.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        connection.commit()
    finally:
        connection.close()


def ensure_default_session(db_path: str | Path | None = None) -> int:
    """Return the ID of the most recent session, or create one if none exist."""
    sessions = get_sessions(db_path=db_path)
    if sessions:
        return sessions[0]["id"]
    return create_session("Initial Workspace", db_path=db_path)
