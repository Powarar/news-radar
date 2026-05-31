"""
Summarization via Groq API (llama-3.1-8b-instant).
Returns None if Groq is unavailable — news is saved without summary.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_MAX_CHARS = 3000
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "llama-3.1-8b-instant"

_SYSTEM_PROMPT = """\
You are a news summarizer. Summarize the given news article in 2–3 sentences.
Be concise and factual. Reply in the same language as the article."""

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(timeout=20)
    return _client


def summarize(text: str) -> str | None:
    if not settings.groq_api_key:
        return None

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
                "temperature": 0.3,
                "max_tokens": 200,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        logger.warning("Groq summarize failed: %s", e)
        return None
