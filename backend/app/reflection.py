from __future__ import annotations

from typing import Any, Dict, Optional

from .memory import memory_service


def reflect_on_task(
    *,
    task_id: str,
    intent: str,
    input_text: str,
    result: Dict[str, Any],
    user_id: str = "local-dev",
) -> int:
    status = "success" if result.get("ok", False) else "failed"
    message = str(result.get("message", ""))
    reflection_text = (
        f"reflection\n"
        f"task={task_id}\n"
        f"intent={intent} status={status}\n"
        f"message={message}"
    )

    metadata = {
        "kind": "reflection",
        "intent": intent,
        "input_text": input_text,
        "result": result.get("data", {}),
    }

    return memory_service.write_procedural_rule(
        user_id=user_id,
        rule_text=reflection_text,
        source_task_id=task_id,
        metadata=metadata,
        confidence=0.72,
    )


def build_reflection(
    *,
    task_id: str,
    intent: str,
    status: str,
    summary: str,
    user_id: str = "local-dev",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    text = (
        f"reflection\n"
        f"task={task_id}\n"
        f"intent={intent} status={status}\n"
        f"message={summary}"
    )
    return memory_service.write_procedural_rule(
        user_id=user_id,
        rule_text=text,
        source_task_id=task_id,
        metadata={"kind": "reflection", **(metadata or {})},
        confidence=0.70,
    )
