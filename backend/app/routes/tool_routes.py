from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.tenant import resolve_user_id
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolExecuteRequest(BaseModel):
    name: str = Field(min_length=1)
    args: Dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None
    task_id: Optional[str] = None


def _get_registry(request: Request) -> ToolRegistry:
    reg = getattr(request.app.state, "tool_registry", None)
    if reg is None:
        raise HTTPException(status_code=503, detail="Tool registry not initialized")
    return reg


def _get_executor(request: Request) -> ToolExecutor:
    exe = getattr(request.app.state, "tool_executor", None)
    if exe is None:
        raise HTTPException(status_code=503, detail="Tool executor not initialized")
    return exe


@router.get("")
def list_tools(registry: ToolRegistry = Depends(_get_registry)) -> Dict[str, Any]:
    specs = registry.list_specs()
    return {
        "ok": True,
        "count": len(specs),
        "tools": [
            {
                "name": s.name,
                "description": s.description,
                "input_schema": s.input_schema,
            }
            for s in specs
        ],
    }


@router.post("/execute")
def execute_tool(
    req: ToolExecuteRequest,
    request: Request,
    user_id: str = Depends(resolve_user_id),
    executor: ToolExecutor = Depends(_get_executor),
) -> Dict[str, Any]:
    rec = executor.execute(
        user_id=user_id,
        tool_name=req.name,
        args=req.args,
        task_id=req.task_id,
        trace_id=req.trace_id,
        metadata={"source": "route:/tools/execute"},
    )
    return {
        "ok": rec.ok,
        "tool": rec.tool_name,
        "latency_ms": rec.latency_ms,
        "output": rec.output,
        "error": rec.error,
    }
