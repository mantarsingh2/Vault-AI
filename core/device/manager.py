"""Device security registration and verification manager for Vault AI."""

from __future__ import annotations

import os
import platform
import secrets
import socket
from pathlib import Path
from typing import Any, Callable

from database import get_connection, initialize_database
from core.device.crypto import (
    DEFAULT_DEVICE_KEY_NAME,
    generate_device_keypair,
    load_device_private_key,
    load_public_key_from_pem,
    public_key_to_pem,
    save_device_private_key,
    sign_device_challenge,
    verify_device_signature,
)
from core.device.hardware import (
    check_hardware_compatibility,
    check_network_environment,
    check_security_environment,
    get_hardware_fingerprint,
    get_hardware_identifiers,
)


def register_device(
    username: str,
    *,
    db_path: str | Path | None = None,
    key_path: str | Path | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    """Execute complete device security registration (Create Vault flow).

    Performs the 4 setup steps:
    1. Cryptographic key pair generated (OS/TPM protected non-exportable key)
    2. Private key protected inside Windows TPM/CNG boundary
    3. Device identity registered in database
    4. Hardware compatibility check
    """
    initialize_database(db_path)
    device_name = platform.node() or socket.gethostname() or "UnknownDevice"
    hardware_fingerprint = get_hardware_fingerprint()

    key_identifier = key_path if key_path is not None else DEFAULT_DEVICE_KEY_NAME

    # Step 1: Generate cryptographic keypair directly in TPM/OS KSP
    private_key, public_key = generate_device_keypair(key_identifier)
    public_pem = public_key_to_pem(public_key)
    key_provider = private_key.provider_name
    if progress_callback:
        progress_callback(1, "key_pair_generated")

    # Step 2: Ensure private key is safely stored and protected
    saved_key_handle = save_device_private_key(private_key, key_identifier)
    is_protected = bool(saved_key_handle and saved_key_handle.exists())
    if progress_callback:
        progress_callback(2, "private_key_protected")

    # Step 3: Register device identity in SQLite database
    connection = get_connection(db_path)
    try:
        # Check if existing device record exists for this username and fingerprint
        existing = connection.execute(
            "SELECT id FROM devices WHERE username = ? AND hardware_fingerprint = ?",
            (username, hardware_fingerprint),
        ).fetchone()

        if existing:
            connection.execute(
                """
                UPDATE devices 
                SET device_name = ?, public_key = ?, key_identifier = ?, key_provider = ?, status = 'trusted', last_verified_at = CURRENT_TIMESTAMP 
                WHERE id = ?
                """,
                (device_name, public_pem, key_identifier, key_provider, existing["id"]),
            )
        else:
            connection.execute(
                """
                INSERT INTO devices (username, device_name, hardware_fingerprint, public_key, key_identifier, key_provider, status)
                VALUES (?, ?, ?, ?, ?, ?, 'trusted')
                """,
                (username, device_name, hardware_fingerprint, public_pem, key_identifier, key_provider),
            )
        connection.commit()
        db_registered = True
    except Exception:
        db_registered = False
    finally:
        connection.close()

    if progress_callback:
        progress_callback(3, "device_identity_registered")

    # Step 4: Hardware checking
    hw_check = check_hardware_compatibility()
    if progress_callback:
        progress_callback(4, "hardware_compatible")

    is_protected = bool(saved_key_handle and saved_key_handle.exists())

    return {
        "success": bool(is_protected and db_registered and hw_check["compatible"]),
        "device_name": device_name,
        "hardware_fingerprint": hardware_fingerprint,
        "public_key": public_pem,
        "key_identifier": key_identifier,
        "key_provider": key_provider,
        "steps": {
            "key_pair_generated": True,
            "private_key_protected": is_protected,
            "device_identity_registered": db_registered,
            "hardware_compatible": hw_check["compatible"],
        },
        "hardware_info": hw_check,
    }


def verify_device(
    username: str,
    *,
    db_path: str | Path | None = None,
    key_path: str | Path | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    """Execute complete device verification (Login / Unlock Vault flow).

    Performs the 4 verification checks:
    1. Cryptographic identity: Validating device key and signature
    2. Registered device: Checking device registration status in DB
    3. Security environment: Analyzing system and OS integrity
    4. Network environment: Checking network adapter & connectivity
    """
    initialize_database(db_path)
    current_fingerprint = get_hardware_fingerprint()

    # Query DB device row
    connection = get_connection(db_path)
    device_row = None
    try:
        device_row = connection.execute(
            "SELECT * FROM devices WHERE username = ? AND hardware_fingerprint = ?",
            (username, current_fingerprint),
        ).fetchone()
    finally:
        connection.close()

    # 1. Cryptographic signature verification using OS/TPM key
    if key_path is not None:
        key_identifier = key_path
    elif device_row is not None and "key_identifier" in device_row.keys() and device_row["key_identifier"]:
        key_identifier = device_row["key_identifier"]
    else:
        key_identifier = DEFAULT_DEVICE_KEY_NAME

    private_key = load_device_private_key(key_identifier)
    crypto_valid = False

    if private_key is not None and device_row is not None:
        try:
            public_key = load_public_key_from_pem(device_row["public_key"])
            challenge = secrets.token_bytes(32)
            signature = sign_device_challenge(private_key, challenge)
            crypto_valid = verify_device_signature(public_key, signature, challenge)
        except Exception:
            crypto_valid = False

    if progress_callback:
        progress_callback(1, "cryptographic_identity")

    # 2. Check DB registration
    registered_device = device_row is not None and device_row["status"] == "trusted"
    if registered_device:
        conn = get_connection(db_path)
        try:
            conn.execute(
                "UPDATE devices SET last_verified_at = CURRENT_TIMESTAMP WHERE id = ?",
                (device_row["id"],),
            )
            conn.commit()
        finally:
            conn.close()

    if progress_callback:
        progress_callback(2, "registered_device")

    # 3. Security environment check
    sec_env = check_security_environment()
    if progress_callback:
        progress_callback(3, "security_environment")

    # 4. Network environment check
    net_env = check_network_environment()
    if progress_callback:
        progress_callback(4, "network_environment")

    is_trusted = bool(registered_device and crypto_valid and sec_env["secure"])
    risk_high = not is_trusted

    return {
        "is_trusted": is_trusted,
        "risk_high": risk_high,
        "hardware_fingerprint": current_fingerprint,
        "steps": {
            "cryptographic_identity": crypto_valid,
            "registered_device": registered_device,
            "security_environment": sec_env["secure"],
            "network_environment": net_env["connected"],
        },
        "details": {
            "security": sec_env,
            "network": net_env,
        },
    }
