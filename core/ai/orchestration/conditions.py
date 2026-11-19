"""Conditional routing functions for Vault AI LangGraph."""

from core.ai.orchestration.state import VaultTaskState


def route_after_classification(state: VaultTaskState) -> str:
    status = state.get("status", "")
    intent = state.get("intent", "")

    if status != "classified":
        return "general_query"

    if intent == "complex_task":
        return "assess_resources"
    elif intent == "casual_chat":
        return "casual_chat"
    elif intent == "system_status":
        return "system_status"
    elif intent == "security_check":
        return "security_check"
    elif intent == "file_operation":
        return "file_operation"
    elif intent == "confirm_action":
        return "confirm_action"
    else:
        return "general_query"


def route_after_resource_assessment(state: VaultTaskState) -> str:
    if state.get("status") != "resources_checked":
        return "blocked"

    model_assessment = state.get("model_assessment", {})
    if not model_assessment:
        return "blocked"

    if model_assessment.get("recommended", False):
        return "generate_plan"

    return "blocked"


def route_after_planning(state: VaultTaskState) -> str:
    return "end"
