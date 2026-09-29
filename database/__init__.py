"""SQLite database package for Vault AI."""

from .database import (
    DEFAULT_DATABASE_PATH,
    add_message,
    create_session,
    delete_session,
    ensure_default_session,
    get_connection,
    get_session_messages,
    get_sessions,
    initialize_database,
    update_session_title,
)

__all__ = [
    "DEFAULT_DATABASE_PATH",
    "add_message",
    "create_session",
    "delete_session",
    "ensure_default_session",
    "get_connection",
    "get_session_messages",
    "get_sessions",
    "initialize_database",
    "update_session_title",
]
