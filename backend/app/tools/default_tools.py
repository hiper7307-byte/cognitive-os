from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import Field

from app.tools.base import BaseTool, ToolContext, ToolInput, ToolOutput


class EchoInput(ToolInput):
    text: str = Field(min_length=1, max_length=10_000)


class EchoTool(BaseTool[EchoInput]):
    name = "echo"
    description = "Returns the provided text."

    input_model = EchoInput

    def run(self, ctx: ToolContext, args: EchoInput) -> ToolOutput:
        return ToolOutput(ok=True, data={"text": args.text, "user_id": ctx.user_id})


class NowInput(ToolInput):
    tz: Optional[str] = Field(default="UTC")


class NowTool(BaseTool[NowInput]):
    name = "now"
    description = "Returns current server time in ISO format."

    input_model = NowInput

    def run(self, ctx: ToolContext, args: NowInput) -> ToolOutput:
        now = datetime.now(timezone.utc).isoformat()
        return ToolOutput(ok=True, data={"utc_now": now, "tz": args.tz or "UTC"})
