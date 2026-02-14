from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from .background import TemporalTaskRunner
from .tenant import resolve_user_id
from .temporal_store import temporal_store

router = APIRouter()
_runner = TemporalTaskRunner()


@router.get("/temporal/tasks")
def temporal_tasks(
    limit: int = Query(default=20, ge=1, le=200),
    user_id: str = Depends(resolve_user_id),
) -> Dict[str, Any]:
    rows = temporal_store.list_tasks(user_id=user_id, limit=limit)
    return {"ok": True, "count": len(rows), "results": rows}


@router.post("/temporal/run_due_once")
def temporal_run_due_once() -> Dict[str, Any]:
    processed = _runner.run_due_once()
    return {"ok": True, "processed": int(processed)}
