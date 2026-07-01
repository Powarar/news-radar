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

Assign a confidence score (0.0–1.0) to EVERY topic that is even weakly related to the article. The scores drive a recommendation engine, so secondary and tertiary topics matter as much as the primary one — dropping them makes recommendations worse.

Topic list:
politics, military, technology, health, science, business, sports, culture, environment

Scoring guide:
- 0.9–1.0  : the article is primarily about this topic
- 0.5–0.8  : the topic is a major secondary theme
- 0.15–0.4 : the topic is mentioned or tangentially relevant (STILL INCLUDE IT)
- < 0.15   : omit (truly unrelated only)

Rules:
- Include every topic scoring >= 0.15. Do NOT drop weak-but-real signals.
- A single article usually has 2–4 relevant topics. Rarely just one.
- If genuinely no topic applies, return {}.
- Output format: {"topic": score, ...}

Examples:
Input: "Apple releases new iPhone model with AI features"
Output: {"technology": 0.95, "business": 0.7, "science": 0.2}

Input: "President signs new trade agreement with implications for tech sector"
Output: {"politics": 0.9, "business": 0.6, "technology": 0.25}

Input: "New study links air pollution to respiratory disease"
Output: {"health": 0.9, "environment": 0.6, "science": 0.4}"""

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
                "max_tokens": 150,
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()

        # extract first {...} block even if model added surrounding text
        match = re.search(r"\{[^{}]*\}", content)
        if not match:
            logger.warning(
                "Groq classify: no JSON in response | raw=%r | text=%.120s",
                content[:300], text[:120],
            )
            return classify_keywords(text)

        try:
            result = json.loads(match.group())
        except json.JSONDecodeError as e:
            logger.warning(
                "Groq classify: invalid JSON %s | raw=%r | text=%.120s",
                e, content[:300], text[:120],
            )
            return classify_keywords(text)

        filtered: dict[str, float] = {}
        for k, v in result.items():
            if k not in TOPICS:
                continue
            try:
                score = float(v)
            except (TypeError, ValueError):
                continue
            if score >= 0.15:
                filtered[k] = score

        if not filtered:
            logger.warning(
                "Groq classify: 0 valid topics, keyword fallback | raw=%r | text=%.120s",
                content[:300], text[:120],
            )
            return classify_keywords(text)
        return filtered

    except Exception as e:
        logger.warning(
            "Groq classify failed: %s | raw=%r | text=%.120s",
            e, locals().get("content", "")[:300], text[:120],
        )
        return classify_keywords(text)
