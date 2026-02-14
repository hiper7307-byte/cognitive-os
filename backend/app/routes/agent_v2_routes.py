from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agent.loop_v2 import IterativeAgentLoopV2
from app.memory import memory_service, new_task_id
from app.tenant import resolve_user_id
from app.tools.models import AgentRunRequest, AgentRunResponse

router = APIRouter(prefix="/agent/v2", tags=["agent_v2"])


def get_agent_loop(request: Request) -> IterativeAgentLoopV2:
    loop = getattr(request.app.state, "agent_loop_v2", None)
    if loop is None:
        raise HTTPException(status_code=503, detail="Agent loop v2 not initialized")
    return loop


@router.post("/run", response_model=AgentRunResponse)
def run_agent_v2(
    req: AgentRunRequest,
    user_id: str = Depends(resolve_user_id),
    loop: IterativeAgentLoopV2 = Depends(get_agent_loop),
) -> AgentRunResponse:
    task_id = new_task_id()
    result = loop.run(user_id=user_id, req=req)

    memory_service.write_task_event(
        user_id=user_id,
        task_id=task_id,
        intent="agent_v2_run",
        user_input=req.prompt,
        outcome="agent_v2_completed" if result.ok else "agent_v2_failed",
        executor="agent_v2_loop",
        status="success" if result.ok else "error",
        extra={
            "max_iterations": req.max_iterations,
            "allow_tools": req.allow_tools,
            "tool_whitelist": req.tool_whitelist,
            "timeout_ms": req.timeout_ms,
            "answer": result.answer,
            "error": result.error,
            "decision_trace": result.decision_trace,
            "tool_traces": result.tool_traces,
            "steps_count": len(result.steps),
        },
    )
    return result
from fastapi.responses import StreamingResponse
import json


@router.post("/stream")
def stream_agent_v2(
    req: AgentRunRequest,
    user_id: str = Depends(resolve_user_id),
    loop: IterativeAgentLoopV2 = Depends(get_agent_loop),
):
    def generator():
        result = loop.run(user_id=user_id, req=req)

        for step in result.steps:
            yield f"data: {json.dumps({'step': step.model_dump()})}\n\n"

        for trace in result.tool_traces:
            yield f"data: {json.dumps({'tool_trace': trace})}\n\n"

        yield f"data: {json.dumps({'final': result.answer})}\n\n"
        yield "data: {\"done\": true}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")
