from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Optional, TypedDict


RouteMode = Literal["memory", "hybrid", "model"]


@dataclass(frozen=True)
class ArbitrationWeights:
    semantic_similarity: float = 0.24
    lexical_score: float = 0.16
    recency_weight: float = 0.14
    confidence_weight: float = 0.18
    identity_alignment_weight: float = 0.20
    contradiction_penalty_weight: float = 0.08


@dataclass(frozen=True)
class ArbitrationThresholds:
    memory_route_min: float = 0.72
    hybrid_route_min: float = 0.46


@dataclass(frozen=True)
class ArbitrationConfig:
    weights: ArbitrationWeights = ArbitrationWeights()
    thresholds: ArbitrationThresholds = ArbitrationThresholds()
    recency_half_life_days: float = 21.0


class ArbitrationComponentScores(TypedDict):
    semantic_similarity: float
    lexical_score: float
    recency_weight: float
    confidence_weight: float
    identity_alignment_weight: float
    contradiction_penalty: float


class ArbitrationMetadata(TypedDict, total=False):
    route_mode: RouteMode
    final_score: float
    component_scores: ArbitrationComponentScores
    weights: Dict[str, float]
    thresholds: Dict[str, float]
    selected_memory_id: Optional[int]
    contradiction_hits: int
    rationale: str
