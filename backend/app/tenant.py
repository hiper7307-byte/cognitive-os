from __future__ import annotations

from fastapi import Header


DEFAULT_USER_ID = "local-dev"
USER_ID_HEADER = "X-User-Id"


def resolve_user_id(x_user_id: str | None = Header(default=None, alias=USER_ID_HEADER)) -> str:
    value = (x_user_id or "").strip()
    return value if value else DEFAULT_USER_ID
