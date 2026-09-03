"""Tests for hardware fingerprinting, OS/TPM cryptographic keypair, and device security."""

import os
import tempfile
import unittest
from pathlib import Path

from core.auth import create_user
from core.device import (
    DeviceKeyHandle,
    check_hardware_compatibility,
    check_network_environment,
    check_security_environment,
    delete_device_private_key,
    generate_device_keypair,
    get_hardware_fingerprint,
    get_hardware_identifiers,
    get_key_storage_info,
    load_device_private_key,
    load_public_key_from_pem,
    public_key_to_pem,
    register_device,
    save_device_private_key,
    sign_device_challenge,
    verify_device,
    verify_device_signature,
)
from database import get_connection


class DeviceSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_devices.db"
        self.test_key_name = "test_unit_device_key"
        create_user("testuser", "CorrectPassword123!", db_path=self.db_path)

    def tearDown(self) -> None:
        delete_device_private_key(self.test_key_name)
        delete_device_private_key("VaultAI_Device_testuser")
        self.temp_dir.cleanup()

    def test_extracts_real_hardware_identifiers(self) -> None:
        ids = get_hardware_identifiers()
        self.assertIn("machine_guid", ids)
        self.assertIn("motherboard_uuid", ids)
        self.assertIn("processor_id", ids)
        self.assertIn("mac_address", ids)
        self.assertIn("hostname", ids)
        self.assertTrue(len(ids["hostname"]) > 0)
        self.assertTrue(len(ids["mac_address"]) > 0)

    def test_generates_unique_deterministic_hardware_fingerprint(self) -> None:
        fp1 = get_hardware_fingerprint()
        fp2 = get_hardware_fingerprint()
        self.assertEqual(fp1, fp2)
        self.assertTrue(fp1.startswith("hw_fp_"))
        self.assertEqual(len(fp1), 6 + 64)  # 'hw_fp_' + 64 hex chars

    def test_cryptographic_keypair_generation_and_signing(self) -> None:
        private_key, public_key = generate_device_keypair(self.test_key_name)
        self.assertIsInstance(private_key, DeviceKeyHandle)
        self.assertTrue(private_key.exists())

        pem = public_key_to_pem(public_key)
        self.assertIn("BEGIN PUBLIC KEY", pem)

        reloaded_pub = load_public_key_from_pem(pem)
        challenge = b"Vault-AI-Random-Nonce-12345"
        signature = sign_device_challenge(private_key, challenge)

        self.assertTrue(verify_device_signature(reloaded_pub, signature, challenge))
        self.assertFalse(verify_device_signature(reloaded_pub, signature, b"Tampered-Nonce"))

    def test_private_key_is_non_exportable(self) -> None:
        private_key, _ = generate_device_keypair(self.test_key_name)
        self.assertFalse(private_key.is_exportable)

        info = get_key_storage_info(self.test_key_name)
        self.assertTrue(info["key_present"])
        self.assertTrue(info["non_exportable"])
        self.assertIn(info["provider"], ("tpm", "software_ksp", "memory_fallback"))

    def test_no_plaintext_private_key_written_to_workspace(self) -> None:
        workspace_dir = Path(__file__).resolve().parents[1]
        legacy_key_file = workspace_dir / ".vault_device_private.key"

        private_key, _ = generate_device_keypair(self.test_key_name)
        save_device_private_key(private_key, self.test_key_name)

        # Confirm zero plaintext private key files exist in the project root
        self.assertFalse(legacy_key_file.exists())

    def test_save_and_load_private_key(self) -> None:
        private_key, _ = generate_device_keypair(self.test_key_name)
        saved_handle = save_device_private_key(private_key, self.test_key_name)
        self.assertTrue(saved_handle.exists())

        loaded_key = load_device_private_key(self.test_key_name)
        self.assertIsNotNone(loaded_key)
        self.assertTrue(loaded_key.exists())

    def test_register_and_verify_device_flow(self) -> None:
        reg_result = register_device(
            "testuser",
            db_path=self.db_path,
            key_path=self.test_key_name,
        )
        self.assertTrue(reg_result["success"])
        self.assertTrue(reg_result["steps"]["key_pair_generated"])
        self.assertTrue(reg_result["steps"]["private_key_protected"])
        self.assertTrue(reg_result["steps"]["device_identity_registered"])
        self.assertTrue(reg_result["steps"]["hardware_compatible"])

        # Check SQLite DB
        conn = get_connection(self.db_path)
        row = conn.execute("SELECT * FROM devices WHERE username = ?", ("testuser",)).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "trusted")
        self.assertTrue(row["public_key"].startswith("-----BEGIN PUBLIC KEY-----"))

        # Verify device
        verify_result = verify_device(
            "testuser",
            db_path=self.db_path,
            key_path=self.test_key_name,
        )
        self.assertTrue(verify_result["is_trusted"])
        self.assertFalse(verify_result["risk_high"])
        self.assertTrue(verify_result["steps"]["cryptographic_identity"])
        self.assertTrue(verify_result["steps"]["registered_device"])
        self.assertTrue(verify_result["steps"]["security_environment"])

    def test_verify_fails_for_unregistered_user(self) -> None:
        verify_result = verify_device(
            "unregistered_user",
            db_path=self.db_path,
            key_path="non_existent_key_name",
        )
        self.assertFalse(verify_result["is_trusted"])
        self.assertTrue(verify_result["risk_high"])


if __name__ == "__main__":
    unittest.main()
