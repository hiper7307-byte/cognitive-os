from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ArbitrationDecision:
    action: str
    thought: str
    confidence: float
    function_call: Optional[Dict[str, Any]] = None
    final_text: Optional[str] = None
    reason: Optional[str] = None


class HybridArbiter:
    """
    Deterministic safety/quality arbitration layer over planner output.
    """

    def decide(
        self,
        *,
        planner_step: Dict[str, Any],
        allow_tools: bool,
        min_confidence_to_finalize: float,
        has_tool_result: bool,
    ) -> ArbitrationDecision:
        action = str(planner_step.get("action", "reflect")).strip().lower()
        thought = str(planner_step.get("thought", ""))
        confidence = float(planner_step.get("confidence", 0.0))
        function_call = planner_step.get("function_call")
        final_text = planner_step.get("final_text")

        if action not in {"tool", "reflect", "retry", "final"}:
            return ArbitrationDecision(
                action="reflect",
                thought="Invalid planner action normalized to reflect.",
                confidence=0.0,
                reason="invalid_action",
            )

        if action == "tool":
            if not allow_tools:
                return ArbitrationDecision(
                    action="reflect",
                    thought="Tools are disabled by request.",
                    confidence=max(confidence - 0.2, 0.0),
                    reason="tools_disabled",
                )
            if not isinstance(function_call, dict) or not str(function_call.get("name", "")).strip():
                return ArbitrationDecision(
                    action="reflect",
                    thought="Invalid function_call payload.",
                    confidence=max(confidence - 0.2, 0.0),
                    reason="invalid_function_call",
                )

        if action == "final":
            text = str(final_text or "").strip()
            if not text:
                return ArbitrationDecision(
                    action="reflect",
                    thought="Finalization blocked: empty final_text.",
                    confidence=max(confidence - 0.2, 0.0),
                    reason="empty_final_text",
                )
            if confidence < min_confidence_to_finalize and not has_tool_result:
                return ArbitrationDecision(
                    action="reflect",
                    thought="Finalization blocked: low confidence without evidence.",
                    confidence=confidence,
                    reason="low_confidence_finalize",
                )

        return ArbitrationDecision(
            action=action,
            thought=thought,
            confidence=confidence,
            function_call=function_call if action == "tool" else None,
            final_text=final_text if action == "final" else None,
        )
