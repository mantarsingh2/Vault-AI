"""
Vault AI — Sigma Rules Behavioral Threat Detection Engine
=========================================================

Implements behavioral detection logic based on open-source Sigma specifications:
  • Suspicious Parent-Child Process Trees (Office/Browser spawning script engines)
  • Obfuscated & Encoded Script Execution (PowerShell -enc, hidden windows, WebClient)
  • Living-off-the-Land Binaries (LOLBins) abuse (certutil, bitsadmin, mshta, rundll32)
  • Reverse Shell & Command-and-Control (C2) Sockets
  • Defense Evasion & Security Disabling Attempts
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ThreatSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class ThreatAlert:
    """Represents a security alert triggered by a Sigma rule match."""
    rule_id: str
    rule_name: str
    severity: ThreatSeverity
    description: str
    matched_data: Dict[str, Any]
    mitre_attack: List[str]
    recommended_action: str


# ---------------------------------------------------------------------------
# Sigma Behavioral Rules Catalog
# ---------------------------------------------------------------------------

SIGMA_RULES = [
    {
        "id": "SIGMA-001",
        "name": "Suspicious Parent-Child Process Execution (Office/Explorer Spawning Shell)",
        "severity": ThreatSeverity.CRITICAL,
        "description": "A productivity software or shell spawned an interpreter commonly abused in spear-phishing and macro attacks.",
        "mitre": ["T1204.002", "T1059.001"],
        "action": "ISOLATE_WIRELESS",
        "parent_images": [
            "winword.exe", "excel.exe", "powerpnt.exe", "outlook.exe",
            "acrord32.exe", "acrobat.exe", "chrome.exe", "msedge.exe", "firefox.exe"
        ],
        "child_images": [
            "powershell.exe", "cmd.exe", "pwsh.exe", "mshta.exe",
            "cscript.exe", "wscript.exe", "certutil.exe", "bitsadmin.exe"
        ],
    },
    {
        "id": "SIGMA-002",
        "name": "Encoded or Obfuscated PowerShell Command Execution",
        "severity": ThreatSeverity.HIGH,
        "description": "PowerShell executed with encoded commands, hidden window styles, or memory download strings indicative of fileless malware.",
        "mitre": ["T1059.001", "T1027"],
        "action": "EVALUATE_AI",
        "target_images": ["powershell.exe", "pwsh.exe"],
        "command_patterns": [
            r"-(?:e|enc|encodedcommand)\s+[A-Za-z0-9+/=]{15,}",
            r"-(?:w|windowstyle)\s+hidden",
            r"downloadstring\s*\(",
            r"downloadfile\s*\(",
            r"invoke-expression|iex\b",
            r"invoke-webrequest|iwr\b",
            r"net\.webclient",
            r"bypass\s+-nop",
            r"tcplistener|tcpclient",
            r"system\.net\.sockets",
        ],
    },
    {
        "id": "SIGMA-003",
        "name": "LOLBins Binary Download or Remote Script Staging",
        "severity": ThreatSeverity.HIGH,
        "description": "Standard Windows utility used to download external payloads or bypass execution policies.",
        "mitre": ["T1105", "T1218"],
        "action": "EVALUATE_AI",
        "target_images": ["certutil.exe", "bitsadmin.exe", "mshta.exe", "rundll32.exe"],
        "command_patterns": [
            r"certutil.*-(?:urlcache|f\s+http|split)",
            r"bitsadmin.*(?:/transfer|/download)",
            r"mshta.*(?:https?://|javascript:)",
            r"rundll32.*(?:javascript:|vbscript:)",
        ],
    },
    {
        "id": "SIGMA-004",
        "name": "Command-and-Control (C2) / Reverse Shell Socket Detection",
        "severity": ThreatSeverity.CRITICAL,
        "description": "A system shell or script utility opened an outbound TCP connection to a known C2, reverse shell, or non-standard port.",
        "mitre": ["T1071.001", "T1571"],
        "action": "ISOLATE_WIRELESS",
        "suspicious_ports": [4444, 1337, 8888, 9001, 5555, 6666, 7777, 9999, 31337],
        "shell_images": ["powershell.exe", "cmd.exe", "rundll32.exe", "cscript.exe", "wscript.exe", "mshta.exe"],
    },
    {
        "id": "SIGMA-005",
        "name": "Security Service Tampering / Defender Evasion Attempt",
        "severity": ThreatSeverity.CRITICAL,
        "description": "Attempt to disable Windows Defender, Firewall, or security event logging.",
        "mitre": ["T1562.001"],
        "action": "ISOLATE_WIRELESS",
        "command_patterns": [
            r"set-mppreference.*-disablerealtimemonitoring\s+\$true",
            r"set-mppreference.*-disablebehavioriterelease\s+\$true",
            r"netsh\s+advfirewall\s+set.*off",
            r"wevtutil.*(?:cl|clear-log)\s+(?:security|system)",
            r"sc\s+stop\s+(?:windefend|mpsvc|bdesvc)",
        ],
    },
]


class SigmaEngine:
    """Evaluates system telemetry events against behavioral Sigma rules."""

    def __init__(self, custom_rules: Optional[List[Dict[str, Any]]] = None):
        self.rules = SIGMA_RULES + (custom_rules or [])

    def evaluate_process(
        self,
        image_name: str,
        cmdline: str,
        parent_name: Optional[str] = None,
        pid: Optional[int] = None,
    ) -> List[ThreatAlert]:
        """Match a running process and its command line against process Sigma rules."""
        alerts: List[ThreatAlert] = []
        image_lower = (image_name or "").lower().strip()
        parent_lower = (parent_name or "").lower().strip()
        cmd_lower = (cmdline or "").lower().strip()

        for r in self.rules:
            # Rule 1: Parent-Child anomaly
            if "parent_images" in r and "child_images" in r:
                if any(parent_lower.endswith(p) for p in r["parent_images"]):
                    if any(image_lower.endswith(c) for c in r["child_images"]):
                        alerts.append(ThreatAlert(
                            rule_id=r["id"],
                            rule_name=r["name"],
                            severity=r["severity"],
                            description=r["description"],
                            matched_data={
                                "process": image_name,
                                "pid": pid,
                                "parent": parent_name,
                                "command_line": cmdline,
                            },
                            mitre_attack=r["mitre"],
                            recommended_action=r["action"],
                        ))

            # Rule 2 & 3: Command pattern matching for specific binaries
            if "target_images" in r and "command_patterns" in r:
                if any(image_lower.endswith(t) for t in r["target_images"]):
                    for pat in r["command_patterns"]:
                        if re.search(pat, cmd_lower):
                            alerts.append(ThreatAlert(
                                rule_id=r["id"],
                                rule_name=r["name"],
                                severity=r["severity"],
                                description=r["description"],
                                matched_data={
                                    "process": image_name,
                                    "pid": pid,
                                    "matched_pattern": pat,
                                    "command_line": cmdline,
                                },
                                mitre_attack=r["mitre"],
                                recommended_action=r["action"],
                            ))
                            break

            # Rule 5: Generic security tampering command lines
            if "command_patterns" in r and "target_images" not in r and "parent_images" not in r:
                for pat in r["command_patterns"]:
                    if re.search(pat, cmd_lower):
                        alerts.append(ThreatAlert(
                            rule_id=r["id"],
                            rule_name=r["name"],
                            severity=r["severity"],
                            description=r["description"],
                            matched_data={
                                "process": image_name,
                                "pid": pid,
                                "matched_pattern": pat,
                                "command_line": cmdline,
                            },
                            mitre_attack=r["mitre"],
                            recommended_action=r["action"],
                        ))
                        break

        return alerts

    def evaluate_connection(
        self,
        image_name: str,
        pid: int,
        remote_ip: str,
        remote_port: int,
        status: str = "ESTABLISHED",
        local_port: Optional[int] = None,
    ) -> List[ThreatAlert]:
        """Match an outbound socket connection or suspicious listening socket against network Sigma rules."""
        alerts: List[ThreatAlert] = []
        image_lower = (image_name or "").lower().strip()

        for r in self.rules:
            # Rule 4: C2 / Reverse shell / Bind shell ports from script interpreters
            if "suspicious_ports" in r and "shell_images" in r:
                if any(image_lower.endswith(s) for s in r["shell_images"]):
                    # 1. Listening socket check (Bind Shell / Backdoor Listener)
                    if status == "LISTEN" and local_port:
                        if local_port in r["suspicious_ports"]:
                            alerts.append(ThreatAlert(
                                rule_id=r["id"],
                                rule_name=f"{r['name']} (Listening Backdoor)",
                                severity=r["severity"],
                                description=f"Script engine '{image_name}' opened an unauthorized listening socket on port {local_port}.",
                                matched_data={
                                    "process": image_name,
                                    "pid": pid,
                                    "local_port": local_port,
                                    "status": status,
                                },
                                mitre_attack=["T1059.001", "T1571"],
                                recommended_action=r["action"],
                            ))
                            continue

                    # 2. Outbound socket check (C2 / Reverse Shell)
                    if remote_ip and remote_ip not in ("127.0.0.1", "::1", "0.0.0.0", "localhost"):
                        if remote_port in r["suspicious_ports"] or remote_port > 1024:
                            alerts.append(ThreatAlert(
                                rule_id=r["id"],
                                rule_name=r["name"],
                                severity=r["severity"],
                                description=r["description"],
                                matched_data={
                                    "process": image_name,
                                    "pid": pid,
                                    "remote_ip": remote_ip,
                                    "remote_port": remote_port,
                                    "status": status,
                                },
                                mitre_attack=r["mitre"],
                                recommended_action=r["action"],
                            ))

        return alerts
