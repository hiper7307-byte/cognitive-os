from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional, Tuple

from fastapi import Header, HTTPException

from .idempotency_store import idempotency_store


def request_hash(payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def get_idempotency_key(x_idempotency_key: Optional[str] = Header(default=None)) -> Optional[str]:
    if x_idempotency_key is None:
        return None
    key = x_idempotency_key.strip()
    if not key:
        return None
    return key


def replay_or_validate(
    *,
    user_id: str,
    endpoint: str,
    idem_key: Optional[str],
    payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not idem_key:
        return None

    h = request_hash(payload)
    existing = idempotency_store.get(user_id=user_id, endpoint=endpoint, idem_key=idem_key)
    if not existing:
        return None

    cached_response, _status, cached_hash = existing
    if cached_hash != h:
        raise HTTPException(status_code=409, detail="Idempotency key reuse with different payload")
    return cached_response


def persist_idempotent_response(
    *,
    user_id: str,
    endpoint: str,
    idem_key: Optional[str],
    payload: Dict[str, Any],
    response: Dict[str, Any],
    status_code: int = 200,
) -> None:
    if not idem_key:
        return
    h = request_hash(payload)
    idempotency_store.put(
        user_id=user_id,
        endpoint=endpoint,
        idem_key=idem_key,
        request_hash=h,
        response=response,
        status_code=status_code,
    )
