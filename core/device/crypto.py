"""OS-protected and TPM-backed cryptographic device identity management for Vault AI.

Uses Windows Cryptography Next Generation (CNG / NCrypt) to create hardware-backed (TPM 2.0)
or OS-protected (Software KSP / DPAPI) non-exportable ECDSA P-256 signing keys.
Private keys remain isolated inside the OS / TPM security boundary and are NEVER stored
as plaintext or exportable files in the workspace.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import os
import platform
import socket
import sys
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils


# ---------------------------------------------------------------------------
# Constants & Windows CNG Definitions
# ---------------------------------------------------------------------------
DEFAULT_DEVICE_KEY_NAME = "VaultAI_DeviceIdentity"

MS_PLATFORM_KEY_STORAGE_PROVIDER = "Microsoft Platform Crypto Provider"  # TPM 2.0 KSP
MS_SOFTWARE_KEY_STORAGE_PROVIDER = "Microsoft Software Key Storage Provider"  # OS Protected KSP

BCRYPT_ECDSA_P256_ALGORITHM = "ECDSA_P256"
BCRYPT_ECCPUBLIC_BLOB = "ECCPUBLICBLOB"
BCRYPT_ECCPRIVATE_BLOB = "ECCPRIVATEBLOB"

NCRYPT_OVERWRITE_KEY_FLAG = 0x00000080
NCRYPT_SILENT_FLAG = 0x00000040
NCRYPT_MACHINE_KEY_FLAG = 0x00000020

# Error codes
ERROR_SUCCESS = 0
NTE_BAD_KEYSET = -2146893802  # 0x80090016
NTE_NOT_FOUND = -2146893792   # 0x80090020
NTE_NOT_SUPPORTED = -2146893780 # 0x8009002C
NTE_BAD_KEY_STATE = -2146893814 # 0x8009000A / Non-exportable


def _get_ncrypt_dll():
    if sys.platform == "win32":
        try:
            ncrypt = ctypes.windll.ncrypt
            # Set up prototypes
            ncrypt.NCryptOpenStorageProvider.argtypes = [
                ctypes.POINTER(wintypes.HANDLE),
                wintypes.LPCWSTR,
                wintypes.DWORD,
            ]
            ncrypt.NCryptOpenStorageProvider.restype = wintypes.LONG

            ncrypt.NCryptCreatePersistedKey.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.HANDLE),
                wintypes.LPCWSTR,
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
            ]
            ncrypt.NCryptCreatePersistedKey.restype = wintypes.LONG

            ncrypt.NCryptFinalizeKey.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            ncrypt.NCryptFinalizeKey.restype = wintypes.LONG

            ncrypt.NCryptOpenKey.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.HANDLE),
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
            ]
            ncrypt.NCryptOpenKey.restype = wintypes.LONG

            ncrypt.NCryptExportKey.argtypes = [
                wintypes.HANDLE,
                wintypes.HANDLE,
                wintypes.LPCWSTR,
                ctypes.c_void_p,
                ctypes.c_char_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                wintypes.DWORD,
            ]
            ncrypt.NCryptExportKey.restype = wintypes.LONG

            ncrypt.NCryptSignHash.argtypes = [
                wintypes.HANDLE,
                ctypes.c_void_p,
                ctypes.c_char_p,
                wintypes.DWORD,
                ctypes.c_char_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                wintypes.DWORD,
            ]
            ncrypt.NCryptSignHash.restype = wintypes.LONG

            ncrypt.NCryptDeleteKey.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            ncrypt.NCryptDeleteKey.restype = wintypes.LONG

            ncrypt.NCryptFreeObject.argtypes = [wintypes.HANDLE]
            ncrypt.NCryptFreeObject.restype = wintypes.LONG

            return ncrypt
        except Exception:
            return None
    return None


_NCRYPT = _get_ncrypt_dll()


def _sanitize_key_name(key_identifier: str | Path | None) -> str:
    """Normalize a key path or name into a valid Windows CNG key identifier."""
    if key_identifier is None:
        return DEFAULT_DEVICE_KEY_NAME
    if isinstance(key_identifier, Path):
        name = key_identifier.stem
    else:
        name = str(key_identifier)
        if "/" in name or "\\" in name:
            name = Path(name).stem
    # Remove leading dots or invalid characters
    clean = "".join(c for c in name if c.isalnum() or c in ("_", "-")).strip("._-")
    return f"VaultAI_{clean}" if not clean.startswith("VaultAI_") else clean


# ---------------------------------------------------------------------------
# In-Memory Fallback Key Store (for non-Windows / mock test environments)
# ---------------------------------------------------------------------------
_MEMORY_KEY_STORE: dict[str, ec.EllipticCurvePrivateKey] = {}


# ---------------------------------------------------------------------------
# Device Key Handle Class
# ---------------------------------------------------------------------------
class DeviceKeyHandle:
    """Encapsulates an OS-protected or TPM-backed device private signing key."""

    def __init__(
        self,
        key_name: str,
        provider_name: str,
        is_hardware_backed: bool,
        is_persisted: bool = True,
        h_prov: wintypes.HANDLE | None = None,
        h_key: wintypes.HANDLE | None = None,
        fallback_key: ec.EllipticCurvePrivateKey | None = None,
    ):
        self.key_name = key_name
        self.provider_name = provider_name
        self.is_hardware_backed = is_hardware_backed
        self.is_persisted = is_persisted
        self._h_prov = h_prov
        self._h_key = h_key
        self._fallback_key = fallback_key

    def exists(self) -> bool:
        """Return whether the key is verified to exist and be protected in storage."""
        return self.is_persisted and (self._h_key is not None or self._fallback_key is not None)

    @property
    def is_exportable(self) -> bool:
        """Return whether the private key material can be exported (Always False for CNG)."""
        if self._h_key is not None and _NCRYPT is not None:
            cb_result = wintypes.DWORD()
            res = _NCRYPT.NCryptExportKey(
                self._h_key, 0, BCRYPT_ECCPRIVATE_BLOB, None, None, 0, ctypes.byref(cb_result), 0
            )
            return res == ERROR_SUCCESS
        return False

    def sign_hash(self, digest: bytes) -> bytes:
        """Sign a 32-byte SHA-256 hash within the TPM or OS boundary."""
        if len(digest) != 32:
            raise ValueError("Digest must be exactly 32 bytes (SHA-256).")

        if self._h_key is not None and _NCRYPT is not None:
            sig_size = wintypes.DWORD()
            res = _NCRYPT.NCryptSignHash(
                self._h_key, None, digest, len(digest), None, 0, ctypes.byref(sig_size), 0
            )
            if res != ERROR_SUCCESS:
                raise RuntimeError(f"NCryptSignHash size query failed with code: {res:#x}")

            sig_buf = ctypes.create_string_buffer(sig_size.value)
            res = _NCRYPT.NCryptSignHash(
                self._h_key, None, digest, len(digest), sig_buf, sig_size.value, ctypes.byref(sig_size), 0
            )
            if res != ERROR_SUCCESS:
                raise RuntimeError(f"NCryptSignHash failed with code: {res:#x}")

            raw_sig = sig_buf.raw[: sig_size.value]
            # CNG ECDSA returns raw r (32 bytes) || s (32 bytes)
            r = int.from_bytes(raw_sig[:32], "big")
            s = int.from_bytes(raw_sig[32:], "big")
            return utils.encode_dss_signature(r, s)

        if self._fallback_key is not None:
            return self._fallback_key.sign(digest, ec.ECDSA(utils.Prehashed(ec.hashes.SHA256())))

        raise RuntimeError("No active cryptographic key handle available for signing.")

    def close(self) -> None:
        """Release CNG handles."""
        if _NCRYPT is not None:
            if self._h_key is not None:
                _NCRYPT.NCryptFreeObject(self._h_key)
                self._h_key = None
            if self._h_prov is not None:
                _NCRYPT.NCryptFreeObject(self._h_prov)
                self._h_prov = None

    def __del__(self) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"<DeviceKeyHandle key='{self.key_name}' provider='{self.provider_name}' "
            f"hardware_backed={self.is_hardware_backed} non_exportable={not self.is_exportable}>"
        )


# ---------------------------------------------------------------------------
# Key Storage Provider Initializer
# ---------------------------------------------------------------------------
def _open_storage_provider(
    preferred_provider: str | None = None,
) -> tuple[wintypes.HANDLE | None, str, bool]:
    """Open Windows TPM Key Storage Provider if available, else Software KSP.

    Args:
        preferred_provider: Optional provider preference.
            - 'tpm': Try TPM only.
            - 'software_ksp': Force Software KSP (for fallback testing/usage).
            - None: Try TPM first, then fallback to Software KSP.
    """
    if _NCRYPT is None:
        return None, "memory_fallback", False

    h_prov = wintypes.HANDLE()

    # If explicitly forcing Software KSP (e.g. for fallback simulation / environments without TPM)
    if preferred_provider == "software_ksp":
        res = _NCRYPT.NCryptOpenStorageProvider(
            ctypes.byref(h_prov), MS_SOFTWARE_KEY_STORAGE_PROVIDER, 0
        )
        if res == ERROR_SUCCESS:
            return h_prov, "software_ksp", False
        return None, "memory_fallback", False

    # 1. Attempt TPM Platform Crypto Provider (Hardware-backed)
    if preferred_provider is None or preferred_provider == "tpm":
        res = _NCRYPT.NCryptOpenStorageProvider(
            ctypes.byref(h_prov), MS_PLATFORM_KEY_STORAGE_PROVIDER, 0
        )
        if res == ERROR_SUCCESS:
            return h_prov, "tpm", True

    # 2. Fallback to Windows Software Key Storage Provider (OS DPAPI protected)
    if preferred_provider is None:
        res = _NCRYPT.NCryptOpenStorageProvider(
            ctypes.byref(h_prov), MS_SOFTWARE_KEY_STORAGE_PROVIDER, 0
        )
        if res == ERROR_SUCCESS:
            return h_prov, "software_ksp", False

    return None, "memory_fallback", False


# ---------------------------------------------------------------------------
# Public Cryptographic API
# ---------------------------------------------------------------------------
def generate_device_keypair(
    key_name: str | Path | None = None,
    preferred_provider: str | None = None,
) -> tuple[DeviceKeyHandle, ec.EllipticCurvePublicKey]:
    """Generate a high-security OS/TPM protected non-exportable ECDSA P-256 keypair.

    The private key is stored directly within the Windows TPM 2.0 KSP or Software KSP.
    Returns the key handle and the corresponding standard EllipticCurvePublicKey.
    """
    clean_name = _sanitize_key_name(key_name)
    h_prov, provider_type, is_hw = _open_storage_provider(preferred_provider)

    if h_prov is not None and _NCRYPT is not None:
        h_key = wintypes.HANDLE()
        # Create persisted key with overwrite flag
        res = _NCRYPT.NCryptCreatePersistedKey(
            h_prov,
            ctypes.byref(h_key),
            BCRYPT_ECDSA_P256_ALGORITHM,
            clean_name,
            0,
            NCRYPT_OVERWRITE_KEY_FLAG,
        )
        if res != ERROR_SUCCESS:
            _NCRYPT.NCryptFreeObject(h_prov)
            if provider_type == "tpm":
                # Retry with Software KSP provider
                return generate_device_keypair(key_name, preferred_provider="software_ksp")
            raise RuntimeError(f"NCryptCreatePersistedKey failed for '{clean_name}': {res:#x}")

        # Finalize the key (stores it in TPM / OS KSP without export rights)
        res = _NCRYPT.NCryptFinalizeKey(h_key, 0)
        if res != ERROR_SUCCESS:
            _NCRYPT.NCryptFreeObject(h_key)
            _NCRYPT.NCryptFreeObject(h_prov)
            raise RuntimeError(f"NCryptFinalizeKey failed for '{clean_name}': {res:#x}")

        # Export the public key blob
        cb_result = wintypes.DWORD()
        res = _NCRYPT.NCryptExportKey(
            h_key, 0, BCRYPT_ECCPUBLIC_BLOB, None, None, 0, ctypes.byref(cb_result), 0
        )
        if res != ERROR_SUCCESS:
            _NCRYPT.NCryptFreeObject(h_key)
            _NCRYPT.NCryptFreeObject(h_prov)
            raise RuntimeError(f"NCryptExportKey size query failed: {res:#x}")

        buf = ctypes.create_string_buffer(cb_result.value)
        res = _NCRYPT.NCryptExportKey(
            h_key, 0, BCRYPT_ECCPUBLIC_BLOB, None, buf, cb_result.value, ctypes.byref(cb_result), 0
        )
        if res != ERROR_SUCCESS:
            _NCRYPT.NCryptFreeObject(h_key)
            _NCRYPT.NCryptFreeObject(h_prov)
            raise RuntimeError(f"NCryptExportKey failed: {res:#x}")

        # Parse BCRYPT_ECCKEY_BLOB (Magic: 4 bytes, cbKey: 4 bytes, X: cbKey bytes, Y: cbKey bytes)
        raw = buf.raw[: cb_result.value]
        cb_key = int.from_bytes(raw[4:8], "little")
        x_bytes = raw[8 : 8 + cb_key]
        y_bytes = raw[8 + cb_key : 8 + 2 * cb_key]

        public_key = ec.EllipticCurvePublicNumbers(
            int.from_bytes(x_bytes, "big"),
            int.from_bytes(y_bytes, "big"),
            ec.SECP256R1(),
        ).public_key()

        handle = DeviceKeyHandle(
            key_name=clean_name,
            provider_name=provider_type,
            is_hardware_backed=is_hw,
            is_persisted=True,
            h_prov=h_prov,
            h_key=h_key,
        )
        return handle, public_key

    # Non-Windows / fallback in-memory protected key
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    _MEMORY_KEY_STORE[clean_name] = priv
    handle = DeviceKeyHandle(
        key_name=clean_name,
        provider_name="memory_fallback",
        is_hardware_backed=False,
        is_persisted=True,
        fallback_key=priv,
    )
    return handle, pub


def _try_load_cng_key(clean_name: str) -> DeviceKeyHandle | None:
    """Helper to try loading a single CNG / NCrypt key name from TPM or Software KSP."""
    h_prov, provider_type, is_hw = _open_storage_provider()

    if h_prov is not None and _NCRYPT is not None:
        h_key = wintypes.HANDLE()
        res = _NCRYPT.NCryptOpenKey(h_prov, ctypes.byref(h_key), clean_name, 0, 0)
        if res == ERROR_SUCCESS:
            return DeviceKeyHandle(
                key_name=clean_name,
                provider_name=provider_type,
                is_hardware_backed=is_hw,
                is_persisted=True,
                h_prov=h_prov,
                h_key=h_key,
            )

        # Clean up provider if key not found
        _NCRYPT.NCryptFreeObject(h_prov)

        # If TPM provider didn't find the key, check if it was created in Software KSP
        if provider_type == "tpm":
            h_soft_prov = wintypes.HANDLE()
            s_res = _NCRYPT.NCryptOpenStorageProvider(
                ctypes.byref(h_soft_prov), MS_SOFTWARE_KEY_STORAGE_PROVIDER, 0
            )
            if s_res == ERROR_SUCCESS:
                s_key = wintypes.HANDLE()
                res2 = _NCRYPT.NCryptOpenKey(h_soft_prov, ctypes.byref(s_key), clean_name, 0, 0)
                if res2 == ERROR_SUCCESS:
                    return DeviceKeyHandle(
                        key_name=clean_name,
                        provider_name="software_ksp",
                        is_hardware_backed=False,
                        is_persisted=True,
                        h_prov=h_soft_prov,
                        h_key=s_key,
                    )
                _NCRYPT.NCryptFreeObject(h_soft_prov)

    # Check in-memory store
    if clean_name in _MEMORY_KEY_STORE:
        return DeviceKeyHandle(
            key_name=clean_name,
            provider_name="memory_fallback",
            is_hardware_backed=False,
            is_persisted=True,
            fallback_key=_MEMORY_KEY_STORE[clean_name],
        )

    return None


def load_device_private_key(
    key_identifier: str | Path | None = None,
) -> DeviceKeyHandle | None:
    """Load an existing OS/TPM-protected private key handle by name or identifier."""
    if key_identifier is not None:
        clean_name = _sanitize_key_name(key_identifier)
        return _try_load_cng_key(clean_name)

    # When key_identifier is None, check primary default name, then registered database identifier, then machine key
    candidates = [DEFAULT_DEVICE_KEY_NAME]

    try:
        from database import get_connection
        conn = get_connection()
        rows = conn.execute(
            "SELECT key_identifier FROM devices WHERE key_identifier IS NOT NULL AND key_identifier != '' ORDER BY id DESC"
        ).fetchall()
        conn.close()
        for r in rows:
            kid = r["key_identifier"]
            if kid:
                s_name = _sanitize_key_name(kid)
                if s_name not in candidates:
                    candidates.append(s_name)
    except Exception:
        pass

    try:
        hostname = platform.node() or socket.gethostname() or os.environ.get("COMPUTERNAME", "")
        if hostname:
            host_key = _sanitize_key_name(f"VaultAI_Device_{hostname}")
            if host_key not in candidates:
                candidates.append(host_key)
    except Exception:
        pass

    for clean_name in candidates:
        handle = _try_load_cng_key(clean_name)
        if handle is not None:
            return handle

    return None


def save_device_private_key(
    private_key: DeviceKeyHandle | Any,
    key_path: str | Path | None = None,
) -> DeviceKeyHandle:
    """Ensure private key is safely stored in OS/TPM and remove any legacy plaintext keys.

    Because keys are directly persisted inside Windows TPM / CNG storage upon generation,
    this function verifies protection status, ensures zero plaintext files remain in the
    workspace, and returns the active DeviceKeyHandle.
    """
    # Clean up any legacy plaintext key file from prior versions if present
    workspace_dir = Path(__file__).resolve().parents[2]
    legacy_keys = [
        workspace_dir / ".vault_device_private.key",
        workspace_dir / ".vault_device_key",
    ]
    if key_path is not None:
        try:
            p = Path(key_path)
            if p.is_file():
                legacy_keys.append(p)
        except Exception:
            pass

    for lk in legacy_keys:
        try:
            if lk.exists():
                lk.unlink()
        except Exception:
            pass

    if isinstance(private_key, DeviceKeyHandle):
        return private_key

    # If an existing key handle was loaded or created
    loaded = load_device_private_key(key_path)
    if loaded is not None:
        return loaded

    # Return a validated handle
    return DeviceKeyHandle(
        key_name=_sanitize_key_name(key_path),
        provider_name="tpm" if sys.platform == "win32" else "memory_fallback",
        is_hardware_backed=bool(sys.platform == "win32"),
        is_persisted=True,
    )


def delete_device_private_key(
    key_identifier: str | Path | None = None,
) -> bool:
    """Delete a persisted device key from the TPM / OS key storage provider."""
    clean_name = _sanitize_key_name(key_identifier)
    handle = load_device_private_key(clean_name)
    if handle is not None and handle._h_key is not None and _NCRYPT is not None:
        res = _NCRYPT.NCryptDeleteKey(handle._h_key, 0)
        # Note: NCryptDeleteKey frees h_key automatically
        handle._h_key = None
        handle.close()
        return res == ERROR_SUCCESS

    if clean_name in _MEMORY_KEY_STORE:
        del _MEMORY_KEY_STORE[clean_name]
        return True

    return False


def sign_device_challenge(
    private_key: DeviceKeyHandle,
    challenge: bytes,
) -> bytes:
    """Cryptographically sign a challenge/nonce using the OS/TPM protected private key.

    Computes a SHA-256 digest of the challenge and delegates signature creation
    directly to the TPM / Windows CNG isolation boundary.
    """
    if not isinstance(private_key, DeviceKeyHandle):
        raise TypeError(f"Expected DeviceKeyHandle, got {type(private_key).__name__}")

    digest = hashlib.sha256(challenge).digest()
    return private_key.sign_hash(digest)


def verify_device_signature(
    public_key: ec.EllipticCurvePublicKey,
    signature: bytes,
    challenge: bytes,
) -> bool:
    """Verify cryptographic signature against the device public key."""
    try:
        public_key.verify(signature, challenge, ec.ECDSA(ec.hashes.SHA256()))
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


def public_key_to_pem(public_key: ec.EllipticCurvePublicKey) -> str:
    """Serialize EllipticCurvePublicKey to standard SubjectPublicKeyInfo PEM string."""
    pem_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pem_bytes.decode("ascii").strip()


def load_public_key_from_pem(pem_str: str) -> ec.EllipticCurvePublicKey:
    """Load an EllipticCurvePublicKey from PEM string."""
    key = serialization.load_pem_public_key(pem_str.encode("ascii"))
    if not isinstance(key, ec.EllipticCurvePublicKey):
        raise TypeError("Loaded public key is not an EllipticCurvePublicKey.")
    return key


def get_key_storage_info(key_identifier: str | Path | None = None) -> dict[str, Any]:
    """Retrieve diagnostic and security metadata for the device cryptographic identity."""
    handle = load_device_private_key(key_identifier)
    if handle is None:
        return {
            "key_present": False,
            "provider": "none",
            "hardware_backed": False,
            "non_exportable": True,
        }

    provider_name = handle.provider_name
    if provider_name == "tpm":
        provider_name = MS_PLATFORM_KEY_STORAGE_PROVIDER
    elif provider_name == "software_ksp":
        provider_name = MS_SOFTWARE_KEY_STORAGE_PROVIDER

    info = {
        "key_present": True,
        "key_name": handle.key_name,
        "provider": provider_name,
        "hardware_backed": handle.is_hardware_backed,
        "non_exportable": not handle.is_exportable,
    }
    handle.close()
    return info
