"""
Summarization via Groq API (llama-3.1-8b-instant).
Returns (summary, status) where status is one of:
  - "ok"      — summary generated
  - "skipped" — no API key configured
  - "failed"  — API error / network error / malformed response
"""

import logging
import re
import time

import httpx

from app.core.config import settings
from app.core.text_utils import strip_emoji

logger = logging.getLogger(__name__)

_MAX_CHARS = 3000
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "llama-3.1-8b-instant"
_MAX_RETRIES = 3          # 1 initial attempt + 3 retries = 4 total
_BACKOFF_BASE = 2.0       # seconds: 1→2→4 between retries
_MIN_RETRY_AFTER = 1.0    # fallback sleep for 429 when Retry-After header is missing

_SYSTEM_PROMPT = """\
You are a news summarizer. Summarize the given news article in ONE short sentence (max ~15 words).
Be concise and factual. Reply in the same language as the article.
Output plain text only — absolutely no emoji, no symbols, no markdown."""

_SENTENCE_BOUNDARY = re.compile(r'[.!?]\s+(?=[А-ЯA-ZЁ])')
# Only matched when preceded by whitespace/start-of-string, so we don't mistake
# "т.е." or "Dr." for a sentence boundary.
_ABBREV = re.compile(
    r'(?:^|\s)(?:'
    r'т\.е|т\.к|т\.д|т\.п|и т\.д|и т\.п|'
    r'г|ул|д|стр|в|см|напр|'
    r'Mr|Mrs|Ms|Dr|Prof|etc|i\.e|e\.g|vs|St|Ave|Blvd'
    r')\.?(?=\s)',
    flags=re.UNICODE | re.IGNORECASE,
)


def _soft_truncate(text: str, max_chars: int) -> str:
    """Truncate text at the last sentence boundary before max_chars.
    Fallback: last word boundary. Avoids cutting mid-word."""
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]

    boundaries = list(_SENTENCE_BOUNDARY.finditer(truncated))
    if boundaries:
        end = boundaries[-1].start() + 2  # after ". "
        candidate = truncated[:end].strip()
        if candidate:
            return candidate

    last_space = truncated.rfind(" ")
    if last_space > 80:  # avoid cutting too short
        return truncated[:last_space].strip()

    return truncated


def _first_sentence(text: str) -> str:
    """Extract the first sentence, respecting common abbreviations.
    Splits on .!? only when followed by space + capital letter (or digit)."""
    parts = re.split(r'(?<=[.!?])\s+(?=[А-ЯA-ZЁ])', text, maxsplit=1)
    first = parts[0].strip()

    if _ABBREV.search(first):
        # The "sentence" ends in an abbreviation, not a real boundary — the
        # model's reply was just short, return it as-is.
        return text.strip()

    return first if first else text.strip()


def _parse_retry_after(resp: httpx.Response) -> float:
    """Extract retry delay from Groq 429 response or Retry-After header."""
    try:
        body = resp.json()
        retry = body.get("error", {}).get("retry_after_seconds")
        if retry is not None:
            return float(retry)
    except (ValueError, KeyError, TypeError, AttributeError):
        pass

    header = resp.headers.get("retry-after", "")
    if header:
        try:
            return float(header)
        except ValueError:
            pass

    return _MIN_RETRY_AFTER


def summarize(text: str, news_id: int | None = None) -> tuple[str | None, str]:
    """Return (summary, status). status ∈ {"ok", "skipped", "failed"}.

    Implements retry with exponential backoff for network errors and HTTP 429.
    Soft-truncates input to _MAX_CHARS at sentence boundary.
    """
    if not settings.groq_api_key:
        return None, "skipped"

    truncated = _soft_truncate(text, _MAX_CHARS)
    label = f"news_id={news_id}" if news_id is not None else "caller=unknown"

    for attempt in range(_MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=settings.groq_api_timeout) as client:
                resp = client.post(
                    _GROQ_URL,
                    headers={
                        "Authorization": f"Bearer {settings.groq_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": _MODEL,
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": truncated},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 200,
                    },
                )

            if resp.status_code == 429:
                retry_after = _parse_retry_after(resp)
                if attempt < _MAX_RETRIES:
                    logger.info(
                        "Groq rate-limited (attempt %d/%d), sleeping %.1fs [%s]",
                        attempt + 1, _MAX_RETRIES + 1, retry_after, label,
                    )
                    time.sleep(retry_after)
                    continue
                logger.warning(
                    "Groq summarize: rate-limited after %d retries [%s]",
                    _MAX_RETRIES + 1, label,
                )
                return None, "failed"

            if resp.status_code != 200:
                logger.warning(
                    "Groq summarize failed: HTTP %d | body=%.300s [%s]",
                    resp.status_code, resp.text[:300], label,
                )
                return None, "failed"

            data = resp.json()
            summary = data["choices"][0]["message"]["content"].strip()
            if not summary:
                logger.warning("Groq summarize: empty content | raw=%r [%s]", data, label)
                return None, "failed"

            summary = strip_emoji(summary)
            summary = _first_sentence(summary)

            if not summary:
                logger.warning("Groq summarize: empty after cleaning [%s]", label)
                return None, "failed"

            logger.info(
                "Groq summarize ok: %d chars, input was %d chars [%s]",
                len(summary), len(truncated), label,
            )
            return summary, "ok"

        except httpx.HTTPError as e:
            if attempt < _MAX_RETRIES:
                wait = _BACKOFF_BASE ** attempt
                logger.info(
                    "Groq summarize retry %d/%d after: %s (sleeping %.1fs) [%s]",
                    attempt + 1, _MAX_RETRIES, e, wait, label,
                )
                time.sleep(wait)
                continue
            logger.warning(
                "Groq summarize network error after %d retries: %s [%s]",
                _MAX_RETRIES + 1, e, label,
            )
            return None, "failed"

        except (KeyError, IndexError, ValueError) as e:
            logger.warning("Groq summarize malformed response: %s [%s]", e, label)
            return None, "failed"
        except Exception as e:
            logger.warning("Groq summarize unexpected error: %s [%s]", e, label)
            return None, "failed"

    logger.error("Groq summarize: exhausted retries [%s]", label)
    return None, "failed"
