from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.tools.base import BaseTool


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError("Tool name is required")
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def require(self, name: str) -> BaseTool:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool '{name}'")
        return tool

    def list_specs(self) -> List[ToolSpec]:
        specs: List[ToolSpec] = []
        for tool in self._tools.values():
            schema = tool.input_model.model_json_schema()
            specs.append(
                ToolSpec(
                    name=tool.name,
                    description=tool.description,
                    input_schema=schema,
                )
            )
        specs.sort(key=lambda x: x.name)
        return specs

    def clear(self) -> None:
        self._tools.clear()
