from __future__ import annotations

import os
import json
from typing import AsyncGenerator

import httpx


class LLMClient:
    def __init__(self) -> None:
        self.api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        self.model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
        self.base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.enabled = bool(self.api_key)

    async def chat(self, prompt: str) -> str:
        if not self.enabled:
            return "LLM disabled: OPENAI_API_KEY is missing."

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
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

    async def chat_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        Streams token chunks using OpenAI streaming mode.
        Yields token strings progressively.
        """

        if not self.enabled:
            yield "LLM disabled: OPENAI_API_KEY is missing."
            return

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a precise execution assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as res:
                if res.status_code >= 400:
                    yield f"LLM upstream error: {res.status_code}"
                    return

                async for line in res.aiter_lines():
                    if not line:
                        continue

                    if line.startswith("data: "):
                        data_str = line[len("data: ") :].strip()

                        if data_str == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0]["delta"]
                            token = delta.get("content")
                            if token:
                                yield token
                        except Exception:
                            continue


llm_client = LLMClient()
