"""
Topic classification via Groq API (llama-3.1-8b-instant).
Falls back to keyword classifier if Groq is unavailable.
"""

import json
import logging
import re

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
You are a news topic classifier. Your response must be a single JSON object — nothing else. No explanation, no markdown, no code fences, no text before or after.

Assign confidence scores (0.0–1.0) only to relevant topics from this list:
politics, military, technology, health, science, business, sports, culture, environment

Rules:
- Omit topics with score <= 0.2
- If no topic applies, return {}
- Output format: {"topic": score, ...}

Examples:
Input: "Apple releases new iPhone model with AI features"
Output: {"technology": 0.95, "business": 0.6}

Input: "President signs new trade agreement"
Output: {"politics": 0.9, "business": 0.5}"""

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(timeout=20)
    return _client


def classify(text: str) -> dict[str, float]:
    if not text or not text.strip():
        return {}

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

        # extract first {...} block even if model added surrounding text
        match = re.search(r"\{[^{}]*\}", content)
        if not match:
            logger.warning("Groq classify: no JSON object found | raw: %.200s", content)
            return classify_keywords(text)

        result = json.loads(match.group())
        return {k: float(v) for k, v in result.items() if k in TOPICS}

    except Exception as e:
        logger.warning("Groq classify failed: %s | raw: %.200s — using keyword fallback", e, locals().get("content", ""))
        return classify_keywords(text)
