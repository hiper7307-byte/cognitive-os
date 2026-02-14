from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class FunctionCall(BaseModel):
    name: str = Field(min_length=1)
    arguments: Dict[str, Any] = Field(default_factory=dict)


class AgentStepResult(BaseModel):
    step_index: int
    thought: str = ""
    action: Literal["final", "tool", "reflect", "retry"] = "reflect"
    function_call: Optional[FunctionCall] = None
    final_text: Optional[str] = None
    confidence: float = 0.0
    notes: Dict[str, Any] = Field(default_factory=dict)


class AgentRunRequest(BaseModel):
    prompt: str = Field(min_length=1)
    max_iterations: int = Field(default=6, ge=1, le=20)
    allow_tools: bool = True
    tool_whitelist: Optional[List[str]] = None
    timeout_ms: int = Field(default=20_000, ge=1_000, le=120_000)


class AgentRunResponse(BaseModel):
    ok: bool
    answer: str
    steps: List[AgentStepResult] = Field(default_factory=list)
    tool_traces: List[Dict[str, Any]] = Field(default_factory=list)
    decision_trace: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
