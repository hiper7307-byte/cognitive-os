from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


@dataclass
class ArbitrationResult:
    mode: str  # "memory_only" | "llm_only" | "hybrid"
    confidence: float
    scores: Dict[str, float]
    rationale: str


class ReasoningArbitrator:
    """
    Decides reasoning mode using lightweight deterministic scoring:
    - lexical score (memory query hit ratio)
    - vector score (top similarity if available)
    - recency score (freshness of top memory)
    - confidence score (mean memory confidence)
    """

    def __init__(self) -> None:
        # Tunable weights; keep simple and explicit.
        self.w_lexical = 0.25
        self.w_vector = 0.35
        self.w_recency = 0.20
        self.w_confidence = 0.20

        # Gate thresholds
        self.memory_only_threshold = 0.72
        self.hybrid_threshold = 0.38

    def decide(
        self,
        *,
        query: str,
        memory_rows: List[Dict[str, Any]],
        vector_ranked: Optional[List[Tuple[int, float]]] = None,
        now_iso: Optional[str] = None,
    ) -> ArbitrationResult:
        now_iso = now_iso or _utc_now_iso()

        lexical = self._score_lexical(query=query, memory_rows=memory_rows)
        vector = self._score_vector(vector_ranked=vector_ranked)
        recency = self._score_recency(memory_rows=memory_rows, now_iso=now_iso)
        conf = self._score_confidence(memory_rows=memory_rows)

        fused = (
            lexical * self.w_lexical
            + vector * self.w_vector
            + recency * self.w_recency
            + conf * self.w_confidence
        )

        if fused >= self.memory_only_threshold:
            mode = "memory_only"
            rationale = "High memory evidence quality; answer from memory context."
        elif fused >= self.hybrid_threshold:
            mode = "hybrid"
            rationale = "Moderate memory evidence; combine memory context with LLM synthesis."
        else:
            mode = "llm_only"
            rationale = "Low memory evidence; rely on LLM general reasoning."

        return ArbitrationResult(
            mode=mode,
            confidence=round(fused, 4),
            scores={
                "lexical": round(lexical, 4),
                "vector": round(vector, 4),
                "recency": round(recency, 4),
                "confidence": round(conf, 4),
                "fused": round(fused, 4),
            },
            rationale=rationale,
        )

    def _score_lexical(self, *, query: str, memory_rows: List[Dict[str, Any]]) -> float:
        q = (query or "").strip().lower()
        if not q:
            return 0.0
        if not memory_rows:
            return 0.0

        terms = [t for t in q.split() if t]
        if not terms:
            return 0.0

        hits = 0
        for row in memory_rows:
            txt = str(row.get("content", "")).lower()
            if any(t in txt for t in terms):
                hits += 1

        ratio = hits / max(1, len(memory_rows))
        return min(1.0, max(0.0, ratio))

    def _score_vector(self, *, vector_ranked: Optional[List[Tuple[int, float]]]) -> float:
        if not vector_ranked:
            return 0.0
        # Expect score roughly similarity-like. Clamp robustly.
        best = _safe_float(vector_ranked[0][1], 0.0)
        return min(1.0, max(0.0, best))

    def _score_recency(self, *, memory_rows: List[Dict[str, Any]], now_iso: str) -> float:
        if not memory_rows:
            return 0.0

        now = self._parse_iso(now_iso)
        if now is None:
            return 0.0

        # Use freshest record among rows.
        freshest_hours = None
        for r in memory_rows:
            created_at = r.get("created_at")
            dt = self._parse_iso(str(created_at)) if created_at else None
            if dt is None:
                continue
            age_hours = max(0.0, (now - dt).total_seconds() / 3600.0)
            if freshest_hours is None or age_hours < freshest_hours:
                freshest_hours = age_hours

        if freshest_hours is None:
            return 0.0

        # Piecewise freshness decay:
        # <= 6h -> near 1
        # 24h -> ~0.8
        # 7d -> ~0.4
        # 30d+ -> ~0.1
        if freshest_hours <= 6:
            return 1.0
        if freshest_hours <= 24:
            return 0.8
        if freshest_hours <= 24 * 7:
            return 0.4
        if freshest_hours <= 24 * 30:
            return 0.2
        return 0.1

    def _score_confidence(self, *, memory_rows: List[Dict[str, Any]]) -> float:
        if not memory_rows:
            return 0.0
        vals: List[float] = []
        for r in memory_rows:
            vals.append(min(1.0, max(0.0, _safe_float(r.get("confidence", 0.0), 0.0))))
        return sum(vals) / max(1, len(vals))

    def _parse_iso(self, v: str):
        try:
            s = v.strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s)
        except Exception:
            return None


reasoning_arbitrator = ReasoningArbitrator()
