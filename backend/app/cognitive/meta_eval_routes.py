from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Header, HTTPException, Query

from .runtime import meta_eval_service

router = APIRouter(prefix="/cognitive/meta-eval", tags=["cognitive-meta-eval"])


def _require_user_id(x_user_id: str | None) -> str:
    user_id = (x_user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    return user_id


@router.get("/recent")
def recent_meta_eval_events(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    limit: int = Query(default=20, ge=1, le=200),
) -> Dict[str, Any]:
    user_id = _require_user_id(x_user_id)
    rows = meta_eval_service.recent_events(user_id=user_id, limit=limit)
    return {
        "ok": True,
        "count": len(rows),
        "results": rows,
    }


@router.get("/stats")
def meta_eval_stats(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    window: int = Query(default=200, ge=10, le=5000),
) -> Dict[str, Any]:
    user_id = _require_user_id(x_user_id)

    rows: List[Dict[str, Any]] = meta_eval_service.recent_events(user_id=user_id, limit=window)

    total = len(rows)
    if total == 0:
        return {
            "ok": True,
            "window": window,
            "total": 0,
            "by_endpoint": {},
            "by_mode": {},
            "had_exception_count": 0,
            "avg_score": 0.0,
            "avg_confidence": 0.0,
        }

    by_endpoint: Dict[str, int] = {}
    by_mode: Dict[str, int] = {}
    had_exception_count = 0
    score_sum = 0.0
    conf_sum = 0.0

    for r in rows:
        endpoint = str(r.get("endpoint", "unknown"))
        by_endpoint[endpoint] = by_endpoint.get(endpoint, 0) + 1

        decision = r.get("decision_json", {}) or {}
        mode = str(decision.get("mode", "unknown"))
        by_mode[mode] = by_mode.get(mode, 0) + 1

        if bool(decision.get("had_exception", False)):
            had_exception_count += 1

        try:
            score_sum += float(decision.get("score", 0.0))
        except Exception:
            pass

        try:
            conf_sum += float(decision.get("confidence", 0.0))
        except Exception:
            pass

    return {
        "ok": True,
        "window": window,
        "total": total,
        "by_endpoint": by_endpoint,
        "by_mode": by_mode,
        "had_exception_count": had_exception_count,
        "avg_score": round(score_sum / total, 4),
        "avg_confidence": round(conf_sum / total, 4),
    }
