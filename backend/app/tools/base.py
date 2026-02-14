from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Generic, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError


class ToolInput(BaseModel):
    pass


class ToolOutput(BaseModel):
    ok: bool = True
    data: Dict[str, Any] = {}
    error: Optional[str] = None


TIn = TypeVar("TIn", bound=ToolInput)


@dataclass
class ToolContext:
    user_id: str
    task_id: Optional[str] = None
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolExecutionError(RuntimeError):
    pass


class BaseTool(Generic[TIn]):
    name: str = ""
    description: str = ""
    input_model: Type[TIn] = ToolInput

    def validate_input(self, payload: Dict[str, Any]) -> TIn:
        try:
            return self.input_model.model_validate(payload)
        except ValidationError as exc:
            raise ToolExecutionError(f"Invalid input for tool '{self.name}': {exc}") from exc

    def run(self, ctx: ToolContext, args: TIn) -> ToolOutput:
        raise NotImplementedError("Tool must implement run()")
