import tempfile
import time
import unittest
from pathlib import Path

from core.auth import (
    LOCKOUT_DURATION_SECONDS,
    MAX_FAILED_ATTEMPTS,
    create_user,
    get_lockout_status,
    record_failed_attempt,
    reset_failed_attempts,
    verify_user,
)
from database import get_connection


class AuthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_directory.name) / "test_vault_ai.db"

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_registers_user_with_a_hash_not_plaintext_password(self) -> None:
        password = "correct-horse-battery-staple"

        self.assertTrue(create_user("alice", password, db_path=self.db_path))
        self.assertFalse(create_user("alice", password, db_path=self.db_path))

        connection = get_connection(self.db_path)
        try:
            stored_hash = connection.execute(
                "SELECT password_hash FROM users WHERE username = ?", ("alice",)
            ).fetchone()["password_hash"]
        finally:
            connection.close()

        self.assertNotEqual(stored_hash, password)
        self.assertTrue(stored_hash.startswith("scrypt$"))

    def test_verifies_correct_password_and_rejects_invalid_credentials(self) -> None:
        create_user("alice", "correct-password", db_path=self.db_path)

        self.assertTrue(verify_user("alice", "correct-password", db_path=self.db_path))
        self.assertFalse(verify_user("alice", "wrong-password", db_path=self.db_path))
        self.assertFalse(verify_user("unknown", "correct-password", db_path=self.db_path))

    def test_locks_out_after_five_failed_attempts_and_resets(self) -> None:
        create_user("alice", "correct-password", db_path=self.db_path)

        for attempt in range(1, 5):
            attempts, remaining = record_failed_attempt("alice", db_path=self.db_path)
            self.assertEqual(attempts, attempt)
            self.assertEqual(remaining, 0.0)
            status_attempts, status_remaining = get_lockout_status("alice", db_path=self.db_path)
            self.assertEqual(status_attempts, attempt)
            self.assertEqual(status_remaining, 0.0)

        # 5th failed attempt triggers 10 minute lockout
        attempts, remaining = record_failed_attempt("alice", db_path=self.db_path)
        self.assertEqual(attempts, 5)
        self.assertGreater(remaining, 590.0)
        self.assertLessEqual(remaining, 600.0)

        status_attempts, status_remaining = get_lockout_status("alice", db_path=self.db_path)
        self.assertEqual(status_attempts, 5)
        self.assertGreater(status_remaining, 0.0)

        # Reset failed attempts on success
        reset_failed_attempts("alice", db_path=self.db_path)
        status_attempts, status_remaining = get_lockout_status("alice", db_path=self.db_path)
        self.assertEqual(status_attempts, 0)
        self.assertEqual(status_remaining, 0.0)


if __name__ == "__main__":
    unittest.main()
