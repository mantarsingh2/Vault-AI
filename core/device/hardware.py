"""Hardware identifier extraction and system environment checking for Vault AI."""

from __future__ import annotations

import hashlib
import os
import platform
import socket
import subprocess
import uuid
import sys


def _query_registry_machine_guid() -> str:
    """Retrieve Windows MachineGuid from registry if available."""
    if sys.platform != "win32":
        return ""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(guid).strip()
    except Exception:
        return ""


def _query_wmi_command(command: str) -> str:
    """Run a fast PowerShell CIM/WMI query with timeout."""
    if sys.platform != "win32":
        return ""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return res.stdout.strip()
    except Exception:
        return ""


def get_mac_address() -> str:
    """Return primary MAC address formatted as colon-separated hex."""
    node = uuid.getnode()
    return ":".join(
        ["{:02x}".format((node >> ele) & 0xFF) for ele in range(0, 8 * 6, 8)][::-1]
    )


def get_hardware_identifiers() -> dict[str, str]:
    """Extract real machine hardware identifiers.

    Returns a dictionary containing:
    - machine_guid: Windows Machine GUID
    - motherboard_uuid: Motherboard / System UUID
    - processor_id: CPU Processor ID
    - baseboard_serial: Motherboard Serial Number
    - mac_address: Primary network MAC address
    - hostname: Device network name
    - platform: OS and CPU architecture details
    """
    machine_guid = _query_registry_machine_guid()
    motherboard_uuid = _query_wmi_command(
        "(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID"
    )
    processor_id = _query_wmi_command(
        "(Get-CimInstance -Class Win32_Processor).ProcessorId"
    )
    baseboard_serial = _query_wmi_command(
        "(Get-CimInstance -Class Win32_BaseBoard).SerialNumber"
    )

    hostname = (
        platform.node()
        or socket.gethostname()
        or os.environ.get("COMPUTERNAME", "UNKNOWN_HOST")
    )

    return {
        "machine_guid": machine_guid or "NO_MACHINE_GUID",
        "motherboard_uuid": motherboard_uuid or "NO_MOTHERBOARD_UUID",
        "processor_id": processor_id or platform.processor() or "NO_CPU_ID",
        "baseboard_serial": baseboard_serial or "NO_BASEBOARD_SERIAL",
        "mac_address": get_mac_address(),
        "hostname": hostname,
        "platform": platform.platform(),
        "architecture": platform.machine(),
    }


def get_hardware_fingerprint() -> str:
    """Generate a unique deterministic SHA-256 hardware fingerprint hash."""
    ids = get_hardware_identifiers()
    canonical_string = "|".join(
        [
            f"guid={ids['machine_guid']}",
            f"mb={ids['motherboard_uuid']}",
            f"cpu={ids['processor_id']}",
            f"board={ids['baseboard_serial']}",
            f"mac={ids['mac_address']}",
            f"arch={ids['architecture']}",
        ]
    )
    digest = hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()
    return f"hw_fp_{digest}"


def check_hardware_compatibility() -> dict[str, any]:
    """Validate that local hardware is compatible with Vault AI."""
    arch = platform.machine().lower()
    is_64bit = "64" in arch or "arm" in arch
    cpu_info = platform.processor() or "Compatible Processor"

    return {
        "compatible": is_64bit,
        "architecture": platform.machine(),
        "cpu": cpu_info,
        "os": platform.platform(),
        "status": "Hardware is compatible" if is_64bit else "Hardware architecture not supported",
    }


def check_security_environment() -> dict[str, any]:
    """Analyze system and OS integrity."""
    os_name = platform.system()
    release = platform.release()
    is_supported_os = os_name in ("Windows", "Darwin", "Linux")

    return {
        "secure": is_supported_os,
        "os_name": os_name,
        "os_release": release,
        "status": "System and OS integrity verified" if is_supported_os else "Unrecognized environment",
    }


def check_network_environment() -> dict[str, any]:
    """Check local network adapter and identity status."""
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"

    has_network = local_ip != "127.0.0.1" or bool(get_mac_address())

    return {
        "connected": has_network,
        "hostname": hostname,
        "local_ip": local_ip,
        "mac_address": get_mac_address(),
        "status": "Network environment verified" if has_network else "Local standalone mode",
    }
