"""
Summarization via Groq API (llama-3.1-8b-instant).
Returns (summary, status) where status is one of:
  - "ok"      — summary generated
  - "skipped" — no API key configured
  - "failed"  — API error / network error / malformed response
"""

import logging
import re

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_MAX_CHARS = 3000
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "llama-3.1-8b-instant"

_SYSTEM_PROMPT = """\
You are a news summarizer. Summarize the given news article in ONE short sentence (max ~15 words).
Be concise and factual. Reply in the same language as the article.
Output plain text only — absolutely no emoji, no symbols, no markdown."""

# Диапазоны Unicode-эмодзи (включая модификаторы, флаги, символы и ZWJ-последовательности).
_EMOJI_RE = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"  # regional indicator symbols (флаги)
    "\U0001F300-\U0001F5FF"  # символы и пиктограммы
    "\U0001F600-\U0001F64F"  # смайлики
    "\U0001F680-\U0001F6FF"  # транспорт и карты
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"  # доп. символы
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"  # разные символы
    "\U00002700-\U000027BF"  # дингбаты
    "\U0001F018-\U0001F270"
    "\U0001F1E6-\U0001F1FF"
    "\u200d"                  # zero-width joiner
    "\ufe0f"                  # variation selector-16
    "]+",
    flags=re.UNICODE,
)

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

        # Гарантированно убираем эмодзи и лишние пробелы.
        summary = _EMOJI_RE.sub("", summary).strip()
        summary = re.sub(r"\s{2,}", " ", summary)

        # Оставляем только первое предложение — summary должен быть коротким.
        first = re.split(r"(?<=[.!?])\s+", summary, maxsplit=1)[0].strip()
        if first:
            summary = first

        if not summary:
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
