from __future__ import annotations

import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from app.cognitive.dynamics_models import ContradictionCandidate, DynamicsConfig
from app.cognitive.dynamics_store import DynamicsStore


_WORD_RE = re.compile(r"[a-zA-Z0-9']+")


def _now_epoch() -> int:
    return int(time.time())


def _tokenize(text: str) -> set[str]:
    return {m.group(0).lower() for m in _WORD_RE.finditer(text or "") if m.group(0)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _extract_first_number(text: str) -> Optional[float]:
    m = re.search(r"[-+]?\d+(?:\.\d+)?", text or "")
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


class MemoryDynamicsService:
    def __init__(self, store: DynamicsStore, config: Optional[DynamicsConfig] = None) -> None:
        self.store = store
        self.config = config or DynamicsConfig()

    def reinforce_memory(self, *, user_id: str, memory_id: int, by: int = 1) -> Dict[str, Any]:
        delta = max(1, int(by))
        row = self.store.increment_reference(user_id=user_id, memory_id=memory_id, by=delta)
        return {"ok": True, "memory_id": memory_id, "reference_count": row.get("reference_count", 0)}

    def apply_decay_pass(self, *, user_id: str, limit: int = 500) -> Dict[str, Any]:
        rows = self.store.list_semantic_memories(user_id=user_id, limit=limit)
        changed = 0
        now = _now_epoch()
        min_c = self.config.decay.min_confidence
        max_c = self.config.decay.max_confidence
        half_life = max(self.config.decay.half_life_days, 1e-6)
        decay_lambda = math.log(2.0) / (half_life * 86400.0)

        for row in rows:
            memory_id = int(row["memory_id"])
            base_conf = float(row.get("confidence") or 0.5)
            base_conf = min(max(base_conf, min_c), max_c)
            updated_at = int(row.get("updated_at") or now)
            ref_count = int(row.get("reference_count") or 0)

            age_seconds = max(0, now - updated_at)
            decay_factor = math.exp(-decay_lambda * age_seconds)
            boosted = base_conf + (ref_count * self.config.reinforcement.boost_per_reference)
            decayed = boosted * decay_factor
            new_conf = min(max(decayed, min_c), max_c)

            if abs(new_conf - base_conf) >= 1e-4:
                self.store.update_memory_confidence(user_id=user_id, memory_id=memory_id, confidence=new_conf)
                changed += 1

        return {"ok": True, "scanned": len(rows), "changed": changed}

    def detect_contradictions(self, *, user_id: str, limit: int = 400) -> Dict[str, Any]:
        rows = self.store.list_semantic_memories(user_id=user_id, limit=limit)
        conflicts = 0
        candidates = self._find_candidates(rows)

        for c in candidates:
            cid = self.store.upsert_conflict(
                user_id=user_id,
                left_memory_id=c.left_memory_id,
                right_memory_id=c.right_memory_id,
                relation=self.config.contradiction_relation,
                reason=c.reason,
                score=c.score,
                metadata={"field_name": c.field_name},
            )
            if cid:
                conflicts += 1

        return {"ok": True, "scanned": len(rows), "conflicts_detected": conflicts}

    def link_correction(
        self,
        *,
        user_id: str,
        from_memory_id: int,
        to_memory_id: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        link_id = self.store.link_lineage(
            user_id=user_id,
            from_memory_id=from_memory_id,
            to_memory_id=to_memory_id,
            relation=self.config.correction_relation,
            metadata=metadata or {},
        )
        return {"ok": True, "lineage_id": link_id}

    def list_conflicts(self, *, user_id: str, status: Optional[str], limit: int) -> Dict[str, Any]:
        rows = self.store.list_conflicts(user_id=user_id, status=status, limit=limit)
        return {"ok": True, "count": len(rows), "results": rows}

    def resolve_conflict(self, *, user_id: str, conflict_id: int) -> Dict[str, Any]:
        ok = self.store.resolve_conflict(user_id=user_id, conflict_id=conflict_id)
        return {"ok": ok, "conflict_id": conflict_id}

    def _find_candidates(self, rows: List[Dict[str, Any]]) -> List[ContradictionCandidate]:
        out: List[ContradictionCandidate] = []
        n = len(rows)
        tokens_cache: List[set[str]] = [_tokenize(str(r.get("content", ""))) for r in rows]
        nums_cache: List[Optional[float]] = [_extract_first_number(str(r.get("content", ""))) for r in rows]

        for i in range(n):
            left = rows[i]
            left_id = int(left["memory_id"])
            left_tokens = tokens_cache[i]
            left_num = nums_cache[i]
            left_text = str(left.get("content", ""))

            for j in range(i + 1, n):
                right = rows[j]
                right_id = int(right["memory_id"])
                if left_id == right_id:
                    continue

                right_tokens = tokens_cache[j]
                right_num = nums_cache[j]
                right_text = str(right.get("content", ""))

                sim = _jaccard(left_tokens, right_tokens)
                if sim < self.config.contradiction.lexical_threshold:
                    continue

                neg_left = (" not " in f" {left_text.lower()} ") or ("never" in left_text.lower())
                neg_right = (" not " in f" {right_text.lower()} ") or ("never" in right_text.lower())
                numeric_conflict = False

                if left_num is not None and right_num is not None:
                    denom = max(abs(left_num), abs(right_num), 1.0)
                    rel = abs(left_num - right_num) / denom
                    numeric_conflict = rel > self.config.contradiction.numeric_relative_tolerance

                polarity_conflict = neg_left != neg_right
                if not polarity_conflict and not numeric_conflict:
                    continue

                reason = "polarity_conflict" if polarity_conflict else "numeric_conflict"
                score = min(0.99, max(0.5, sim))
                l_id, r_id = sorted((left_id, right_id))
                out.append(
                    ContradictionCandidate(
                        left_memory_id=l_id,
                        right_memory_id=r_id,
                        reason=reason,
                        score=score,
                    )
                )
        return out
