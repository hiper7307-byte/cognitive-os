from __future__ import annotations

import os


def _as_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


COGNITIVE_ROUTE_PRIMARY: bool = _as_bool("COGNITIVE_ROUTE_PRIMARY", default=True)
