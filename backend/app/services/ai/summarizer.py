"""
Summarization via Groq API (llama-3.1-8b-instant).
Returns (summary, status) where status is one of:
  - "ok"      — summary generated
  - "skipped" — no API key configured
  - "failed"  — API error / network error / malformed response
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
Be concise and factual. Reply in the same language as the article.
Do not use any emoji or special symbols — plain text only."""

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(timeout=20)
    return _client


def summarize(text: str) -> tuple[str | None, str]:
    """Return (summary, status). status ∈ {"ok", "skipped", "failed"}."""
    if not settings.groq_api_key:
        return None, "skipped"

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
        if resp.status_code != 200:
            logger.warning(
                "Groq summarize failed: HTTP %d | body=%.300s",
                resp.status_code, resp.text[:300],
            )
            return None, "failed"

        data = resp.json()
        summary = data["choices"][0]["message"]["content"].strip()
        if not summary:
            logger.warning("Groq summarize: empty content | raw=%r", data)
            return None, "failed"
        return summary, "ok"

    except httpx.HTTPError as e:
        logger.warning("Groq summarize network error: %s", e)
        return None, "failed"
    except (KeyError, IndexError, ValueError) as e:
        logger.warning("Groq summarize malformed response: %s", e)
        return None, "failed"
    except Exception as e:
        logger.warning("Groq summarize unexpected error: %s", e)
        return None, "failed"
