"""Main LangGraph workflow for Vault AI."""

import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
_ROOT = str(Path(__file__).resolve().parents[3])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from langgraph.graph import StateGraph, START, END

from core.ai.orchestration.state import VaultTaskState

from core.ai.orchestration.nodes import (
    classify_request_node,
    casual_chat_node,
    system_status_node,
    security_check_node,
    file_operation_node,
    general_query_node,
    confirm_action_node,
    assess_resources_node,
    generate_plan_node,
    resource_blocked_node,
)

from core.ai.orchestration.conditions import (
    route_after_classification,
    route_after_resource_assessment,
)


def build_vault_graph():
    """Build and compile the Vault AI LangGraph workflow."""
    workflow = StateGraph(VaultTaskState)

    # Register workflow nodes
    workflow.add_node("classify_request", classify_request_node)
    workflow.add_node("casual_chat", casual_chat_node)
    workflow.add_node("system_status", system_status_node)
    workflow.add_node("security_check", security_check_node)
    workflow.add_node("file_operation", file_operation_node)
    workflow.add_node("general_query", general_query_node)
    workflow.add_node("confirm_action", confirm_action_node)
    workflow.add_node("assess_resources", assess_resources_node)
    workflow.add_node("generate_plan", generate_plan_node)
    workflow.add_node("resource_blocked", resource_blocked_node)

    # Starting point: classify user intent
    workflow.add_edge(START, "classify_request")

    # Intent-based routing from classifier
    workflow.add_conditional_edges(
        "classify_request",
        route_after_classification,
        {
            "assess_resources": "assess_resources",
            "casual_chat": "casual_chat",
            "system_status": "system_status",
            "security_check": "security_check",
            "file_operation": "file_operation",
            "general_query": "general_query",
            "confirm_action": "confirm_action",
            "end": END,
        },
    )

    # Resource assessment routing for complex tasks
    workflow.add_conditional_edges(
        "assess_resources",
        route_after_resource_assessment,
        {
            "generate_plan": "generate_plan",
            "blocked": "resource_blocked",
            "end": END,
        },
    )

    # Terminal edges
    workflow.add_edge("casual_chat", END)
    workflow.add_edge("system_status", END)
    workflow.add_edge("security_check", END)
    workflow.add_edge("file_operation", END)
    workflow.add_edge("general_query", END)
    workflow.add_edge("confirm_action", END)
    workflow.add_edge("generate_plan", END)
    workflow.add_edge("resource_blocked", END)

    return workflow.compile()


vault_graph = build_vault_graph()


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Hello"
    print(f"\n--- Testing LangGraph with prompt: '{prompt}' ---")
    result = vault_graph.invoke({"user_query": prompt})
    print(f"Status: {result.get('status')}")
    print(f"Intent: {result.get('intent')}")
    print(f"Steps:  {result.get('steps')}")
    print(f"\nResponse:\n{result.get('response')}\n")
