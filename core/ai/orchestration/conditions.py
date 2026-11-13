
"""Conditional routing functions for Vault AI LangGraph."""

from core.ai.orchestration.state import VaultTaskState


def route_after_classification(state: VaultTaskState) -> str:
    status = state.get("status", "")
    intent = state.get("intent", "")

    if status != "classified":
        return "end"

    if intent == "complex_task":
        return "assess_resources"

    return "end"


def route_after_resource_assessment(state: VaultTaskState) -> str:
    if state.get("status") != "resources_checked":
        return "end"

    model_assessment = state.get("model_assessment", {})

    # Fail safely if model assessment is missing.
    if not model_assessment:
        return "blocked"

    if model_assessment.get("recommended"):
        return "generate_plan"

    return "blocked"


def route_after_planning(state: VaultTaskState) -> str:
    status = state.get("status", "")

    if status == "planned":
        return "end"

    if status == "failed":
        return "end"

    return "end"
