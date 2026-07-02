"""
Unified AI pipeline — classify topics AND summarize in one Groq call.
Falls back to keyword classifier if Groq is unavailable; summary is skipped on fallback.
"""

import json
import logging
import re
import time

import httpx

from app.core.config import settings
from app.core.text_utils import strip_emoji
from app.services.ai.keyword_classifier import classify_keywords

logger = logging.getLogger(__name__)

_MAX_CHARS = 1500
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "llama-3.1-8b-instant"
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0
_MIN_RETRY_AFTER = 1.0

TOPICS = [
    "politics", "military", "technology", "health",
    "science", "business", "sports", "culture", "environment",
]

_SYSTEM_PROMPT = """\
You are a news analyst. For the given article, do TWO things:

1. Classify into topics with confidence scores (0.0–1.0).
2. Write a ONE-sentence summary (max ~15 words) in the article's language.

Respond with a single JSON object — nothing else. No explanation, no markdown.
Format: {"topics": {"topic": score, ...}, "summary": "one sentence"}

Topic list: politics, military, technology, health, science, business, sports, culture, environment

Scoring:
- 0.9–1.0: primary topic
- 0.5–0.8: major secondary
- 0.15–0.4: tangentially relevant (STILL INCLUDE)
- < 0.15: omit
- Include 2–4 topics typically. Return {} if nothing matches.

Summary: factual, no emoji, no markdown, in the article's language.

Examples:
Input: "Apple releases new iPhone with AI features"
Output: {"topics": {"technology": 0.95, "business": 0.7, "science": 0.2}, "summary": "Apple announced a new iPhone model with integrated artificial intelligence features."}

Input: "New study links air pollution to respiratory disease"
Output: {"topics": {"health": 0.9, "environment": 0.6, "science": 0.4}, "summary": "A new study found that air pollution significantly increases the risk of respiratory diseases."}"""

_SENTENCE_BOUNDARY = re.compile(r'[.!?]\s+(?=[А-ЯA-ZЁ])')
_ABBREV = re.compile(
    r'(?:^|\s)(?:'
    r'т\.е|т\.к|т\.д|т\.п|и т\.д|и т\.п|'
    r'г|ул|д|стр|в|см|напр|'
    r'Mr|Mrs|Ms|Dr|Prof|etc|i\.e|e\.g|vs|St|Ave|Blvd'
    r')\.?(?=\s)',
    flags=re.UNICODE | re.IGNORECASE,
)

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(timeout=30)
    return _client


def _soft_truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    boundaries = list(_SENTENCE_BOUNDARY.finditer(truncated))
    if boundaries:
        end = boundaries[-1].start() + 2
        candidate = truncated[:end].strip()
        if candidate:
            return candidate
    last_space = truncated.rfind(" ")
    if last_space > 80:
        return truncated[:last_space].strip()
    return truncated


def _first_sentence(text: str) -> str:
    parts = re.split(r'(?<=[.!?])\s+(?=[А-ЯA-ZЁ])', text, maxsplit=1)
    first = parts[0].strip()
    if _ABBREV.search(first):
        return text.strip()
    return first if first else text.strip()


def _parse_retry_after(resp: httpx.Response) -> float:
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


def process(text: str, news_id: int | None = None) -> tuple[dict[str, float], str | None, str]:
    """Return (topics, summary, status). status ∈ {"ok", "skipped", "failed"}.

    One Groq call for both classify and summarize.
    Retries 429 with exponential backoff. Falls back to keyword classifier
    if Groq is unavailable; summary is None on fallback.
    """
    if not text or not text.strip():
        return {}, None, "skipped"

    if not settings.groq_api_key:
        return classify_keywords(text), None, "skipped"

    truncated = _soft_truncate(text, _MAX_CHARS)
    label = f"news_id={news_id}" if news_id is not None else "caller=unknown"

    for attempt in range(_MAX_RETRIES + 1):
        try:
            client = _get_client()
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
                    "temperature": 0,
                    "max_tokens": 300,
                },
            )

            if resp.status_code == 429:
                retry_after = _parse_retry_after(resp)
                if attempt < _MAX_RETRIES:
                    logger.info(
                        "Pipeline rate-limited (attempt %d/%d), sleeping %.1fs [%s]",
                        attempt + 1, _MAX_RETRIES + 1, retry_after, label,
                    )
                    time.sleep(retry_after)
                    continue
                logger.warning(
                    "Pipeline: rate-limited after %d retries [%s]",
                    _MAX_RETRIES + 1, label,
                )
                return classify_keywords(text), None, "failed"

            if resp.status_code != 200:
                logger.warning(
                    "Pipeline HTTP %d: %.300s [%s]",
                    resp.status_code, resp.text[:300], label,
                )
                return classify_keywords(text), None, "failed"

            content = resp.json()["choices"][0]["message"]["content"].strip()
            break  # success — exit retry loop

        except httpx.HTTPError as e:
            if attempt < _MAX_RETRIES:
                wait = _BACKOFF_BASE ** attempt
                logger.info(
                    "Pipeline retry %d/%d after: %s (%.1fs) [%s]",
                    attempt + 1, _MAX_RETRIES, e, wait, label,
                )
                time.sleep(wait)
                continue
            logger.warning(
                "Pipeline network error after %d retries: %s [%s]",
                _MAX_RETRIES + 1, e, label,
            )
            return classify_keywords(text), None, "failed"

        except (KeyError, IndexError, ValueError) as e:
            logger.warning("Pipeline malformed response: %s [%s]", e, label)
            return classify_keywords(text), None, "failed"
    else:
        # exhausted retries without success
        logger.error("Pipeline: exhausted retries [%s]", label)
        return classify_keywords(text), None, "failed"

    # Parse successful response
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        logger.warning(
            "Pipeline: no JSON in response, keyword fallback | raw=%r [%s]",
            content[:300], label,
        )
        return classify_keywords(text), None, "failed"

    try:
        result = json.loads(match.group())
    except json.JSONDecodeError as e:
        logger.warning(
            "Pipeline: invalid JSON %s, keyword fallback | raw=%r [%s]",
            e, content[:300], label,
        )
        return classify_keywords(text), None, "failed"

    topics_raw = result.get("topics", {})
    if not isinstance(topics_raw, dict):
        topics_raw = {}

    topics: dict[str, float] = {}
    for k, v in topics_raw.items():
        if k not in TOPICS:
            continue
        try:
            score = float(v)
        except (TypeError, ValueError):
            continue
        if score >= 0.15:
            topics[k] = score

    summary_raw = result.get("summary", "")
    if not isinstance(summary_raw, str):
        summary_raw = ""

    summary = None
    if summary_raw.strip():
        summary = strip_emoji(summary_raw.strip())
        summary = _first_sentence(summary)
        if not summary:
            summary = None

    if not topics:
        logger.warning(
            "Pipeline: 0 valid topics, keyword fallback | raw=%r [%s]",
            content[:300], label,
        )
        return classify_keywords(text), summary, "ok" if summary else "skipped"

    logger.info(
        "Pipeline ok: %d topics, summary %d chars [%s]",
        len(topics), len(summary) if summary else 0, label,
    )
    return topics, summary, "ok"
