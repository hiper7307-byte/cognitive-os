from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class RetryPolicy:
    max_total_retries: int = 3
    max_retries_per_tool: int = 2
    backoff_base_ms: int = 150


@dataclass(frozen=True)
class AgentPolicy:
    max_iterations_default: int = 6
    max_iterations_cap: int = 20
    min_confidence_to_finalize: float = 0.45
    retry: RetryPolicy = RetryPolicy()


def clamp_iterations(value: int, policy: AgentPolicy) -> int:
    if value < 1:
        return 1
    if value > policy.max_iterations_cap:
        return policy.max_iterations_cap
    return value


class RetryState:
    def __init__(self) -> None:
        self.total_retries = 0
        self.per_tool: Dict[str, int] = {}

    def can_retry(self, tool_name: Optional[str], policy: AgentPolicy) -> bool:
        if self.total_retries >= policy.retry.max_total_retries:
            return False
        if not tool_name:
            return True
        used = self.per_tool.get(tool_name, 0)
        return used < policy.retry.max_retries_per_tool

    def mark_retry(self, tool_name: Optional[str]) -> None:
        self.total_retries += 1
        if tool_name:
            self.per_tool[tool_name] = self.per_tool.get(tool_name, 0) + 1
