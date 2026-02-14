from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .meta_eval_store import MetaEvalStore


@dataclass(frozen=True)
class MetaEvalDecision:
    error_type: str
    severity: str
    self_accuracy_score: float
    hallucination_flag: bool
    rationale: str


class MetaEvalService:
    """
    Lightweight deterministic evaluator.
    You can later replace the heuristics with model-assisted scoring.
    """

    def __init__(self, store: MetaEvalStore) -> None:
        self.store = store

    def evaluate_response(
        self,
        *,
        used_memory: bool,
        memory_count: int,
        llm_enabled: bool,
        arbitration_mode: str,
        response_text: str,
        had_exception: bool,
    ) -> MetaEvalDecision:
        text = (response_text or "").strip().lower()

        if had_exception:
            return MetaEvalDecision(
                error_type="runtime_exception",
                severity="high",
                self_accuracy_score=0.15,
                hallucination_flag=False,
                rationale="Unhandled exception occurred.",
            )

        if not text:
            return MetaEvalDecision(
                error_type="empty_response",
                severity="medium",
                self_accuracy_score=0.30,
                hallucination_flag=False,
                rationale="Response body empty.",
            )

        # Basic hallucination heuristic:
        # If llm unavailable but text sounds like confident factual answer, flag.
        suspicious_claim = any(k in text for k in ["definitely", "certainly", "guaranteed", "always"])
        hallucination = (not llm_enabled and suspicious_claim)

        base = 0.72
        if used_memory and memory_count > 0:
            base += 0.12
        if arbitration_mode == "memory_only":
            base += 0.06
        if arbitration_mode == "llm_only":
            base -= 0.05
        if "llm disabled" in text:
            base -= 0.07
        if hallucination:
            base -= 0.35

        score = max(0.0, min(1.0, base))

        error_type = "none"
        severity = "low"
        rationale = "Normal response path."

        if hallucination:
            error_type = "hallucination_risk"
            severity = "high"
            rationale = "Potential unsupported certainty while LLM disabled."

        return MetaEvalDecision(
            error_type=error_type,
            severity=severity,
            self_accuracy_score=score,
            hallucination_flag=hallucination,
            rationale=rationale,
        )

    def persist_event(
        self,
        *,
        user_id: str,
        trace_id: str,
        endpoint: str,
        decision: MetaEvalDecision,
        task_id: Optional[str] = None,
        correction_of_event_id: Optional[int] = None,
        notes: Optional[Dict[str, Any]] = None,
    ) -> int:
        payload_notes = dict(notes or {})
        payload_notes["rationale"] = decision.rationale
        return self.store.write_event(
            user_id=user_id,
            trace_id=trace_id,
            task_id=task_id,
            endpoint=endpoint,
            error_type=decision.error_type,
            severity=decision.severity,
            self_accuracy_score=decision.self_accuracy_score,
            hallucination_flag=decision.hallucination_flag,
            correction_of_event_id=correction_of_event_id,
            notes=payload_notes,
        )
