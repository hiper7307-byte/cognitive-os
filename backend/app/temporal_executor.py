from __future__ import annotations

from typing import Any, Dict

from .agent_loop import AgentInput, agent_loop
from .memory import memory_service


class TemporalExecutor:
    def execute(self, *, user_id: str, task_id: str, kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        kind_norm = (kind or "").strip().lower()

        if kind_norm == "run_task":
            text = str(payload.get("text", "")).strip()
            if not text:
                memory_service.write_task_event(
                    user_id=user_id,
                    task_id=task_id,
                    intent="temporal_run_task",
                    user_input="",
                    outcome="temporal_run_task_empty_payload",
                    executor="TemporalExecutor.execute",
                    status="failed",
                    extra={"kind": kind_norm, "payload": payload},
                )
                return {"ok": False, "error": "payload.text is required"}

            result = agent_loop.run_once(AgentInput(text=text), user_id=user_id)
            memory_service.write_task_event(
                user_id=user_id,
                task_id=task_id,
                intent="temporal_run_task",
                user_input=text,
                outcome="temporal_run_task_executed",
                executor="TemporalExecutor.execute",
                status="success",
                extra={"kind": kind_norm, "result": result},
            )
            return {"ok": True, "result": result}

        if kind_norm == "write_semantic":
            text = str(payload.get("text", "")).strip()
            if not text:
                return {"ok": False, "error": "payload.text is required"}
            memory_id = memory_service.write_semantic_fact(
                user_id=user_id,
                fact_text=text,
                source_task_id=task_id,
                metadata={"source": "temporal_executor"},
            )
            memory_service.write_task_event(
                user_id=user_id,
                task_id=task_id,
                intent="temporal_write_semantic",
                user_input=text,
                outcome="temporal_semantic_written",
                executor="TemporalExecutor.execute",
                status="success",
                extra={"kind": kind_norm, "memory_id": memory_id},
            )
            return {"ok": True, "memory_id": memory_id}

        memory_service.write_task_event(
            user_id=user_id,
            task_id=task_id,
            intent="temporal_unknown_kind",
            user_input="",
            outcome="temporal_unknown_kind",
            executor="TemporalExecutor.execute",
            status="failed",
            extra={"kind": kind_norm, "payload": payload},
        )
        return {"ok": False, "error": f"unsupported kind: {kind}"}


temporal_executor = TemporalExecutor()
