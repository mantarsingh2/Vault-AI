"""Device security, hardware fingerprinting, and cryptographic verification."""

from .hardware import (
    check_hardware_compatibility,
    check_network_environment,
    check_security_environment,
    get_hardware_fingerprint,
    get_hardware_identifiers,
    get_mac_address,
)
from .crypto import (
    DeviceKeyHandle,
    delete_device_private_key,
    generate_device_keypair,
    get_key_storage_info,
    load_device_private_key,
    load_public_key_from_pem,
    public_key_to_pem,
    save_device_private_key,
    sign_device_challenge,
    verify_device_signature,
)
from .manager import register_device, verify_device

__all__ = [
    "DeviceKeyHandle",
    "check_hardware_compatibility",
    "check_network_environment",
    "check_security_environment",
    "delete_device_private_key",
    "generate_device_keypair",
    "get_hardware_fingerprint",
    "get_hardware_identifiers",
    "get_key_storage_info",
    "get_mac_address",
    "load_device_private_key",
    "load_public_key_from_pem",
    "public_key_to_pem",
    "register_device",
    "save_device_private_key",
    "sign_device_challenge",
    "verify_device",
    "verify_device_signature",
]
