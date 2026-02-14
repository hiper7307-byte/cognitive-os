from __future__ import annotations

from fastapi import APIRouter, Depends

from app.cognitive.identity_models import (
    IdentityAlignmentRequest,
    IdentityAlignmentResponse,
    IdentityProfileResponse,
    IdentityProfileUpsertRequest,
)
from app.cognitive.runtime import identity_alignment_service
from app.tenant import resolve_user_id

router = APIRouter(prefix="/cognitive/identity", tags=["cognitive_identity"])


@router.get("/profile", response_model=IdentityProfileResponse)
def get_profile(user_id: str = Depends(resolve_user_id)) -> IdentityProfileResponse:
    profile = identity_alignment_service.get_profile(user_id=user_id)
    return IdentityProfileResponse(ok=True, **profile)


@router.put("/profile", response_model=IdentityProfileResponse)
def upsert_profile(
    req: IdentityProfileUpsertRequest,
    user_id: str = Depends(resolve_user_id),
) -> IdentityProfileResponse:
    profile = identity_alignment_service.upsert_profile(
        user_id=user_id,
        values=req.values,
        goals=req.goals,
        constraints=req.constraints,
        risk_tolerance=req.risk_tolerance,
        metadata=req.metadata,
    )
    return IdentityProfileResponse(ok=True, **profile)


@router.post("/score", response_model=IdentityAlignmentResponse)
def score_alignment(
    req: IdentityAlignmentRequest,
    user_id: str = Depends(resolve_user_id),
) -> IdentityAlignmentResponse:
    out = identity_alignment_service.score_alignment(
        user_id=user_id,
        text=req.text,
        candidate_action=req.candidate_action,
    )
    return IdentityAlignmentResponse(**out)
