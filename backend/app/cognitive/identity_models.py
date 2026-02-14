from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class IdentityWeights:
    values_weight: float = 0.35
    goals_weight: float = 0.35
    constraints_weight: float = 0.20
    risk_weight: float = 0.10


@dataclass(frozen=True)
class IdentityConfig:
    min_score: float = 0.0
    max_score: float = 1.0
    weights: IdentityWeights = IdentityWeights()


class IdentityProfileUpsertRequest(BaseModel):
    values: List[str] = Field(default_factory=list, max_length=200)
    goals: List[str] = Field(default_factory=list, max_length=200)
    constraints: List[str] = Field(default_factory=list, max_length=200)
    risk_tolerance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Dict[str, str] = Field(default_factory=dict)


class IdentityProfileResponse(BaseModel):
    ok: bool
    user_id: str
    values: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    risk_tolerance: float = 0.5
    updated_at_epoch: int = 0
    metadata: Dict[str, str] = Field(default_factory=dict)


class IdentityAlignmentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    candidate_action: Optional[str] = Field(default=None, max_length=4000)


class IdentityAlignmentResponse(BaseModel):
    ok: bool
    score: float
    components: Dict[str, float] = Field(default_factory=dict)
    matched: Dict[str, List[str]] = Field(default_factory=dict)
    trace: Dict[str, str] = Field(default_factory=dict)
