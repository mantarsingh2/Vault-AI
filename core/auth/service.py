"""Registration and password verification for local Vault AI users."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sqlite3
import time
from pathlib import Path

from database import get_connection, initialize_database


_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 600  # 10 minutes


def _normalise_username(username: str) -> str:
    if not isinstance(username, str):
        raise ValueError("Username must be a string.")

    normalised = username.strip()
    if not normalised:
        raise ValueError("Username cannot be empty.")
    return normalised


def _validate_password(password: str) -> None:
    if not isinstance(password, str) or not password:
        raise ValueError("Password cannot be empty.")


def _hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    encoded_salt = base64.b64encode(salt).decode("ascii")
    encoded_key = base64.b64encode(derived_key).decode("ascii")
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${encoded_salt}${encoded_key}"


def _password_matches(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n, r, p, encoded_salt, encoded_key = stored_hash.split("$")
        if algorithm != "scrypt":
            return False

        salt = base64.b64decode(encoded_salt.encode("ascii"), validate=True)
        expected_key = base64.b64decode(encoded_key.encode("ascii"), validate=True)
        actual_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected_key),
        )
    except (ValueError, TypeError, UnicodeError):
        return False

    return hmac.compare_digest(actual_key, expected_key)


def create_user(username: str, password: str, *, db_path: str | Path | None = None) -> bool:
    """Create a user with a salted password hash.

    Returns ``True`` when created and ``False`` when the username already exists.
    ``db_path`` is optional to support isolated tests.
    """
    username = _normalise_username(username)
    _validate_password(password)
    initialize_database(db_path)

    try:
        connection = get_connection(db_path)
        try:
            connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, _hash_password(password)),
            )
            connection.commit()
        finally:
            connection.close()
    except sqlite3.IntegrityError:
        return False

    return True


def verify_user(username: str, password: str, *, db_path: str | Path | None = None) -> bool:
    """Return whether ``password`` is valid for ``username``."""
    try:
        username = _normalise_username(username)
        _validate_password(password)
    except ValueError:
        return False

    initialize_database(db_path)
    connection = get_connection(db_path)
    try:
        row = connection.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        connection.close()

    return row is not None and _password_matches(password, row["password_hash"])


def get_lockout_status(username: str, *, db_path: str | Path | None = None) -> tuple[int, float]:
    """Return (failed_attempts, remaining_lockout_seconds) for the user.

    If lockout expired, resets failed_attempts and locked_until to 0.
    """
    try:
        username = _normalise_username(username)
    except ValueError:
        return (0, 0.0)

    initialize_database(db_path)
    connection = get_connection(db_path)
    try:
        row = connection.execute(
            "SELECT failed_attempts, locked_until FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row is None:
            return (0, 0.0)

        failed_attempts = row["failed_attempts"] or 0
        locked_until = row["locked_until"] or 0.0
        now = time.time()

        if locked_until > now:
            return (failed_attempts, locked_until - now)
        elif locked_until > 0:
            connection.execute(
                "UPDATE users SET failed_attempts = 0, locked_until = 0 WHERE username = ?",
                (username,),
            )
            connection.commit()
            return (0, 0.0)

        return (failed_attempts, 0.0)
    finally:
        connection.close()


def record_failed_attempt(username: str, *, db_path: str | Path | None = None) -> tuple[int, float]:
    """Record a failed login attempt. If failed_attempts >= 5, lock for 10 minutes.

    Returns (new_failed_attempts, remaining_lockout_seconds).
    """
    try:
        username = _normalise_username(username)
    except ValueError:
        return (0, 0.0)

    initialize_database(db_path)
    connection = get_connection(db_path)
    try:
        row = connection.execute(
            "SELECT failed_attempts, locked_until FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row is None:
            return (0, 0.0)

        now = time.time()
        locked_until = row["locked_until"] or 0.0

        if locked_until > now:
            return (row["failed_attempts"] or 0, locked_until - now)

        current_attempts = (row["failed_attempts"] or 0) if locked_until == 0 else 0
        new_attempts = current_attempts + 1

        if new_attempts >= MAX_FAILED_ATTEMPTS:
            new_locked_until = now + LOCKOUT_DURATION_SECONDS
            connection.execute(
                "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE username = ?",
                (new_attempts, new_locked_until, username),
            )
            connection.commit()
            return (new_attempts, float(LOCKOUT_DURATION_SECONDS))
        else:
            connection.execute(
                "UPDATE users SET failed_attempts = ?, locked_until = 0 WHERE username = ?",
                (new_attempts, username),
            )
            connection.commit()
            return (new_attempts, 0.0)
    finally:
        connection.close()


def reset_failed_attempts(username: str, *, db_path: str | Path | None = None) -> None:
    """Reset failed attempts and lockout timestamp for username."""
    try:
        username = _normalise_username(username)
    except ValueError:
        return

    initialize_database(db_path)
    connection = get_connection(db_path)
    try:
        connection.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = 0 WHERE username = ?",
            (username,),
        )
        connection.commit()
    finally:
        connection.close()
