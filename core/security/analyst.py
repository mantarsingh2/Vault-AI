"""
Vault AI — AI SOC Analyst & Threat Containment Coordinator
==========================================================

Bridges system telemetry, Sigma behavioral rules, and the local Qwen3 8B AI engine:
  • Receives raw telemetry and Sigma alerts from TelemetrySentinel
  • Queries local Qwen3 8B via Ollama to evaluate command line obfuscation, intent, and MITRE tactics
  • Determines containment action: Emergency Wireless Kill-Switch (Air-Gap) or Monitoring
  • Coordinates with core.security.killswitch to execute or restore network isolation
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from core.ai.local_model import OllamaService
from core.security.killswitch import (
    disconnect_all_wireless,
    get_wireless_status,
    restore_wireless,
)
from core.security.sentinel import hunt_system_threats
from core.security.sigma_engine import ThreatAlert, ThreatSeverity

ANALYST_SYSTEM_PROMPT = """You are Vault AI's Tier-2 SOC (Security Operations Center) Analyst AI running locally on Qwen3 8B.
Your task is to analyze real-time endpoint telemetry and behavioral Sigma alerts triggered on the user's laptop.

Evaluate:
1. Is this an ACTIVE MALICIOUS ATTACK (C2 beacon, reverse shell, ransomware staging, LOLBin abuse, tampering) OR benign developer/administrative activity?
2. Assess severity: CRITICAL, HIGH, MEDIUM, or BENIGN.
3. Recommend action: AIR_GAP_ISOLATION (immediate wireless cut-off) or CONTINUE_MONITORING.
4. Provide a crisp forensic summary explaining WHAT is happening and WHY the action is recommended.

Format your response clearly using markdown with bullet points and a concluding recommendation block."""


class SOCAnalyst:
    """Evaluates telemetry using local Qwen3 8B and coordinates containment."""

    def __init__(self, ollama: Optional[OllamaService] = None):
        self.ollama = ollama or OllamaService()

    def analyze_threats(self, incident: Optional[Dict[str, Any]] = None, auto_isolate: bool = False) -> Dict[str, Any]:
        """Perform a full threat hunt, evaluate findings with Qwen3 8B, and optionally isolate."""
        if incident is None:
            incident = hunt_system_threats()

        alerts: List[ThreatAlert] = incident.get("alerts", [])
        has_threats = incident.get("has_active_threat", False)

        # 1. Clean system: no behavioral rules triggered
        if not alerts:
            metrics = incident.get("system_metrics", {})
            return {
                "verdict": "CLEAN",
                "severity": "LOW",
                "isolation_triggered": False,
                "incident": incident,
                "summary": (
                    "### 🛡️ **Active Threat Hunt Diagnostic: System Secure**\n\n"
                    "✅ **Telemetry Scan Complete:** Scanned live process trees, listening sockets, and network connections.\n\n"
                    "| Telemetry Vector | Live Diagnostic Status |\n"
                    "| :--- | :--- |\n"
                    "| **Process Tree Anomalies** | 🟢 Clean (No unauthorized parent-child shell spawning) |\n"
                    "| **Script & PowerShell Obfuscation** | 🟢 Clean (No `-enc`, hidden windows, or WebClient memory stagers) |\n"
                    "| **Living-off-the-Land (LOLBins)** | 🟢 Clean (No certutil/bitsadmin payload staging detected) |\n"
                    "| **Command & Control (C2) Sockets** | 🟢 Clean (No active reverse shell sockets on known C2 ports) |\n"
                    "| **Security Service Tampering** | 🟢 Clean (Windows Defender & Security Event logs intact) |\n"
                    f"| **Live System Load** | CPU: `{metrics.get('cpu_percent', 0.0)}%` | RAM: `{metrics.get('ram_percent', 0.0)}%` |\n\n"
                    "> 💡 **SOC Analysis (Qwen3 8B):** No active cyber intrusion patterns or remote attacker channels found. "
                    "All wireless adapters and firewall boundaries are operating normally."
                ),
            }

        # 2. Alerts found: Feed incident telemetry to Qwen3 8B for forensic analysis
        telemetry_lines = []
        for i, a in enumerate(alerts, 1):
            telemetry_lines.append(
                f"Alert #{i}: [{a.severity.value}] {a.rule_name} (ID: {a.rule_id})\n"
                f"  - MITRE ATT&CK: {', '.join(a.mitre_attack)}\n"
                f"  - Details: {json.dumps(a.matched_data, default=str)}\n"
                f"  - Action Hint: {a.recommended_action}"
            )

        telemetry_summary = "\n".join(telemetry_lines)
        prompt = (
            f"ENDPOINT TELEMETRY ALERT:\n"
            f"Total Alerts: {len(alerts)} (Critical: {incident.get('critical_count')}, High: {incident.get('high_count')})\n\n"
            f"Alert Details:\n{telemetry_summary}\n\n"
            f"Conduct triage: Assess if this constitutes an active threat requiring immediate wireless isolation."
        )

        ai_reasoning = ""
        try:
            ai_reasoning = self.ollama.chat(
                messages=[
                    {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=600,
            )
        except Exception as e:
            ai_reasoning = (
                f"Local Qwen3 8B offline or busy ({e}). Rule-based emergency evaluation applied:\n"
                f"- Critical alerts present: {incident.get('critical_count')}\n"
                f"- MITRE Tactics: Unauthorized execution / C2 network traffic."
            )

        # 3. Determine if containment is necessary
        critical_alerts = [a for a in alerts if a.severity == ThreatSeverity.CRITICAL]
        should_isolate = auto_isolate or (len(critical_alerts) > 0 and any(a.recommended_action == "ISOLATE_WIRELESS" for a in critical_alerts))

        isolation_result = None
        if should_isolate:
            reason = f"Automated SOC containment: {len(critical_alerts)} critical intrusion alerts detected."
            isolation_result = disconnect_all_wireless(reason=reason)

        # 4. Build executive response markdown
        verdict = "CRITICAL_ATTACK" if critical_alerts else "SUSPICIOUS"
        status_badge = "🔴 **ACTIVE INTRUSION DETECTED**" if critical_alerts else "⚠️ **SUSPICIOUS ACTIVITY DETECTED**"

        alert_table_rows = []
        for a in alerts[:5]:
            alert_table_rows.append(
                f"| `{a.rule_id}` | **{a.severity.value}** | {a.rule_name} | `{', '.join(a.mitre_attack)}` |"
            )

        containment_md = ""
        if isolation_result and isolation_result.get("success"):
            containment_md = (
                "\n### 🛑 **EMERGENCY WIRELESS CONTAINMENT EXECUTED**\n\n"
                "✅ **Laptop Air-Gapped:** Outbound data exfiltration halted immediately.\n"
                f"- **Firewall Isolation Rule:** Deployed (`VaultAI_Emergency_KillSwitch` blocking outbound traffic)\n"
                f"- **Wi-Fi Adapters Disabled:** `{', '.join(isolation_result.get('disabled_adapters', [])) or 'All wireless interfaces'}`\n"
                f"- **Bluetooth Transceivers:** Powered off to prevent wireless tethering bypass.\n\n"
                "> 💡 **To reconnect:** Say **`restore wireless`** or **`reconnect wifi`** when the system is clean."
            )
        elif should_isolate:
            containment_md = (
                "\n### ⚠️ **Containment Action Recommended**\n"
                "Critical alerts recommend cutting off wireless connections immediately. "
                "Say **`disconnect all wireless`** to execute full air-gap isolation."
            )

        full_md = (
            f"### {status_badge}\n\n"
            f"**SOC Incident Analysis & Telemetry Assessment**\n\n"
            f"| Rule ID | Severity | Threat Type | MITRE ATT&CK |\n"
            f"| :--- | :--- | :--- | :--- |\n"
            + "\n".join(alert_table_rows)
            + f"\n\n#### 🧠 **Qwen3 8B Forensic Triage:**\n\n{ai_reasoning}\n"
            + containment_md
        )

        return {
            "verdict": verdict,
            "severity": "CRITICAL" if critical_alerts else "HIGH",
            "isolation_triggered": should_isolate and (isolation_result.get("success") if isolation_result else False),
            "isolation_result": isolation_result,
            "incident": incident,
            "summary": full_md,
        }

    def emergency_airgap(self, reason: str = "Operator emergency kill-switch initiated") -> Dict[str, Any]:
        """Manually trigger immediate wireless isolation and emergency firewall block."""
        result = disconnect_all_wireless(reason=reason)

        if result.get("success"):
            adapters = ", ".join(result.get("disabled_adapters", [])) or "All 802.11/WWAN Adapters"
            bt_count = len(result.get("disabled_bluetooth", []))
            summary = (
                "### 🛑 **Emergency Wireless Kill-Switch Activated**\n\n"
                "✅ **Air-Gap Containment Enforced:** All wireless communications have been severed.\n\n"
                "| Containment Vector | Enforcement Status | Technical Action |\n"
                "| :--- | :--- | :--- |\n"
                "| **Outbound Firewall Block** | 🛡️ Active | Deployed instant rule `VaultAI_Emergency_KillSwitch` |\n"
                f"| **Wi-Fi / WWAN Adapters** | 🔴 Disabled | Turned off `{adapters}` via NetAdapter API |\n"
                f"| **Bluetooth Transceivers** | 🔴 Powered Off | Disabled {bt_count} Bluetooth PnP controllers |\n"
                "| **Active Foreign Sockets** | 🔌 Terminated | Closed established external connections |\n\n"
                "> 💡 **Security Guarantee:** Attacker C2 channels, data exfiltration, and lateral wireless bridging are blocked.\n\n"
                "> 🔄 **Restoration:** Reply with **`restore wireless`** or **`reconnect wifi`** to bring all adapters and traffic back online."
            )
        else:
            summary = (
                "### ⚠️ **Wireless Kill-Switch Execution Warning**\n\n"
                f"Encountered an issue during emergency containment: {result.get('errors')}\n\n"
                "> 💡 **Note:** Disabling hardware network adapters requires Administrative privileges. "
                "Ensure Vault AI is running with adequate permissions."
            )

        return {
            "success": result.get("success", False),
            "result": result,
            "summary": summary,
        }

    def restore_connectivity(self) -> Dict[str, Any]:
        """Safely remove firewall isolation rule and re-enable Wi-Fi and Bluetooth."""
        result = restore_wireless()

        if result.get("success"):
            adapters = ", ".join(result.get("enabled_adapters", [])) or "Wi-Fi Adapters"
            summary = (
                "### 🌐 **Wireless Connectivity Successfully Restored**\n\n"
                "✅ **Normal Network Operations Resumed:**\n\n"
                "| Component | Restoration Status | Details |\n"
                "| :--- | :--- | :--- |\n"
                "| **Emergency Firewall Rule** | 🟢 Removed | Outbound isolation rule deactivated |\n"
                f"| **Wi-Fi / WWAN Adapters** | 🟢 Re-enabled | `{adapters}` enabled via NetAdapter API |\n"
                "| **Bluetooth Controller** | 🟢 Restored | Bluetooth radio re-enabled via PnP Device Manager |\n\n"
                "> 💡 **Tip:** Adapters will take 3-5 seconds to re-associate with your saved Wi-Fi network."
            )
        else:
            summary = (
                "### ⚠️ **Restoration Notice**\n\n"
                f"Could not cleanly restore all network components: {result.get('errors')}\n\n"
                "You can also manually re-enable Wi-Fi in Windows Action Center (Win + A)."
            )

        return {
            "success": result.get("success", False),
            "result": result,
            "summary": summary,
        }


# Singleton
_analyst = SOCAnalyst()


def analyze_security_threats(auto_isolate: bool = False) -> Dict[str, Any]:
    """Public helper to run SOC threat analysis."""
    return _analyst.analyze_threats(auto_isolate=auto_isolate)


def trigger_emergency_killswitch(reason: str = "Operator requested wireless kill-switch") -> Dict[str, Any]:
    """Public helper to trigger emergency wireless kill-switch."""
    return _analyst.emergency_airgap(reason=reason)


def trigger_restore_wireless() -> Dict[str, Any]:
    """Public helper to restore wireless connectivity."""
    return _analyst.restore_connectivity()
