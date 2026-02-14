from __future__ import annotations

from typing import Any, Dict, List

from .memory import memory_service


def build_plan(goal: str, context_limit: int = 10) -> Dict[str, Any]:
    clean_goal = (goal or "").strip()
    if not clean_goal:
        return {"ok": False, "message": "goal is empty", "data": {}}

    context_hits = memory_service.retrieve(
        query=clean_goal,
        memory_types=["procedural", "semantic", "episodic"],
        limit=context_limit,
    )

    steps: List[str] = [
        f"Define success criteria for: {clean_goal}",
        "Enumerate constraints, resources, and deadlines",
        "Split into milestones and executable tasks",
        "Execute next critical task in current cycle",
        "Review outcome and write reflection memory",
    ]

    return {
        "ok": True,
        "message": "plan_created",
        "data": {
            "goal": clean_goal,
            "steps": steps,
            "context": context_hits,
        },
    }
