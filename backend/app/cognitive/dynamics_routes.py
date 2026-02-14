from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.cognitive.runtime import dynamics_service
from app.tenant import resolve_user_id

router = APIRouter(prefix="/cognitive/dynamics", tags=["cognitive_dynamics"])


class ReinforceRequest(BaseModel):
    memory_id: int = Field(gt=0)
    by: int = Field(default=1, ge=1, le=100)


class DecayRequest(BaseModel):
    limit: int = Field(default=500, ge=1, le=5000)


class ContradictionsRequest(BaseModel):
    limit: int = Field(default=400, ge=1, le=3000)


class CorrectionLinkRequest(BaseModel):
    from_memory_id: int = Field(gt=0)
    to_memory_id: int = Field(gt=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.post("/reinforce")
def reinforce(
    req: ReinforceRequest,
    user_id: str = Depends(resolve_user_id),
) -> Dict[str, Any]:
    return dynamics_service.reinforce_memory(user_id=user_id, memory_id=req.memory_id, by=req.by)


@router.post("/decay")
def decay(
    req: DecayRequest,
    user_id: str = Depends(resolve_user_id),
) -> Dict[str, Any]:
    return dynamics_service.apply_decay_pass(user_id=user_id, limit=req.limit)


@router.post("/contradictions/detect")
def contradictions_detect(
    req: ContradictionsRequest,
    user_id: str = Depends(resolve_user_id),
) -> Dict[str, Any]:
    return dynamics_service.detect_contradictions(user_id=user_id, limit=req.limit)


@router.get("/contradictions")
def contradictions_list(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    user_id: str = Depends(resolve_user_id),
) -> Dict[str, Any]:
    return dynamics_service.list_conflicts(user_id=user_id, status=status, limit=limit)


@router.post("/contradictions/{conflict_id}/resolve")
def contradictions_resolve(
    conflict_id: int,
    user_id: str = Depends(resolve_user_id),
) -> Dict[str, Any]:
    return dynamics_service.resolve_conflict(user_id=user_id, conflict_id=conflict_id)


@router.post("/lineage/correct")
def lineage_correct(
    req: CorrectionLinkRequest,
    user_id: str = Depends(resolve_user_id),
) -> Dict[str, Any]:
    return dynamics_service.link_correction(
        user_id=user_id,
        from_memory_id=req.from_memory_id,
        to_memory_id=req.to_memory_id,
        metadata=req.metadata,
    )
