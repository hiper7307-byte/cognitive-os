from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.cognitive.runtime import arbitration_service
from app.tenant import resolve_user_id

router = APIRouter(prefix="/cognitive/arbitration", tags=["cognitive_arbitration"])


class ArbitrationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    candidate_action: Optional[str] = Field(default=None, max_length=4000)
    memory_types: Optional[List[str]] = None
    limit: int = Field(default=20, ge=1, le=200)


@router.post("/score")
def arbitration_score(
    req: ArbitrationRequest,
    user_id: str = Depends(resolve_user_id),
) -> Dict[str, Any]:
    return arbitration_service.arbitrate(
        user_id=user_id,
        prompt=req.prompt,
        candidate_action=req.candidate_action,
        memory_types=req.memory_types,
        limit=req.limit,
    )
