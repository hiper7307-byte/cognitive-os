from __future__ import annotations

import os
from fastapi import APIRouter

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/env")
def debug_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    return {
        "env_path": env_path,
        "env_exists": os.path.exists(env_path),
        "llm_api_key_present": bool(os.getenv("LLM_API_KEY")),
        "llm_api_key_prefix": (os.getenv("LLM_API_KEY") or "")[:10],
        "llm_base_url": os.getenv("LLM_BASE_URL"),
        "llm_model": os.getenv("LLM_MODEL"),
    }
