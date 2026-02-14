from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.cognitive.identity_models import IdentityConfig
from app.cognitive.identity_store import IdentityAlignmentStore

_WORD_RE = re.compile(r"[a-zA-Z0-9']+")


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _WORD_RE.finditer(text or "")}


def _hit_ratio(terms: List[str], haystack: str) -> tuple[float, List[str]]:
    if not terms:
        return 0.0, []
    h = _tokens(haystack)
    matched: List[str] = []
    for t in terms:
        tk = _tokens(t)
        if tk and tk.issubset(h):
            matched.append(t)
    return (len(matched) / max(len(terms), 1)), matched


class IdentityAlignmentService:
    def __init__(self, store: IdentityAlignmentStore, config: Optional[IdentityConfig] = None) -> None:
        self.store = store
        self.config = config or IdentityConfig()

    def upsert_profile(
        self,
        *,
        user_id: str,
        values: List[str],
        goals: List[str],
        constraints: List[str],
        risk_tolerance: float,
        metadata: Dict[str, str],
    ) -> Dict[str, Any]:
        return self.store.upsert_profile(
            user_id=user_id,
            values=self._normalize_list(values),
            goals=self._normalize_list(goals),
            constraints=self._normalize_list(constraints),
            risk_tolerance=float(risk_tolerance),
            metadata=metadata,
        )

    def get_profile(self, *, user_id: str) -> Dict[str, Any]:
        profile = self.store.get_profile(user_id=user_id)
        if profile:
            return profile
        return {
            "user_id": user_id,
            "values": [],
            "goals": [],
            "constraints": [],
            "risk_tolerance": 0.5,
            "metadata": {},
            "updated_at_epoch": 0,
        }

    def score_alignment(
        self,
        *,
        user_id: str,
        text: str,
        candidate_action: Optional[str] = None,
    ) -> Dict[str, Any]:
        profile = self.get_profile(user_id=user_id)
        basis = (text or "").strip()
        action = (candidate_action or "").strip()
        source = f"{basis}\n{action}".strip()

        values_ratio, values_hit = _hit_ratio(profile["values"], source)
        goals_ratio, goals_hit = _hit_ratio(profile["goals"], source)

        constraints_ratio, constraints_hit = _hit_ratio(profile["constraints"], source)
        constraints_component = 1.0 - constraints_ratio if profile["constraints"] else 1.0

        risk_user = float(profile.get("risk_tolerance", 0.5))
        risk_action = self._infer_risk(action or basis)
        risk_component = max(0.0, 1.0 - abs(risk_user - risk_action))

        w = self.config.weights
        raw = (
            (w.values_weight * values_ratio)
            + (w.goals_weight * goals_ratio)
            + (w.constraints_weight * constraints_component)
            + (w.risk_weight * risk_component)
        )

        score = min(self.config.max_score, max(self.config.min_score, raw))
        components = {
            "values": round(values_ratio, 6),
            "goals": round(goals_ratio, 6),
            "constraints": round(constraints_component, 6),
            "risk": round(risk_component, 6),
        }
        matched = {
            "values": values_hit,
            "goals": goals_hit,
            "constraints_triggered": constraints_hit,
        }
        trace = {
            "method": "weighted_keyword_alignment_v1",
            "source_used": "text+candidate_action" if action else "text",
        }

        self.store.log_alignment_event(
            user_id=user_id,
            text=basis,
            candidate_action=action if action else None,
            score=score,
            components=components,
            matched=matched,
            trace=trace,
        )

        return {
            "ok": True,
            "score": score,
            "components": components,
            "matched": matched,
            "trace": trace,
        }

    @staticmethod
    def _normalize_list(items: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for x in items or []:
            s = " ".join(str(x).split()).strip()
            if not s:
                continue
            low = s.lower()
            if low in seen:
                continue
            seen.add(low)
            out.append(s)
        return out

    @staticmethod
    def _infer_risk(text: str) -> float:
        t = (text or "").lower()
        high_markers = ["all in", "leverage", "bet", "gamble", "extreme", "aggressive", "unsafe"]
        low_markers = ["safe", "conservative", "low risk", "steady", "gradual", "cautious"]

        high = sum(1 for m in high_markers if m in t)
        low = sum(1 for m in low_markers if m in t)

        if high == 0 and low == 0:
            return 0.5
        score = 0.5 + (0.15 * high) - (0.15 * low)
        return min(1.0, max(0.0, score))
