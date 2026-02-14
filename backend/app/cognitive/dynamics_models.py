from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DecayConfig:
    half_life_days: float = 30.0
    min_confidence: float = 0.05
    max_confidence: float = 1.0


@dataclass(frozen=True)
class ReinforcementConfig:
    boost_per_reference: float = 0.015
    max_references_per_event: int = 1


@dataclass(frozen=True)
class ContradictionConfig:
    lexical_threshold: float = 0.78
    numeric_relative_tolerance: float = 0.02
    min_text_len: int = 4


@dataclass(frozen=True)
class DynamicsConfig:
    decay: DecayConfig = DecayConfig()
    reinforcement: ReinforcementConfig = ReinforcementConfig()
    contradiction: ContradictionConfig = ContradictionConfig()
    semantic_memory_type: str = "semantic"
    correction_relation: str = "corrects"
    contradiction_relation: str = "contradicts"


@dataclass
class ContradictionCandidate:
    left_memory_id: int
    right_memory_id: int
    reason: str
    score: float
    field_name: Optional[str] = None
