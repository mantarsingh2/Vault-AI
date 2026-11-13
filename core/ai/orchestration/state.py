from typing import TypedDict, Any, Dict, List


class VaultTaskState(TypedDict, total=False):
    task_id: str
    session_id: str
    user_query: str

    intent: str
    task_type: str

    plan: List[Dict[str, Any]]
    current_step: int

    approval_required: bool
    approval_status: str

    execution_result: Dict[str, Any]

    status: str
    error: str
    response: str
    steps: List[str]
    plan_hash: str
    # General system resource information
    resource_report: Dict[str, Any]
    resource_assessment: Dict[str, Any]

    # Model-specific resource information
    model_assessment: Dict[str, Any]