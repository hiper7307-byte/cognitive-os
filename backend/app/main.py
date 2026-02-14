from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .cognitive.meta_eval_routes import router as cognitive_meta_eval_router

from .agent.loop_v2 import IterativeAgentLoopV2
from .agent_loop import AgentInput, agent_loop
from .background import TemporalTaskRunner
from .bootstrap_agent_v2 import build_agent_loop_v2, build_tool_registry
from .cognitive.arbitration_routes import router as cognitive_arbitration_router
from .cognitive.dynamics_routes import router as cognitive_dynamics_router
from .cognitive.identity_routes import router as cognitive_identity_router
from .cognitive.graph_routes import router as cognitive_graph_router
from .cognitive.meta_eval_routes import router as cognitive_meta_router
from .debug_env import router as debug_router
from .idempotency import get_idempotency_key, persist_idempotent_response, replay_or_validate
from .identity_routes import router as identity_router
from .llm_client import llm_client
from .llm_routes import router as llm_router
from .memory import memory_service, new_task_id
from .memory_governance_routes import router as memory_governance_router
from .routes.agent_v2_routes import router as agent_v2_router
from .routes.tool_routes import router as tool_router
from .schemas import (
    MemoryQueryRequest,
    TaskRequest,
    TaskResponse,
    TemporalTaskCreateRequest,
    TemporalTaskCreateResponse,
)
from .tenant import resolve_user_id
from .tools.executor import ToolExecutor
from .tools.registry import ToolRegistry
from .vector_routes import router as vector_router

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")



runner = TemporalTaskRunner()


@asynccontextmanager
async def lifespan(app: FastAPI):
    runner.start()

    registry = build_tool_registry(runner=runner)
    executor = ToolExecutor(registry)
    loop_v2 = build_agent_loop_v2(registry=registry)

    app.state.tool_registry = registry
    app.state.tool_executor = executor
    app.state.agent_loop_v2 = loop_v2

    try:
        yield
    finally:
        runner.stop()


app = FastAPI(title="AI OS / Agent Platform", version="1.6.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(llm_router)
app.include_router(vector_router)
app.include_router(debug_router)
app.include_router(identity_router)
app.include_router(memory_governance_router)
app.include_router(cognitive_dynamics_router)
app.include_router(cognitive_identity_router)
app.include_router(cognitive_arbitration_router)
app.include_router(cognitive_graph_router)
app.include_router(cognitive_meta_router)
app.include_router(cognitive_meta_eval_router)

from .temporal_routes import router as temporal_router  # noqa: E402

app.include_router(temporal_router)
app.include_router(agent_v2_router)
app.include_router(tool_router)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "ai_task_os_backend",
        "llm_enabled": llm_client.enabled,
        "agent_v2_enabled": isinstance(getattr(app.state, "agent_loop_v2", None), IterativeAgentLoopV2),
        "tools_enabled": isinstance(getattr(app.state, "tool_registry", None), ToolRegistry),
    }


@app.post("/task", response_model=TaskResponse)
def run_task(
    req: TaskRequest,
    user_id: str = Depends(resolve_user_id),
    idem_key: Optional[str] = Depends(get_idempotency_key),
) -> Dict[str, Any]:
    payload = {"text": req.text}
    cached = replay_or_validate(
        user_id=user_id,
        endpoint="/task",
        idem_key=idem_key,
        payload=payload,
    )
    if cached is not None:
        return cached

    response = agent_loop.run_once(AgentInput(text=req.text), user_id=user_id)

    persist_idempotent_response(
        user_id=user_id,
        endpoint="/task",
        idem_key=idem_key,
        payload=payload,
        response=response,
        status_code=200,
    )
    return response


@app.post("/memory/query")
def memory_query(req: MemoryQueryRequest, user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    results = memory_service.retrieve(
        user_id=user_id,
        query=req.query.strip(),
        memory_types=req.types,
        limit=req.limit,
    )
    return {"ok": True, "count": len(results), "results": results}


@app.get("/memory/recent")
def memory_recent(
    memory_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    user_id: str = Depends(resolve_user_id),
) -> Dict[str, Any]:
    rows = memory_service.recent(user_id=user_id, memory_type=memory_type, limit=limit)
    return {"ok": True, "count": len(rows), "results": rows}


@app.post("/temporal/create", response_model=TemporalTaskCreateResponse)
def temporal_create(
    req: TemporalTaskCreateRequest,
    user_id: str = Depends(resolve_user_id),
    idem_key: Optional[str] = Depends(get_idempotency_key),
) -> Dict[str, Any]:
    if req.run_at_epoch <= 0:
        raise HTTPException(status_code=400, detail="run_at_epoch must be > 0")

    payload = {
        "kind": req.kind,
        "run_at_epoch": req.run_at_epoch,
        "payload": req.payload,
    }
    cached = replay_or_validate(
        user_id=user_id,
        endpoint="/temporal/create",
        idem_key=idem_key,
        payload=payload,
    )
    if cached is not None:
        return cached

    task_id = new_task_id()
    temporal_task_id = runner.enqueue(
        user_id=user_id,
        task_id=task_id,
        kind=req.kind.strip(),
        payload_json=json.dumps(req.payload, ensure_ascii=False),
        run_at_epoch=req.run_at_epoch,
    )

    memory_service.write_task_event(
        user_id=user_id,
        task_id=task_id,
        intent="temporal_create",
        user_input=f"create temporal task kind={req.kind}",
        outcome="temporal_task_enqueued",
        executor="runner.enqueue",
        status="success",
        extra={
            "temporal_task_id": temporal_task_id,
            "kind": req.kind,
            "run_at_epoch": req.run_at_epoch,
            "payload": req.payload,
        },
    )

    response = {"ok": True, "temporal_task_id": temporal_task_id, "status": "queued"}

    persist_idempotent_response(
        user_id=user_id,
        endpoint="/temporal/create",
        idem_key=idem_key,
        payload=payload,
        response=response,
        status_code=200,
    )
    return response
