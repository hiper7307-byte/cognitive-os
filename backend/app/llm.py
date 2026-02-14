import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def llm_intent(text: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Extract task type and entities."},
            {"role": "user", "content": text}
        ]
    )

    return {
        "task_type": "general",
        "confidence": 0.95,
        "entities": {"raw": text}
    }
