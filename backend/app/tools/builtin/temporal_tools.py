from __future__ import annotations

import json
from typing import Any, Dict

from pydantic import Field

from app.background import TemporalTaskRunner
from app.memory import memory_service, new_task_id
from app.tools.base import BaseTool, ToolContext, ToolExecutionError, ToolInput, ToolOutput


class TemporalCreateInput(ToolInput):
    kind: str = Field(min_length=1, max_length=120)
    run_at_epoch: int = Field(gt=0)
    payload: Dict[str, Any] = Field(default_factory=dict)


class TemporalCreateTool(BaseTool[TemporalCreateInput]):
    name = "temporal_create"
    description = "Creates a temporal task in the background runner queue."

    input_model = TemporalCreateInput

    def __init__(self, runner: TemporalTaskRunner) -> None:
        self.runner = runner

    def run(self, ctx: ToolContext, args: TemporalCreateInput) -> ToolOutput:
        if not args.kind.strip():
            raise ToolExecutionError("kind cannot be empty")

        task_id = new_task_id()
        temporal_task_id = self.runner.enqueue(
            user_id=ctx.user_id,
            task_id=task_id,
            kind=args.kind.strip(),
            payload_json=json.dumps(args.payload, ensure_ascii=False),
            run_at_epoch=args.run_at_epoch,
        )

        memory_service.write_task_event(
            user_id=ctx.user_id,
            task_id=task_id,
            intent="temporal_create_tool",
            user_input=f"create temporal task kind={args.kind}",
            outcome="temporal_task_enqueued",
            executor="TemporalCreateTool.run",
            status="success",
            extra={
                "temporal_task_id": temporal_task_id,
                "kind": args.kind,
                "run_at_epoch": args.run_at_epoch,
                "payload": args.payload,
                "trace_id": ctx.trace_id,
            },
        )

        return ToolOutput(
            ok=True,
            data={
                "temporal_task_id": temporal_task_id,
                "status": "queued",
            },
        )
