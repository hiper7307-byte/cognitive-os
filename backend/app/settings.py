from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    llm_api_key: str | None
    llm_base_url: str
    llm_model: str


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    return v if v else None


def get_settings() -> Settings:
    return Settings(
        llm_api_key=_clean(os.getenv("LLM_API_KEY")),
        llm_base_url=_clean(os.getenv("LLM_BASE_URL")) or "https://api.openai.com/v1",
        llm_model=_clean(os.getenv("LLM_MODEL")) or "gpt-4o-mini",
    )
