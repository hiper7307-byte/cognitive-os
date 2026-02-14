from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.llm_client import llm_client
from app.tools.function_calling import build_tool_descriptors, parse_function_call_payload
from app.tools.registry import ToolRegistry


SYSTEM_PROMPT = """You are the planning core of a Personal Cognitive OS.
Return strictly one JSON object per turn with fields:
- action: one of ["tool","reflect","retry","final"]
- thought: short internal rationale
- confidence: float 0..1
- function_call: optional object {name:string, arguments:object}
- final_text: required when action="final"

Rules:
1) Prefer tool usage when a concrete external/actionable check is needed.
2) If previous tool failed, either retry with corrected arguments or reflect.
3) Stop with action="final" when enough evidence exists.
4) Never output markdown, code fences, or prose outside JSON.
"""


class LLMPlannerAdapter:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def _build_messages(
        self,
        *,
        prompt: str,
        step: int,
        working_memory: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        wm_compact = json.dumps(working_memory[-8:], ensure_ascii=False)
        user_msg = {
            "role": "user",
            "content": (
                f"Step: {step}\n"
                f"User objective: {prompt}\n"
                f"Recent working memory (JSON): {wm_compact}\n"
                "Return next-step JSON only."
            ),
        }
        return [{"role": "system", "content": SYSTEM_PROMPT}, user_msg]

    def _fallback(self, prompt: str, working_memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        if working_memory:
            last = working_memory[-1]
            if last.get("type") == "tool_result" and last.get("ok"):
                return {
                    "action": "final",
                    "thought": "Tool result available; finalize.",
                    "final_text": f"Result: {last.get('output')}",
                    "confidence": 0.65,
                }
        return {
            "action": "final",
            "thought": "LLM unavailable; deterministic fallback.",
            "final_text": f"Received: {prompt}",
            "confidence": 0.4,
        }

    def next_step(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = str(payload.get("prompt", ""))
        step = int(payload.get("step", 0))
        allow_tools = bool(payload.get("allow_tools", True))
        working_memory = payload.get("working_memory", []) or []
        whitelist: Optional[List[str]] = payload.get("tool_whitelist")

        if not llm_client.enabled:
            return self._fallback(prompt, working_memory)

        messages = self._build_messages(prompt=prompt, step=step, working_memory=working_memory)

        tools = build_tool_descriptors(self.registry, whitelist=whitelist) if allow_tools else None

        try:
            raw = llm_client.chat(
                messages=messages,
                temperature=0.1,
                tools=tools,
                tool_choice="auto" if allow_tools else None,
                response_format={"type": "json_object"},
            )
        except Exception:
            return self._fallback(prompt, working_memory)

        # Expected flexible shapes from pluggable llm_client:
        # - {"content": "...json..."} or {"text": "...json..."} or direct dict
        # - optional tool call object in raw["tool_call"]
        tool_call = raw.get("tool_call") if isinstance(raw, dict) else None
        if tool_call and allow_tools:
            return {
                "action": "tool",
                "thought": "LLM selected function call.",
                "function_call": {
                    "name": tool_call.get("name", ""),
                    "arguments": parse_function_call_payload(tool_call.get("arguments")),
                },
                "confidence": float(tool_call.get("confidence", 0.6)),
            }

        payload_obj: Dict[str, Any]
        if isinstance(raw, dict) and "content" in raw and isinstance(raw["content"], str):
            try:
                payload_obj = json.loads(raw["content"])
            except Exception:
                return self._fallback(prompt, working_memory)
        elif isinstance(raw, dict) and "text" in raw and isinstance(raw["text"], str):
            try:
                payload_obj = json.loads(raw["text"])
            except Exception:
                return self._fallback(prompt, working_memory)
        elif isinstance(raw, dict):
            payload_obj = raw
        else:
            return self._fallback(prompt, working_memory)

        action = str(payload_obj.get("action", "reflect")).strip().lower()
        if action not in {"tool", "reflect", "retry", "final"}:
            action = "reflect"

        function_call = payload_obj.get("function_call")
        if action == "tool":
            if not allow_tools or not isinstance(function_call, dict):
                return {
                    "action": "reflect",
                    "thought": "Tool requested but unavailable/invalid.",
                    "confidence": float(payload_obj.get("confidence", 0.3)),
                }
            function_call = {
                "name": str(function_call.get("name", "")),
                "arguments": parse_function_call_payload(function_call.get("arguments")),
            }

        return {
            "action": action,
            "thought": str(payload_obj.get("thought", "")),
            "confidence": float(payload_obj.get("confidence", 0.0)),
            "function_call": function_call if action == "tool" else None,
            "final_text": payload_obj.get("final_text"),
        }
