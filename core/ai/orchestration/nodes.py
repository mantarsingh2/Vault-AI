
"""LangGraph nodes for Vault AI orchestration."""

import json
from core.ai.orchestration.resource_engine import ResourceEngine
from typing import Any

from core.ai.orchestration.state import VaultTaskState
from core.ai.router import classify_intent
from core.ai.ollama_client import OllamaClient


def classify_request_node(state: VaultTaskState) -> dict:
    """
    Classify the user's request using Vault AI's existing router.
    No system operations are performed here.
    """

    user_query = state.get("user_query", "").strip()

    if not user_query:
        return {
            "status": "failed",
            "error": "User query is empty.",
        }

    intent = classify_intent(user_query)

    return {
        "intent": intent.value,
        "task_type": intent.value,
        "status": "classified",
        "steps": ["User request classified"],
    }


def generate_plan_node(state: VaultTaskState) -> dict:
    """
    Generate a structured task plan using the existing Ollama client.
    This node only generates a plan. It does not execute anything.
    """

    user_query = state.get("user_query", "")

    client = OllamaClient()

    # Check local Ollama connection
    if not client.check_connection(timeout=2.0):
        return {
            "status": "failed",
            "error": "Cannot connect to local Ollama.",
        }

    # Check model availability
    if not client.is_model_available():
        return {
            "status": "failed",
            "error": f"Model '{client.default_model}' is unavailable.",
        }

    prompt = f"""
You are Vault AI's task planning engine.

Create a safe, step-by-step plan for this user request:

{user_query}

Rules:
1. Do not execute any operations.
2. Do not invent successful system checks.
3. Return only valid JSON.
4. Each step must have a clear description.

Return this structure:

{{
    "summary": "Brief task summary",
    "plan": [
        {{
            "step": 1,
            "description": "First action",
            "type": "inspection"
        }}
    ]
}}
"""

    result = client.generate(
        prompt=prompt,
        system_prompt="You are a careful desktop AI task planner.",
        response_format="json",
        options={
            "temperature": 0.1,
            "num_predict": 1000,
        },
        think=False,
        timeout=300,
    )

    if not result.get("success"):
        return {
            "status": "failed",
            "error": result.get("error", "Plan generation failed."),
        }

    try:
        parsed = json.loads(result.get("response", ""))

        if not isinstance(parsed, dict):
            raise ValueError("Expected a JSON object.")

        plan = parsed.get("plan")

        if not isinstance(plan, list):
            raise ValueError("Plan must be a list.")

        # Validate individual plan steps
        if not all(
            isinstance(item, dict)
            and isinstance(item.get("description"), str)
            and item["description"].strip()
            for item in plan
        ):
            raise ValueError("Invalid plan step structure.")

        return {
    "plan": plan,
    "response": parsed.get(
        "summary",
        "Task plan generated. Awaiting approval."
    ),
    "status": "awaiting_approval",
    "approval_required": True,
    "approval_status": "pending",
    "steps": [
        "Task plan generated using Qwen",
        "Waiting for user approval",
    ],
}

    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "status": "failed",
            "error": f"Invalid plan returned by AI: {exc}",
        }
def assess_resources_node(state: VaultTaskState) -> dict:
    """Assess general system resources and selected model requirements."""

    try:
        engine = ResourceEngine()

        # Collect hardware information once
        report = engine.get_resource_report()

        # General system resource assessment
        resource_assessment = engine.assess_resources(report)

        # Model-specific resource assessment
        model_assessment = engine.assess_model_resources(
            model_name="qwen3:8b",
            estimated_ram_gb=8.0,
            estimated_vram_gb=4.0,
            report=report,
        )

        previous_steps = state.get("steps", [])

        return {
            "resource_report": report,
            "resource_assessment": resource_assessment,
            "model_assessment": model_assessment,
            "status": "resources_checked",
            "steps": previous_steps + [
                "System resources assessed",
                "Model requirements assessed",
            ],
        }

    except Exception as exc:
        return {
            "status": "failed",
            "error": f"Resource assessment failed: {exc}",
        }