from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from .executors import exec_list_notes, exec_plan, exec_save_note, exec_semantic, exec_set_reminder
from .intent import classify_intent
from .memory import memory_service, new_task_id
from .reflection import reflect_on_task


@dataclass
class AgentInput:
    text: str


def _normalize_intent(raw: Any) -> Tuple[str, Dict[str, Any]]:
    if isinstance(raw, dict):
        intent = str(raw.get("intent", "semantic"))
        slots = raw.get("slots", {}) or {}
        if not isinstance(slots, dict):
            slots = {}
        return intent, slots
    return str(raw), {}


class AgentLoop:
    def run_once(self, inp: AgentInput, user_id: str = "local-dev") -> Dict[str, Any]:
        task_id = new_task_id()
        raw_intent = classify_intent(inp.text)
        intent, _slots = _normalize_intent(raw_intent)

        if intent == "save_note":
            result = exec_save_note(inp.text, user_id=user_id)
        elif intent == "list_notes":
            result = exec_list_notes(user_id=user_id, limit=20)
        elif intent == "semantic":
            result = exec_semantic(inp.text, user_id=user_id, limit=10)
        elif intent == "plan":
            result = exec_plan(inp.text, user_id=user_id)
        elif intent == "reminder":
            result = exec_set_reminder(inp.text, user_id=user_id)
        else:
            result = exec_semantic(inp.text, user_id=user_id, limit=10)
            intent = "semantic"

        outcome = str(result.get("message", "completed"))
        status = "success" if bool(result.get("ok", False)) else "failed"
        executor = str(result.get("executor", "agent_loop"))

        memory_service.write_task_event(
            user_id=user_id,
            task_id=task_id,
            intent=intent,
            user_input=inp.text,
            outcome=outcome,
            executor=executor,
            status=status,
            extra={"result_data": result.get("data", {})},
            confidence=0.74,
        )

        reflect_on_task(
            task_id=task_id,
            intent=intent,
            input_text=inp.text,
            result=result,
            user_id=user_id,
        )

        return {
            "task_id": task_id,
            "intent": intent,
            "ok": bool(result.get("ok", False)),
            "message": outcome,
            "data": result.get("data", {}),
        }


agent_loop = AgentLoop()
