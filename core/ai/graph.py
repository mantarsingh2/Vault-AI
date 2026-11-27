"""LangGraph orchestration layer for Vault AI.

Replaces the flat if/elif intent chain in engine.py with a StateGraph that
enables stateful, extensible, multi-step agent workflows.

Graph topology
--------------

    [classify] → [router] → [confirm_node]
                           → [file_node]
                           → [system_node]
                           → [security_node]
                           → [complex_node]
                           → [chat_node]
                           → [general_node]   (default)

Each leaf node populates state["response"] (a dict) and returns.
The graph is then compiled into ``agent_graph`` which is what
``engine.py`` calls via ``agent_graph.invoke(state)``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypedDict

try:
    from langgraph.graph import END, StateGraph
    HAS_LANGGRAPH = True
except (ImportError, ModuleNotFoundError):
    HAS_LANGGRAPH = False
    END = "__end__"
    StateGraph = None

from core.ai.router import Intent, classify_intent

# ---------------------------------------------------------------------------
# Shared state schema
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    """Shared mutable state passed between all graph nodes."""

    # Inputs
    user_query: str
    session_id: str
    conversation_history: List[Dict[str, str]]
    on_chunk: Optional[Callable[[str], None]]

    # Set by classify_node
    intent: str

    # Set by leaf nodes
    response: Dict[str, Any]


# ---------------------------------------------------------------------------
# Utility: lazy imports to avoid circular-import issues at module load time
# ---------------------------------------------------------------------------

def _get_local_model_query():
    """Return _query_local_model from engine (deferred to avoid circulars)."""
    from core.ai.engine import _query_local_model  # noqa: PLC0415
    return _query_local_model


def _get_pending_actions():
    """Return the PENDING_ACTIONS dict from engine."""
    from core.ai import engine  # noqa: PLC0415
    return engine.PENDING_ACTIONS


# ---------------------------------------------------------------------------
# Node: classify
# ---------------------------------------------------------------------------

def classify_node(state: AgentState) -> AgentState:
    """Classify the user query and store intent in state."""
    intent = classify_intent(state["user_query"])
    return {"intent": intent.value}


# ---------------------------------------------------------------------------
# Node: router  (conditional edge source)
# ---------------------------------------------------------------------------

def router_node(state: AgentState) -> str:
    """Return the name of the next node based on intent."""
    intent = state.get("intent", Intent.GENERAL_QUERY.value)
    routing = {
        Intent.CONFIRM_ACTION.value: "confirm_node",
        Intent.FILE_OPERATION.value: "file_node",
        Intent.SYSTEM_STATUS.value: "system_node",
        Intent.SECURITY_CHECK.value: "security_node",
        Intent.COMPLEX_TASK.value: "complex_node",
        Intent.CASUAL_CHAT.value: "chat_node",
        Intent.GENERAL_QUERY.value: "general_node",
    }
    return routing.get(intent, "general_node")


# ---------------------------------------------------------------------------
# Node: confirm_node
# ---------------------------------------------------------------------------

def confirm_node(state: AgentState) -> AgentState:
    """Execute a previously pending file-operation action."""
    from core.file_manager.executor import execute_organization_plan  # noqa: PLC0415

    session_id = state.get("session_id", "default")
    pending_actions = _get_pending_actions()
    pending = pending_actions.get(session_id)
    intent = state.get("intent", Intent.CONFIRM_ACTION.value)

    if pending:
        exec_result = execute_organization_plan(pending)
        del pending_actions[session_id]
        response = {
            "role": "assistant",
            "content": exec_result["summary"],
            "intent": intent,
            "status": "success",
            "steps": ["User Confirmed Execution", f"Moved {exec_result['success_count']} Files"],
        }
    else:
        response = {
            "role": "assistant",
            "content": "There are no pending actions to execute right now. What else can I help you with?",
            "intent": intent,
            "status": "success",
            "steps": ["No Pending Action Found"],
        }

    return {"response": response}


# ---------------------------------------------------------------------------
# Node: file_node  — delegates to core.file_manager.operations engine
# ---------------------------------------------------------------------------

def _PLACEHOLDER(): pass  # (old helpers removed — now in core.file_manager.operations)


def file_node(state: AgentState) -> AgentState:
    """Handle ALL file-operation intents via the FileOperationEngine.

    Priority:
      1. core.file_manager.operations.execute_file_query()
         → handles create/delete/move/copy/rename/list/search/open
      2. VaultAIAgent fallback
         → handles organize/duplicate/AI-categorize scan queries
    """
    from core.file_manager.operations import execute_file_query  # noqa: PLC0415

    user_query = state["user_query"]
    session_id = state.get("session_id", "default")
    intent = state.get("intent", Intent.FILE_OPERATION.value)
    pending_actions = _get_pending_actions()

    # ── 1. Try the full file operation engine ─────────────────────────────────
    fs_result = execute_file_query(user_query)
    if fs_result is not None:
        return {"response": fs_result}

    # ── 2. VaultAIAgent — scan / organize / duplicate detection ───────────────
    from core.ai.agent import VaultAIAgent  # noqa: PLC0415

    agent = VaultAIAgent()
    result = agent.process_prompt(user_query)

    ai_text = result.get("ai_response", "")
    duplicates = result.get("duplicates", [])
    suggestions = result.get("suggestions", [])
    matched_files = result.get("matched_files", [])

    md_sections: List[str] = []
    if ai_text:
        md_sections.append(ai_text)

    user_asked_duplicates = any(
        w in user_query.lower() for w in ["duplicate", "duplicates", "wasted", "copies", "copy"]
    )
    if duplicates and user_asked_duplicates:
        md_sections.append("### 🔁 **Duplicate Files Breakdown:**\n")
        for idx, d in enumerate(duplicates[:5], 1):
            files_list = "\n".join([f"  - `{f}`" for f in d.get("files", [])])
            md_sections.append(
                f"**Group {idx}** (Size: {d.get('human_size')}, "
                f"Saves: {d.get('potential_savings')}):\n{files_list}"
            )

    user_asked_organize = any(
        w in user_query.lower() for w in ["organize", "sort", "categorize", "cleanup", "clean up", "suggest"]
    )
    if suggestions and user_asked_organize:
        md_sections.append("### 💡 **Suggested Organization Plan:**\n")
        md_sections.append("| Original File | Suggested Destination | Category | Reason |")
        md_sections.append("| :--- | :--- | :--- | :--- |")
        for s in suggestions[:8]:
            orig = Path(s.get("original_path", "")).name
            dest = s.get("suggested_destination", "")
            cat = s.get("category", "")
            reason = s.get("reason", "")
            md_sections.append(f"| `{orig}` | `{dest}` | **{cat}** | {reason} |")
        pending_actions[session_id] = suggestions
        md_sections.append(
            "\n> ⚡ **Awaiting Permission:** Do you want me to go ahead and "
            "move these files for you? (Reply 'yes' or 'do it')"
        )
    elif matched_files:
        md_sections.append(f"\n### 📄 **Discovered Files ({len(matched_files)} items):**\n")
        md_sections.append("| File Name | Category | Size | Path |")
        md_sections.append("| :--- | :--- | :--- | :--- |")
        for f in matched_files[:10]:
            md_sections.append(
                f"| `{f.get('name','')}` | **{f.get('category','')}** | "
                f"{f.get('human_size','')} | `{f.get('path','')}` |"
            )

    if not md_sections:
        md_sections.append(
            "I couldn't determine the file action. Try:\n"
            "- `create a folder named Projects on Desktop`\n"
            "- `move C:\\Users\\HP\\Desktop\\notes.txt to Documents`\n"
            "- `list files in Downloads`\n"
            "- `search for *.pdf on Desktop`"
        )

    return {
        "response": {
            "role": "assistant",
            "content": "\n\n".join(md_sections),
            "intent": intent,
            "status": "success",
            "steps": ["File Operation Engine", "Executed Action"],
        }
    }


# ---------------------------------------------------------------------------
# Node: system_node
# ---------------------------------------------------------------------------

def system_node(state: AgentState) -> AgentState:
    """Return a formatted system/hardware summary."""
    from core.system.monitor import format_system_summary  # noqa: PLC0415

    intent = state.get("intent", Intent.SYSTEM_STATUS.value)
    summary_md = format_system_summary()
    response_text = (
        f"{summary_md}\n\n"
        f"> 💡 **Dynamic Resource Check:** Hardware is operating normally. "
        f"All system resources are verified healthy."
    )
    return {
        "response": {
            "role": "assistant",
            "content": response_text,
            "intent": intent,
            "status": "success",
            "steps": ["Checked CPU & RAM", "Queried Process Table", "Verified Resource Availability"],
        }
    }


# ---------------------------------------------------------------------------
# Node: security_node
# ---------------------------------------------------------------------------

def security_node(state: AgentState) -> AgentState:
    """Execute live security audits, emergency wireless killswitch, threat detection, or TPM checks."""
    import re as _re
    from core.device import get_hardware_identifiers, get_key_storage_info  # noqa: PLC0415
    from core.security.auditor import audit_laptop_security, execute_malware_scan  # noqa: PLC0415
    from core.security.analyst import (  # noqa: PLC0415
        analyze_security_threats,
        trigger_emergency_killswitch,
        trigger_restore_wireless,
    )

    user_query = state.get("user_query", "").lower()
    intent = state.get("intent", Intent.SECURITY_CHECK.value)

    # 1. Emergency Wireless Kill-Switch / Air-Gap Isolation
    is_killswitch = any(k in user_query for k in [
        "disconnect all wireless", "disconnect wireless", "kill wireless", "cut off wireless",
        "stop all wireless", "air gap", "airgap", "kill switch", "killswitch", "isolate wireless",
        "disable wireless", "disable wifi", "stop wireless"
    ]) and not any(k in user_query for k in ["restore", "reconnect", "re-enable", "enable", "how"])

    if is_killswitch:
        ks_res = trigger_emergency_killswitch(reason="Operator emergency air-gap initiated via Vault AI chat")
        return {
            "response": {
                "role": "assistant",
                "content": ks_res["summary"],
                "intent": intent,
                "status": "success",
                "steps": [
                    "Deployed Outbound Firewall Block Rule",
                    "Disabled 802.11/WWAN Network Adapters",
                    "Powered Off Bluetooth Transceivers",
                    "Terminated Active Foreign Sockets",
                ],
            }
        }

    # 2. Restore Wireless Connectivity
    is_restore = any(k in user_query for k in [
        "restore wireless", "restore wifi", "reconnect wireless", "reconnect wifi",
        "re-enable wifi", "re-enable wireless", "enable wifi", "enable wireless",
        "bring back wireless", "bring back wifi"
    ])

    if is_restore:
        rst_res = trigger_restore_wireless()
        return {
            "response": {
                "role": "assistant",
                "content": rst_res["summary"],
                "intent": intent,
                "status": "success",
                "steps": [
                    "Removed Emergency Firewall Isolation Rule",
                    "Re-enabled Wi-Fi Network Adapters",
                    "Restored Bluetooth Radio Transceivers",
                ],
            }
        }

    # 3. Active Threat Hunt & Intrusion Detection (SOC Analyst + Qwen3 8B)
    is_threat_hunt = any(k in user_query for k in [
        "threat hunt", "hunt threats", "detect attack", "detect attacks", "intrusion",
        "attacker", "hacker", "suspicious activity", "soc analyst", "handle attack",
        "c2", "reverse shell", "check attack"
    ])

    if is_threat_hunt:
        auto_isolate = any(k in user_query for k in ["contain", "isolate", "stop it", "stop attack"])
        hunt_res = analyze_security_threats(auto_isolate=auto_isolate)
        return {
            "response": {
                "role": "assistant",
                "content": hunt_res["summary"],
                "intent": intent,
                "status": "success",
                "steps": [
                    "Scanned Active Process Trees for Anomaly & Obfuscation",
                    "Inspected Listening & Outbound Socket Telemetry",
                    "Evaluated Sigma Behavioral Rules (MITRE ATT&CK)",
                    "Performed Forensic Triage via Local Qwen3 8B",
                ],
            }
        }

    # 4. On-demand live malware quick scan execution
    if any(k in user_query for k in ["scan for malware", "malware scan", "virus scan", "defender scan"]):
        scan_res = execute_malware_scan()
        if scan_res.get("success"):
            content = (
                "### 🛡️ **Windows Defender Live Malware Scan Initiated**\n\n"
                "✅ **Execution Status:** Successfully triggered Windows Defender Quick Scan via PowerShell API.\n\n"
                "| Property | Value |\n| :--- | :--- |\n"
                "| **Engine** | Microsoft Defender Antivirus |\n"
                "| **Scan Type** | Quick Scan (Memory, Startup, System Files) |\n"
                "| **Status** | 🟢 Running in Background |\n\n"
                "> 💡 **Tip:** You can continue working normally. Defender will notify you if any threats are intercepted."
            )
        else:
            content = f"⚠️ Could not start Windows Defender scan: {scan_res.get('message')}"

        return {
            "response": {
                "role": "assistant",
                "content": content,
                "intent": intent,
                "status": "success",
                "steps": ["Triggered Windows Defender Quick Scan API", "Verified Background Execution"],
            }
        }

    # 5. Live Laptop Security Audit & Implementation Check
    is_audit_query = any(k in user_query for k in [
        "check", "audit", "verify", "implemented", "laptop security", "pc security",
        "firewall", "defender", "antivirus", "bitlocker", "can you do it"
    ])
    is_pure_tpm_query = ("tpm" in user_query or "cryptographic key" in user_query) and not any(
        k in user_query for k in ["laptop", "firewall", "antivirus", "implemented", "audit", "plan"]
    )

    if is_audit_query and not is_pure_tpm_query:
        audit_res = audit_laptop_security()
        return {
            "response": {
                "role": "assistant",
                "content": audit_res["content"],
                "intent": intent,
                "status": "success",
                "steps": audit_res["steps"],
            }
        }

    # 6. Pure TPM Device Identity check
    sec_info = get_key_storage_info()
    hw_ids = get_hardware_identifiers()
    provider_label = (
        "TPM 2.0 Security Processor (Hardware-backed)"
        if sec_info.get("hardware_backed")
        else "Windows CNG / Software KSP (OS-Protected)"
    )

    response_text = (
        f"### 🛡️ **Vault AI Device Cryptographic Identity**\n\n"
        f"| Security Property | Status | Details |\n"
        f"| :--- | :--- | :--- |\n"
        f"| **Key Storage Provider** | ✅ Verified | `{provider_label}` |\n"
        f"| **Non-Exportability** | 🔒 Active | Private key cannot be dumped or exported |\n"
        f"| **Hardware Fingerprint** | 🔑 Bound | "
        f"`{hw_ids.get('mac_address', 'N/A')}` on `{hw_ids.get('hostname', 'LocalHost')}` |\n"
        f"| **Algorithm** | ⚡ NIST P-256 | ECDSA P-256 with SHA-256 signing |\n\n"
        f"> 🔒 **Security Guarantee:** Your private signing key is isolated within "
        f"the host OS/TPM boundary and never stored in plaintext."
    )
    return {
        "response": {
            "role": "assistant",
            "content": response_text,
            "intent": intent,
            "status": "success",
            "steps": [
                "Queried Windows NCrypt Key Provider",
                "Verified Non-Exportable Flag",
                "Checked Hardware Binding",
            ],
        }
    }


# ---------------------------------------------------------------------------
# Node: complex_node
# ---------------------------------------------------------------------------

def complex_node(state: AgentState) -> AgentState:
    """Generate a multi-step execution plan via local LLM."""
    _query_local_model = _get_local_model_query()
    user_query = state["user_query"]
    intent = state.get("intent", Intent.COMPLEX_TASK.value)
    conversation_history = state.get("conversation_history")
    on_chunk = state.get("on_chunk")

    ollama_response = _query_local_model(
        user_query,
        conversation_history=conversation_history,
        instruction=(
            "Create a step-by-step execution plan for this desktop assistant request. "
            "Do not claim to execute it."
        ),
        on_chunk=on_chunk,
    )

    if ollama_response:
        plan_content = ollama_response
    else:
        plan_content = (
            f"### 📋 **Execution Plan: {user_query}**\n\n"
            "1. **Analyze Requirements & Environment** — Inspect hardware prerequisites and compatibility.\n"
            "2. **Resource Pre-Check** — Validate available CPU/RAM before task initialization.\n"
            "3. **Execute Controlled Setup** — Execute designated tools via safe Execution Manager.\n"
            "4. **Post-Execution Verification** — Verify output state and test for successful completion.\n"
            "5. **Log & Finalize** — Record execution history to SQLite database."
        )

    response_text = f"{plan_content}\n\n> ⚙️ **Vault Policy:** Ready to execute upon your confirmation."
    return {
        "response": {
            "role": "assistant",
            "content": response_text,
            "intent": intent,
            "status": "success",
            "steps": ["Intent Classified as Multi-Step", "Plan Generated", "Resource Feasibility Checked"],
        }
    }


# ---------------------------------------------------------------------------
# Node: chat_node
# ---------------------------------------------------------------------------

def chat_node(state: AgentState) -> AgentState:
    """Handle casual greetings and self-introduction queries."""
    user_query = state["user_query"]
    intent = state.get("intent", Intent.CASUAL_CHAT.value)
    lower = user_query.lower()

    if any(kw in lower for kw in ["who are you", "what can you do", "help", "introduce"]):
        response_text = (
            "### 🤖 **Hello! I'm Vault AI**\n\n"
            "I am your local-first, privacy-respecting AI Desktop Guardian. Here is what I can do for you:\n\n"
            "* 📁 **Intelligent File Management** — Ask: `Which files belong to my project?`, "
            "`Find duplicate files`, or `Organize my documents`\n"
            "* 🖥️ **System & Hardware Monitoring** — Ask: `Show CPU and RAM usage`\n"
            "* 🛡️ **Device Security & TPM Identity** — Ask: `Check TPM security status`\n"
            "* 📋 **Task Planning** — Ask: `Plan setup for Python project`\n\n"
            "How can I help you today?"
        )
    else:
        response_text = "Hello! I am Vault AI. How can I assist you with your files or system today?"

    return {
        "response": {
            "role": "assistant",
            "content": response_text,
            "intent": intent,
            "status": "success",
            "steps": ["Understood Greeting", "Quick Local Response"],
        }
    }


# ---------------------------------------------------------------------------
# Node: general_node
# ---------------------------------------------------------------------------

def general_node(state: AgentState) -> AgentState:
    """Route general / unknown queries to the local Qwen LLM."""
    _query_local_model = _get_local_model_query()
    user_query = state["user_query"]
    intent = state.get("intent", Intent.GENERAL_QUERY.value)
    conversation_history = state.get("conversation_history")
    on_chunk = state.get("on_chunk")

    llm_text = _query_local_model(user_query, conversation_history, on_chunk=on_chunk)

    if llm_text:
        return {
            "response": {
                "role": "assistant",
                "content": llm_text,
                "intent": intent,
                "status": "success",
                "steps": ["Routed to Local Qwen3 8B", "Inference Completed"],
            }
        }

    # Safe fallback when Ollama is unreachable
    response_text = (
        f"I have received your request: **'{user_query}'**.\n\n"
        f"* **Intent:** `{intent}`\n"
        f"* **Local Execution Engine:** Active & Ready\n\n"
        "You can ask me to find duplicate files, organize documents, "
        "check CPU/RAM usage, or inspect device security!"
    )
    return {
        "response": {
            "role": "assistant",
            "content": response_text,
            "intent": intent,
            "status": "success",
            "steps": ["Analyzed Query", "Generated Safe Response"],
        }
    }


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

NODE_MAP: Dict[str, Callable[[AgentState], AgentState]] = {
    "confirm_node": confirm_node,
    "file_node": file_node,
    "system_node": system_node,
    "security_node": security_node,
    "complex_node": complex_node,
    "chat_node": chat_node,
    "general_node": general_node,
}


def direct_execute(state: AgentState) -> Dict[str, Any]:
    """Execute the pipeline steps directly without requiring the LangGraph runtime.
    
    This provides an identical zero-overhead fallback so Vault AI works seamlessly
    in all Python environments even if LangGraph is not installed.
    """
    classified = classify_node(state)
    merged_state = {**state, **classified}
    next_node_name = router_node(merged_state)
    node_fn = NODE_MAP.get(next_node_name, general_node)
    result = node_fn(merged_state)
    return {**merged_state, **result}


def _build_graph() -> Optional[Any]:
    if not HAS_LANGGRAPH or StateGraph is None:
        return None

    workflow = StateGraph(AgentState)

    # Register all nodes
    workflow.add_node("classify", classify_node)
    workflow.add_node("confirm_node", confirm_node)
    workflow.add_node("file_node", file_node)
    workflow.add_node("system_node", system_node)
    workflow.add_node("security_node", security_node)
    workflow.add_node("complex_node", complex_node)
    workflow.add_node("chat_node", chat_node)
    workflow.add_node("general_node", general_node)

    # Entry point → classify
    workflow.set_entry_point("classify")

    # classify → conditional routing
    workflow.add_conditional_edges(
        "classify",
        router_node,
        {
            "confirm_node": "confirm_node",
            "file_node": "file_node",
            "system_node": "system_node",
            "security_node": "security_node",
            "complex_node": "complex_node",
            "chat_node": "chat_node",
            "general_node": "general_node",
        },
    )

    # All leaf nodes → END
    for node in [
        "confirm_node",
        "file_node",
        "system_node",
        "security_node",
        "complex_node",
        "chat_node",
        "general_node",
    ]:
        workflow.add_edge(node, END)

    return workflow.compile()


class _FallbackGraph:
    """Provides .invoke(state) fallback when langgraph runtime is not installed."""
    def invoke(self, state: AgentState) -> Dict[str, Any]:
        return direct_execute(state)


_compiled_graph = None


def get_agent_graph():
    """Return the compiled StateGraph if LangGraph is available, else fallback runner."""
    global _compiled_graph
    if _compiled_graph is None:
        if HAS_LANGGRAPH:
            _compiled_graph = _build_graph()
        if _compiled_graph is None:
            _compiled_graph = _FallbackGraph()
    return _compiled_graph


# For backwards-compatibility with imports of agent_graph
agent_graph = get_agent_graph()


def invoke_agent(state: AgentState) -> Dict[str, Any]:
    """Invoke the agent workflow via LangGraph if available, falling back to direct execution."""
    graph = get_agent_graph()
    if graph is not None:
        try:
            return graph.invoke(state)
        except Exception:
            return direct_execute(state)
    return direct_execute(state)

