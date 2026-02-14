from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .identity_store import IdentityStore
from .tenant import resolve_user_id


router = APIRouter(prefix="/identity", tags=["identity"])
identity_store = IdentityStore()


class IdentityUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    long_term_value_model: Optional[Dict[str, Any]] = None
    stated_goals: Optional[Dict[str, List[str]]] = None
    behavioral_patterns: Optional[List[Dict[str, Any]]] = None


class DecisionAppendRequest(BaseModel):
    task_id: Optional[str] = None
    decision_type: str = Field(..., min_length=1)
    decision_payload: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


@router.get("/profile")
def get_profile(user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    return {"ok": True, "profile": identity_store.get_profile(user_id)}


@router.post("/profile")
def update_profile(req: IdentityUpdateRequest, user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    profile = identity_store.update_profile(
        user_id=user_id,
        display_name=req.display_name,
        long_term_value_model=req.long_term_value_model,
        stated_goals=req.stated_goals,
        behavioral_patterns=req.behavioral_patterns,
    )
    return {"ok": True, "profile": profile}


@router.post("/decision")
def append_decision(req: DecisionAppendRequest, user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    decision_id = identity_store.append_decision(
        user_id=user_id,
        task_id=req.task_id,
        decision_type=req.decision_type,
        decision_payload=req.decision_payload,
        confidence=req.confidence,
    )
    return {"ok": True, "decision_id": decision_id}


@router.get("/decisions")
def get_decisions(limit: int = 20, user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    rows = identity_store.recent_decisions(user_id=user_id, limit=limit)
    return {"ok": True, "count": len(rows), "results": rows}
