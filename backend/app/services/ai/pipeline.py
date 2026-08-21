"""
Unified AI pipeline — classify topics AND summarize in one Groq call.
Falls back through free LLMs, and finally to keyword classifier if all fail;
summary is skipped on total fallback.
"""

import logging
import re
import time

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.config import settings
from app.core.text_utils import strip_emoji
from app.services.ai.keyword_classifier import classify_keywords

logger = logging.getLogger(__name__)

_MAX_CHARS = 1500
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

_MODELS_FALLBACK = [
    "llama-3.1-8b-instant",       # Основная: 14.4K RPD
    "allam-2-7b",                 # Резерв 1: 7K RPD
    "qwen/qwen3.6-27b",           # Резерв 2: 1K RPD
    "openai/gpt-oss-20b",         # Резерв 3: 1K RPD
]

_MAX_RETRIES = 2
_BACKOFF_BASE = 2.0
_MIN_RETRY_AFTER = 1.0
_MAX_RETRY_AFTER = 60.0

TOPICS = [
    "politics", "military", "technology", "health",
    "science", "business", "sports", "culture", "environment",
]

_SYSTEM_PROMPT = """\
Ты новостной аналитик. Для переданной статьи выполни ДВЕ задачи:

1. Классифицируй статью по темам и укажи уверенность (0.0–1.0).
2. Напиши краткое фактическое саммари одним предложением (не более 20 слов).

Саммари ВСЕГДА должно быть ТОЛЬКО НА РУССКОМ ЯЗЫКЕ, независимо от языка
исходной статьи. Переведи смысл на русский, если исходный текст на другом языке.
Не оставляй в саммари непереведённые фразы, кроме имён, названий и общепринятых
аббревиатур.

Ответь одним JSON-объектом и больше ничем. Без пояснений и markdown.
Формат: {"topics": {"topic": score, ...}, "summary": "одно предложение на русском"}

Список тем (ключи не переводить): politics, military, technology, health,
science, business, sports, culture, environment.

Оценки:
- 0.9–1.0: основная тема
- 0.5–0.8: важная дополнительная тема
- 0.15–0.4: косвенно связанная тема (обязательно включить)
- ниже 0.15: не включать
- Обычно указывай 2–4 темы. Верни {}, если ничего не подходит.

Саммари должно быть нейтральным и фактическим, без эмодзи и markdown.

Примеры:
Ввод: "Apple releases new iPhone with AI features"
Вывод: {"topics": {"technology": 0.95, "business": 0.7, "science": 0.2}, "summary": "Apple представила новую модель iPhone со встроенными функциями искусственного интеллекта."}

Ввод: "New study links air pollution to respiratory disease"
Вывод: {"topics": {"health": 0.9, "environment": 0.6, "science": 0.4}, "summary": "Исследование выявило связь загрязнения воздуха с повышенным риском респираторных заболеваний."}"""

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


class GroqNewsResponse(BaseModel):
    """Expected shape of the JSON object returned by Groq."""

    model_config = ConfigDict(extra="ignore")

    topics: dict[str, float]
    summary: str


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(timeout=settings.groq_api_timeout)
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
            return max(_MIN_RETRY_AFTER, min(float(retry), _MAX_RETRY_AFTER))
    except (ValueError, KeyError, TypeError, AttributeError):
        pass
    header = resp.headers.get("retry-after", "")
    if header:
        try:
            return max(_MIN_RETRY_AFTER, min(float(header), _MAX_RETRY_AFTER))
        except ValueError:
            pass
    return _MIN_RETRY_AFTER


def process(text: str, news_id: int | None = None) -> tuple[dict[str, float], str | None, str]:
    """Return (topics, summary, status). status ∈ {"ok", "skipped", "failed"}.

    One Groq call for both classify and summarize.
    Iterates through _MODELS_FALLBACK on rate limits (429) or errors.
    Falls back to keyword classifier if all Groq models are unavailable.
    """
    if not text or not text.strip():
        return {}, None, "skipped"

    if not settings.groq_api_key:
        return classify_keywords(text), None, "skipped"

    truncated = _soft_truncate(text, _MAX_CHARS)
    label = f"news_id={news_id}" if news_id is not None else "caller=unknown"
    content = None

    for model_name in _MODELS_FALLBACK:
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
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": truncated},
                        ],
                        "temperature": 0,
                        "max_tokens": 300,
                        "response_format": {"type": "json_object"},
                    },
                )

                if resp.status_code == 429:
                    retry_after = _parse_retry_after(resp)
                    if attempt < _MAX_RETRIES:
                        logger.info(
                            "Model %s rate-limited (attempt %d/%d), sleeping %.1fs [%s]",
                            model_name, attempt + 1, _MAX_RETRIES + 1, retry_after, label,
                        )
                        time.sleep(retry_after)
                        continue
                    logger.warning(
                        "Model %s rate-limited after retries, switching to fallback model... [%s]",
                        model_name, label,
                    )
                    break  

                if resp.status_code != 200:
                    logger.warning(
                        "Model %s HTTP %d: %.300s [%s]",
                        model_name, resp.status_code, resp.text[:300], label,
                    )
                    break

                content = resp.json()["choices"][0]["message"]["content"].strip()
                break 

            except httpx.HTTPError as e:
                if attempt < _MAX_RETRIES:
                    wait = _BACKOFF_BASE ** attempt
                    time.sleep(wait)
                    continue
                logger.warning("Network error with model %s: %s [%s]", model_name, e, label)
                break
            except (KeyError, IndexError, ValueError) as e:
                logger.warning("Malformed response from model %s: %s [%s]", model_name, e, label)
                break

        if content:
            break  

    if not content:
        
        logger.error("Pipeline: all Groq models failed or rate-limited [%s]", label)
        return classify_keywords(text), None, "failed"

    try:
        result = GroqNewsResponse.model_validate_json(content)
    except ValidationError as e:
        logger.warning(
            "Pipeline: response validation failed %s, keyword fallback | raw=%r [%s]",
            e, content[:300], label,
        )
        return classify_keywords(text), None, "failed"

    topics: dict[str, float] = {}
    for k, score in result.topics.items():
        if k not in TOPICS:
            continue
        if 0.15 <= score <= 1.0:
            topics[k] = score

    summary = None
    if result.summary.strip():
        summary = strip_emoji(result.summary.strip())
        summary = _first_sentence(summary)
        words = summary.split()
        if len(words) > 15:
            summary = " ".join(words[:15]).rstrip(" ,;:") + "…"
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
