from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field

from app.memory import memory_service
from app.tools.base import BaseTool, ToolContext, ToolInput, ToolOutput


class MemoryQueryInput(ToolInput):
    query: str = Field(min_length=1, max_length=2000)
    types: Optional[List[str]] = None
    limit: int = Field(default=10, ge=1, le=100)


class MemoryQueryTool(BaseTool[MemoryQueryInput]):
    name = "memory_query"
    description = "Searches governed memory for the current user."

    input_model = MemoryQueryInput

    def run(self, ctx: ToolContext, args: MemoryQueryInput) -> ToolOutput:
        rows = memory_service.retrieve(
            user_id=ctx.user_id,
            query=args.query.strip(),
            memory_types=args.types,
            limit=args.limit,
        )
        return ToolOutput(
            ok=True,
            data={
                "count": len(rows),
                "results": rows,
            },
        )


class MemoryRecentInput(ToolInput):
    memory_type: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=200)


class MemoryRecentTool(BaseTool[MemoryRecentInput]):
    name = "memory_recent"
    description = "Returns recent memories for the current user."

    input_model = MemoryRecentInput

    def run(self, ctx: ToolContext, args: MemoryRecentInput) -> ToolOutput:
        rows = memory_service.recent(
            user_id=ctx.user_id,
            memory_type=args.memory_type,
            limit=args.limit,
        )
        return ToolOutput(
            ok=True,
            data={
                "count": len(rows),
                "results": rows,
            },
        )


class MemoryWriteNoteInput(ToolInput):
    text: str = Field(min_length=1, max_length=8000)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    tags: Optional[List[str]] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class MemoryWriteNoteTool(BaseTool[MemoryWriteNoteInput]):
    name = "memory_write_note"
    description = "Writes a note memory item for the current user."

    input_model = MemoryWriteNoteInput

    def run(self, ctx: ToolContext, args: MemoryWriteNoteInput) -> ToolOutput:
        memory_id = memory_service.write_note(
            user_id=ctx.user_id,
            text=args.text.strip(),
            confidence=args.confidence,
            tags=args.tags or [],
            meta=args.meta or {},
        )
        return ToolOutput(
            ok=True,
            data={
                "memory_id": memory_id,
                "status": "created",
            },
        )
