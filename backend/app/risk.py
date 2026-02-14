def assess_risk(task_type: str) -> str:
    if task_type in ["email"]:
        return "medium"
    if task_type in ["delete", "payment"]:
        return "high"
    return "low"
