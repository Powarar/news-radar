"""
Topic classification via Groq API (llama-3.1-8b-instant).
Falls back to keyword classifier if Groq is unavailable.
"""

import json
import logging

import httpx

from app.core.config import settings
from app.services.ai.keyword_classifier import classify_keywords

logger = logging.getLogger(__name__)

_MAX_CHARS = 2000
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "llama-3.1-8b-instant"

TOPICS = [
    "politics", "military", "technology", "health",
    "science", "business", "sports", "culture", "environment",
]

_SYSTEM_PROMPT = """\
You are a news classifier. Given a news text, return a JSON object with confidence scores (0.0–1.0) for each topic.
Only include topics with score > 0.2. Reply with ONLY valid JSON, no explanation.

Topics: politics, military, technology, health, science, business, sports, culture, environment

Example output: {"technology": 0.95, "business": 0.6}"""

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(timeout=20)
    return _client


def classify(text: str) -> dict[str, float]:
    if not settings.groq_api_key:
        return classify_keywords(text)

    try:
        resp = _get_client().post(
            _GROQ_URL,
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": _MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text[:_MAX_CHARS]},
                ],
                "temperature": 0,
                "max_tokens": 100,
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()

        # убираем markdown ```json ... ``` если модель добавила
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        result = json.loads(content)
        return {k: float(v) for k, v in result.items() if k in TOPICS}

    except Exception as e:
        logger.warning("Groq classify failed: %s — using keyword fallback", e)
        return classify_keywords(text)
