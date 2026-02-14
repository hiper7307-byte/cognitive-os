from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple

from app.cognitive.arbitration_models import (
    ArbitrationComponentScores,
    ArbitrationConfig,
    ArbitrationMetadata,
)
from app.cognitive.identity_service import IdentityAlignmentService
from app.cognitive.identity_store import IdentityAlignmentStore
from app.memory import memory_service


def _now_epoch() -> int:
    return int(time.time())


def _tokens(text: str) -> set[str]:
    out = set()
    cur = []
    for ch in (text or "").lower():
        if ch.isalnum() or ch == "'":
            cur.append(ch)
        else:
            if cur:
                out.add("".join(cur))
                cur = []
    if cur:
        out.add("".join(cur))
    return out


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


class ArbitrationService:
    def __init__(
        self,
        *,
        config: Optional[ArbitrationConfig] = None,
        identity_alignment_service: Optional[IdentityAlignmentService] = None,
    ) -> None:
        self.config = config or ArbitrationConfig()
        if identity_alignment_service is not None:
            self.identity_alignment_service = identity_alignment_service
        else:
            self.identity_alignment_service = IdentityAlignmentService(
                store=IdentityAlignmentStore(
                    db_path=self._default_db_path(),
                )
            )

    @staticmethod
    def _default_db_path() -> str:
        # kept local fallback; runtime typically injects singleton
        from os import getenv
        from os.path import dirname, join
        return getenv("AI_OS_DB_PATH", join(dirname(dirname(__file__)), "ai_os_memory.db"))

    def arbitrate(
        self,
        *,
        user_id: str,
        prompt: str,
        candidate_action: Optional[str] = None,
        memory_types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        query = (prompt or "").strip()
        if not query:
            return {
                "ok": True,
                "route_mode": "model",
                "final_score": 0.0,
                "selected_memory": None,
                "metadata": self._metadata(
                    route_mode="model",
                    final_score=0.0,
                    component_scores={
                        "semantic_similarity": 0.0,
                        "lexical_score": 0.0,
                        "recency_weight": 0.0,
                        "confidence_weight": 0.0,
                        "identity_alignment_weight": 0.0,
                        "contradiction_penalty": 0.0,
                    },
                    selected_memory_id=None,
                    contradiction_hits=0,
                    rationale="empty_prompt",
                ),
            }

        rows = memory_service.retrieve(
            user_id=user_id,
            query=query,
            memory_types=memory_types,
            limit=limit,
        )

        identity = self.identity_alignment_service.score_alignment(
            user_id=user_id,
            text=query,
            candidate_action=candidate_action,
        )
        identity_score = _safe_float(identity.get("score"), 0.0)

        best_row, best_score, best_components, contradiction_hits = self._rank_rows(
            query=query,
            rows=rows,
            identity_score=identity_score,
        )

        route_mode = self._decide_route(best_score)
        rationale = self._rationale(route_mode=route_mode, score=best_score, rows_count=len(rows))

        return {
            "ok": True,
            "route_mode": route_mode,
            "final_score": round(best_score, 6),
            "selected_memory": best_row,
            "metadata": self._metadata(
                route_mode=route_mode,
                final_score=best_score,
                component_scores=best_components,
                selected_memory_id=_safe_int(best_row.get("id")) if best_row else None,
                contradiction_hits=contradiction_hits,
                rationale=rationale,
            ),
        }

    def _rank_rows(
        self,
        *,
        query: str,
        rows: List[Dict[str, Any]],
        identity_score: float,
    ) -> Tuple[Optional[Dict[str, Any]], float, ArbitrationComponentScores, int]:
        best_row: Optional[Dict[str, Any]] = None
        best_score = -1.0
        best_components: ArbitrationComponentScores = {
            "semantic_similarity": 0.0,
            "lexical_score": 0.0,
            "recency_weight": 0.0,
            "confidence_weight": 0.0,
            "identity_alignment_weight": 0.0,
            "contradiction_penalty": 0.0,
        }

        contradiction_hits = 0
        q_tokens = _tokens(query)
        now = _now_epoch()
        half_life_days = max(self.config.recency_half_life_days, 0.0001)
        decay_lambda = math.log(2.0) / (half_life_days * 86400.0)
        w = self.config.weights

        for row in rows:
            content = str(row.get("content", "") or row.get("text", "") or "")
            c_tokens = _tokens(content)

            semantic_similarity = _jaccard(q_tokens, c_tokens)
            lexical_score = semantic_similarity  # kept explicit for future split into BM25/FTS score

            updated_at = _safe_int(row.get("updated_at"), _safe_int(row.get("created_at"), now))
            age_sec = max(0, now - updated_at)
            recency_weight = math.exp(-decay_lambda * age_sec)

            confidence_weight = min(1.0, max(0.0, _safe_float(row.get("confidence"), 0.5)))
            identity_alignment_weight = min(1.0, max(0.0, identity_score))

            contradiction_penalty = self._contradiction_penalty(content)
            if contradiction_penalty > 0:
                contradiction_hits += 1

            score = (
                w.semantic_similarity * semantic_similarity
                + w.lexical_score * lexical_score
                + w.recency_weight * recency_weight
                + w.confidence_weight * confidence_weight
                + w.identity_alignment_weight * identity_alignment_weight
                - w.contradiction_penalty_weight * contradiction_penalty
            )

            if score > best_score:
                best_score = score
                best_row = row
                best_components = {
                    "semantic_similarity": round(semantic_similarity, 6),
                    "lexical_score": round(lexical_score, 6),
                    "recency_weight": round(recency_weight, 6),
                    "confidence_weight": round(confidence_weight, 6),
                    "identity_alignment_weight": round(identity_alignment_weight, 6),
                    "contradiction_penalty": round(contradiction_penalty, 6),
                }

        if best_score < 0:
            best_score = 0.0

        return best_row, best_score, best_components, contradiction_hits

    @staticmethod
    def _contradiction_penalty(content: str) -> float:
        t = (content or "").lower()
        neg_markers = [" not ", " never ", " impossible ", " cannot ", " can't ", " wont ", " won't "]
        marker_hits = sum(1 for m in neg_markers if m in f" {t} ")
        # bounded to [0,1]
        return min(1.0, marker_hits / 2.0)

    def _decide_route(self, score: float) -> str:
        if score >= self.config.thresholds.memory_route_min:
            return "memory"
        if score >= self.config.thresholds.hybrid_route_min:
            return "hybrid"
        return "model"

    def _rationale(self, *, route_mode: str, score: float, rows_count: int) -> str:
        if rows_count == 0:
            return "no_memory_candidates"
        if route_mode == "memory":
            return f"score_above_memory_threshold:{round(score, 4)}"
        if route_mode == "hybrid":
            return f"score_between_thresholds:{round(score, 4)}"
        return f"score_below_hybrid_threshold:{round(score, 4)}"

    def _metadata(
        self,
        *,
        route_mode: str,
        final_score: float,
        component_scores: ArbitrationComponentScores,
        selected_memory_id: Optional[int],
        contradiction_hits: int,
        rationale: str,
    ) -> ArbitrationMetadata:
        return {
            "route_mode": route_mode,  # type: ignore[typeddict-item]
            "final_score": round(final_score, 6),
            "component_scores": component_scores,
            "weights": {
                "semantic_similarity": self.config.weights.semantic_similarity,
                "lexical_score": self.config.weights.lexical_score,
                "recency_weight": self.config.weights.recency_weight,
                "confidence_weight": self.config.weights.confidence_weight,
                "identity_alignment_weight": self.config.weights.identity_alignment_weight,
                "contradiction_penalty_weight": self.config.weights.contradiction_penalty_weight,
            },
            "thresholds": {
                "memory_route_min": self.config.thresholds.memory_route_min,
                "hybrid_route_min": self.config.thresholds.hybrid_route_min,
            },
            "selected_memory_id": selected_memory_id,
            "contradiction_hits": contradiction_hits,
            "rationale": rationale,
        }
