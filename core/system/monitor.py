"""Live hardware, resource, and process monitoring for Vault AI using psutil."""

from __future__ import annotations

import platform
import socket
import time
from typing import Any

import psutil


def get_system_metrics() -> dict[str, Any]:
    """Collect real-time hardware resource and performance metrics."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    cpu_count_logical = psutil.cpu_count(logical=True) or 1
    cpu_count_physical = psutil.cpu_count(logical=False) or 1
    
    # Memory metrics
    mem = psutil.virtual_memory()
    total_ram_gb = round(mem.total / (1024 ** 3), 2)
    used_ram_gb = round(mem.used / (1024 ** 3), 2)
    free_ram_gb = round(mem.available / (1024 ** 3), 2)
    ram_percent = mem.percent

    # Disk / Storage metrics
    disk = psutil.disk_usage("/")
    total_disk_gb = round(disk.total / (1024 ** 3), 1)
    used_disk_gb = round(disk.used / (1024 ** 3), 1)
    free_disk_gb = round(disk.free / (1024 ** 3), 1)
    disk_percent = disk.percent

    # Battery metrics where available
    battery = psutil.sensors_battery()
    battery_percent = battery.percent if battery else None
    power_plugged = battery.power_plugged if battery else None

    # Top active processes by memory
    top_processes = []
    try:
        for p in sorted(
            psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]),
            key=lambda x: x.info.get("memory_percent") or 0,
            reverse=True,
        )[:5]:
            top_processes.append({
                "pid": p.info["pid"],
                "name": p.info["name"],
                "mem_percent": round(p.info.get("memory_percent") or 0, 1),
                "cpu_percent": round(p.info.get("cpu_percent") or 0, 1),
            })
    except Exception:
        pass

    hostname = platform.node() or socket.gethostname() or "UnknownHost"

    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hostname": hostname,
        "os": platform.platform(),
        "cpu": {
            "percent": cpu_percent,
            "logical_cores": cpu_count_logical,
            "physical_cores": cpu_count_physical,
            "status": "Normal" if cpu_percent < 80 else "High Load",
        },
        "ram": {
            "percent": ram_percent,
            "total_gb": total_ram_gb,
            "used_gb": used_ram_gb,
            "free_gb": free_ram_gb,
            "status": "Optimal" if ram_percent < 85 else "Constrained",
        },
        "disk": {
            "percent": disk_percent,
            "total_gb": total_disk_gb,
            "used_gb": used_disk_gb,
            "free_gb": free_disk_gb,
        },
        "battery": {
            "percent": battery_percent,
            "plugged": power_plugged,
        },
        "top_processes": top_processes,
    }


def format_system_summary() -> str:
    """Return a human-readable structured Markdown report of current system metrics."""
    metrics = get_system_metrics()
    cpu = metrics["cpu"]
    ram = metrics["ram"]
    disk = metrics["disk"]

    lines = [
        f"### 🖥️ **System Health & Hardware Status**",
        f"**Device:** `{metrics['hostname']}` | **OS:** `{metrics['os']}`",
        f"",
        f"| Component | Usage | Details | Status |",
        f"| :--- | :--- | :--- | :--- |",
        f"| **CPU** | `{cpu['percent']}%` | {cpu['logical_cores']} Cores ({cpu['physical_cores']} Physical) | ✅ {cpu['status']} |",
        f"| **RAM** | `{ram['percent']}%` | {ram['used_gb']} GB used / {ram['total_gb']} GB total ({ram['free_gb']} GB free) | ✅ {ram['status']} |",
        f"| **Storage** | `{disk['percent']}%` | {disk['used_gb']} GB used / {disk['total_gb']} GB total ({disk['free_gb']} GB free) | ✅ Healthy |",
    ]

    if metrics["battery"]["percent"] is not None:
        bat = metrics["battery"]
        charging_icon = "⚡ Plugged In" if bat["plugged"] else "🔋 On Battery"
        lines.append(f"| **Battery** | `{bat['percent']}%` | {charging_icon} | Active |")

    if metrics["top_processes"]:
        lines.extend([
            f"",
            f"**Top Processes by Memory:**",
        ])
        for p in metrics["top_processes"]:
            lines.append(f"- `{p['name']}` (PID {p['pid']}): {p['mem_percent']}% RAM, {p['cpu_percent']}% CPU")

    return "\n".join(lines)
