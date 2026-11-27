"""
Vault AI — System Telemetry Sentinel & Threat Sensor
====================================================

Continuously or on-demand gathers live operating system telemetry:
  • Scans active processes, parent-child hierarchies, and command lines
  • Scans active TCP/UDP network connections and listening sockets
  • Evaluates all events through the Sigma Rules Behavioral Engine
  • Generates high-fidelity Incident Snapshots for the Qwen3 SOC Analyst
"""

from __future__ import annotations

import datetime
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import psutil

from core.security.sigma_engine import SigmaEngine, ThreatAlert, ThreatSeverity

IS_WINDOWS = sys.platform == "win32"


class TelemetrySentinel:
    """Live system telemetry collector and anomaly sensor."""

    def __init__(self, sigma_engine: Optional[SigmaEngine] = None):
        self.sigma = sigma_engine or SigmaEngine()

    def scan_processes(self) -> Tuple[List[Dict[str, Any]], List[ThreatAlert]]:
        """Scan all running processes, retrieve parent/child context, and match Sigma rules."""
        scanned: List[Dict[str, Any]] = []
        alerts: List[ThreatAlert] = []

        # Cache pid -> name to resolve parents fast without duplicate syscalls
        proc_map: Dict[int, str] = {}
        cached_procs = []

        for p in psutil.process_iter(["pid", "name", "ppid"]):
            try:
                proc_map[p.info["pid"]] = p.info.get("name") or "Unknown"
                cached_procs.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        for p in cached_procs:
            try:
                pid = p.info["pid"]
                name = p.info.get("name") or ""
                ppid = p.info.get("ppid") or 0
                parent_name = proc_map.get(ppid, "")

                # Retrieve cmdline (might raise AccessDenied on system procs)
                try:
                    cmdline_list = p.cmdline()
                    cmdline = " ".join(cmdline_list) if cmdline_list else name
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    cmdline = name

                # Run process behavioral checks via Sigma Engine
                proc_alerts = self.sigma.evaluate_process(
                    image_name=name,
                    cmdline=cmdline,
                    parent_name=parent_name,
                    pid=pid,
                )
                if proc_alerts:
                    alerts.extend(proc_alerts)
                    scanned.append({
                        "pid": pid,
                        "name": name,
                        "parent": parent_name,
                        "cmdline": cmdline,
                        "alerts": [a.rule_name for a in proc_alerts],
                    })

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return scanned, alerts

    def scan_network_connections(self) -> Tuple[List[Dict[str, Any]], List[ThreatAlert]]:
        """Scan active socket connections and correlate with process images."""
        scanned: List[Dict[str, Any]] = []
        alerts: List[ThreatAlert] = []

        try:
            connections = psutil.net_connections(kind="inet")
        except (psutil.AccessDenied, Exception):
            return scanned, alerts

        # Cache process names
        pname_cache: Dict[int, str] = {}

        for conn in connections:
            try:
                pid = conn.pid
                if not pid:
                    continue

                if pid not in pname_cache:
                    try:
                        pname_cache[pid] = psutil.Process(pid).name()
                    except Exception:
                        pname_cache[pid] = "Unknown"

                proc_name = pname_cache[pid]
                status = conn.status

                local_port = conn.laddr.port if conn.laddr else None
                remote_ip = conn.raddr.ip if conn.raddr else ""
                remote_port = conn.raddr.port if conn.raddr else 0

                # Must have at least a local listening port or an outbound remote address
                if not local_port and not remote_ip:
                    continue

                net_alerts = self.sigma.evaluate_connection(
                    image_name=proc_name,
                    pid=pid,
                    remote_ip=remote_ip,
                    remote_port=remote_port,
                    status=status,
                    local_port=local_port,
                )

                if net_alerts:
                    alerts.extend(net_alerts)
                    scanned.append({
                        "pid": pid,
                        "process": proc_name,
                        "remote_ip": remote_ip or "0.0.0.0",
                        "remote_port": remote_port or local_port,
                        "status": status,
                        "alerts": [a.rule_name for a in net_alerts],
                    })

            except Exception:
                continue

        return scanned, alerts

    def hunt_threats(self) -> Dict[str, Any]:
        """Perform a complete forensic threat hunt across processes and network telemetry.

        Returns an incident snapshot ready for AI triage and containment decisions.
        """
        suspicious_procs, proc_alerts = self.scan_processes()
        suspicious_conns, conn_alerts = self.scan_network_connections()

        all_alerts = proc_alerts + conn_alerts

        critical_count = sum(1 for a in all_alerts if a.severity == ThreatSeverity.CRITICAL)
        high_count = sum(1 for a in all_alerts if a.severity == ThreatSeverity.HIGH)
        medium_count = sum(1 for a in all_alerts if a.severity == ThreatSeverity.MEDIUM)

        has_active_threat = critical_count > 0 or high_count > 0

        # Basic device context
        cpu_pct = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()

        return {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "has_active_threat": has_active_threat,
            "total_alerts": len(all_alerts),
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "alerts": all_alerts,
            "suspicious_processes": suspicious_procs,
            "suspicious_connections": suspicious_conns,
            "system_metrics": {
                "cpu_percent": cpu_pct,
                "ram_percent": mem.percent,
            },
        }


# Module singleton
_sentinel = TelemetrySentinel()


def hunt_system_threats() -> Dict[str, Any]:
    """Public helper to execute an immediate threat hunt."""
    return _sentinel.hunt_threats()
