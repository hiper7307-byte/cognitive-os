from __future__ import annotations

import json
from typing import Any, Dict, List

from app.tools.registry import ToolRegistry


def build_tool_descriptors(registry: ToolRegistry, whitelist: List[str] | None = None) -> List[Dict[str, Any]]:
    specs = registry.list_specs()
    if whitelist is not None:
        allow = set(whitelist)
        specs = [s for s in specs if s.name in allow]

    descriptors: List[Dict[str, Any]] = []
    for spec in specs:
        descriptors.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.input_schema,
                },
            }
        )
    return descriptors


def parse_function_call_payload(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return {"value": parsed}
        except json.JSONDecodeError:
            return {"raw": raw}
    return {"value": raw}
