"""Main LangGraph workflow for Vault AI."""

from langgraph.graph import StateGraph, START, END

from core.ai.orchestration.state import VaultTaskState

from core.ai.orchestration.nodes import (
    classify_request_node,
    assess_resources_node,
    generate_plan_node,
)

from core.ai.orchestration.conditions import (
    route_after_classification,
    route_after_resource_assessment,
    route_after_planning,
)

def resource_blocked_node(state: VaultTaskState) -> dict:
    """Stop planning when model resources are insufficient."""

    assessment = state.get("model_assessment", {})

    reason = assessment.get(
        "reason",
        "Model resource assessment is missing."
    )

    return {
        "status": "blocked",
        "response": (
            "Task planning was paused because the selected model "
            f"cannot safely run with the available resources. Reason: {reason}"
        ),
        "steps": state.get("steps", []) + [
            "Task blocked by model resource assessment"
        ],
    }

def build_vault_graph():

    workflow = StateGraph(VaultTaskState)

    # Register nodes
    workflow.add_node("classify_request", classify_request_node)
    workflow.add_node("assess_resources", assess_resources_node)
    workflow.add_node("generate_plan", generate_plan_node)
    workflow.add_node("resource_blocked", resource_blocked_node)

    # Starting point
    workflow.add_edge(START, "classify_request")

    # Classification routing
    workflow.add_conditional_edges(
        "classify_request",
        route_after_classification,
        {
            "assess_resources": "assess_resources",
            "end": END,
        },
    )

    # Resource assessment routing
    workflow.add_conditional_edges(
        "assess_resources",
        route_after_resource_assessment,
        {
            "generate_plan": "generate_plan",
            "blocked": "resource_blocked",
            "end": END,
        },
    )

    # Planning routing
    workflow.add_conditional_edges(
        "generate_plan",
        route_after_planning,
        {
            "end": END,
        },
    )

    # Stop after resource blocking
    workflow.add_edge("resource_blocked", END)

    return workflow.compile()


vault_graph = build_vault_graph()