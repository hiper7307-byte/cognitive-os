from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .memory import memory_service
from .tenant import resolve_user_id


router = APIRouter(prefix="/memory/governance", tags=["memory-governance"])


class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    retention_until: Optional[str] = None


class MemoryCorrectRequest(BaseModel):
    corrected_content: str = Field(..., min_length=1)
    correction_metadata: Optional[Dict[str, Any]] = None
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)


@router.post("/update/{memory_id}")
def update_memory(memory_id: int, req: MemoryUpdateRequest, user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    ok = memory_service.store.update_memory(
        user_id=user_id,
        memory_id=memory_id,
        content=req.content,
        metadata=req.metadata,
        confidence=req.confidence,
        retention_until=req.retention_until,
    )
    return {"ok": ok, "memory_id": memory_id}


@router.post("/correct/{memory_id}")
def correct_memory(memory_id: int, req: MemoryCorrectRequest, user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    new_id = memory_service.store.correct_memory(
        user_id=user_id,
        memory_id=memory_id,
        corrected_content=req.corrected_content,
        correction_metadata=req.correction_metadata,
        confidence=req.confidence,
    )
    return {"ok": new_id is not None, "memory_id": memory_id, "corrected_memory_id": new_id}


@router.post("/delete/{memory_id}")
def soft_delete_memory(memory_id: int, user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    ok = memory_service.store.soft_delete_memory(user_id=user_id, memory_id=memory_id)
    return {"ok": ok, "memory_id": memory_id}


@router.get("/revisions/{memory_id}")
def get_revisions(memory_id: int, limit: int = 50, user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    rows = memory_service.store.memory_revisions(user_id=user_id, memory_id=memory_id, limit=limit)
    return {"ok": True, "count": len(rows), "results": rows}


@router.post("/purge_expired")
def purge_expired(user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    n = memory_service.store.purge_expired(user_id=user_id)
    return {"ok": True, "purged": n}
