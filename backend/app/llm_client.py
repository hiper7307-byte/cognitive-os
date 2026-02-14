from __future__ import annotations

import os
import httpx


class LLMClient:
    def __init__(self) -> None:
        self.model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
        self.base_url = (
            os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        ).rstrip("/")

    @property
    def api_key(self) -> str:
        return (os.getenv("OPENAI_API_KEY") or "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def chat(self, prompt: str) -> str:
        api_key = self.api_key

        if not api_key:
            return "LLM disabled: OPENAI_API_KEY is missing."

        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a precise execution assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(url, headers=headers, json=payload)

            if res.status_code >= 400:
                return f"LLM upstream error: {res.status_code} {res.text[:300]}"

            data = res.json()

        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            return "LLM upstream returned unexpected response format."


llm_client = LLMClient()
