from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from app.tools.base import ToolContext, ToolExecutionError, ToolOutput
from app.tools.registry import ToolRegistry


@dataclass
class ToolExecutionRecord:
    tool_name: str
    args: Dict[str, Any]
    ok: bool
    latency_ms: int
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute(
        self,
        *,
        user_id: str,
        tool_name: str,
        args: Dict[str, Any],
        task_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        whitelist: Optional[Set[str]] = None,
    ) -> ToolExecutionRecord:
        started = time.perf_counter()
        ctx = ToolContext(
            user_id=user_id,
            task_id=task_id,
            trace_id=trace_id,
            metadata=metadata or {},
        )

        try:
            if whitelist is not None and tool_name not in whitelist:
                raise ToolExecutionError(f"Tool '{tool_name}' is not allowed by whitelist")

            tool = self.registry.require(tool_name)
            parsed = tool.validate_input(args)
            out: ToolOutput = tool.run(ctx, parsed)
            latency = int((time.perf_counter() - started) * 1000)
            return ToolExecutionRecord(
                tool_name=tool_name,
                args=args,
                ok=out.ok,
                latency_ms=latency,
                output=out.data,
                error=out.error,
            )
        except KeyError as exc:
            latency = int((time.perf_counter() - started) * 1000)
            return ToolExecutionRecord(
                tool_name=tool_name,
                args=args,
                ok=False,
                latency_ms=latency,
                error=str(exc),
            )
        except ToolExecutionError as exc:
            latency = int((time.perf_counter() - started) * 1000)
            return ToolExecutionRecord(
                tool_name=tool_name,
                args=args,
                ok=False,
                latency_ms=latency,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            latency = int((time.perf_counter() - started) * 1000)
            return ToolExecutionRecord(
                tool_name=tool_name,
                args=args,
                ok=False,
                latency_ms=latency,
                error=f"Unhandled tool error: {exc}",
            )
