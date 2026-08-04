# Замени самые верхние строчки файла на эти:
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from pydantic import BaseModel, ConfigDict
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, Range

from app.core.config import settings
from app.services.ai.embedding import get_text_embedding

logger = logging.getLogger(__name__)

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

_CHAT_MODELS_FALLBACK = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen/qwen3.6-27b",
]

_MAX_RETRIES = 2
_BACKOFF_BASE = 2.0

_CHAT_SYSTEM_PROMPT = """\
Ты — профессиональный AI-новостной аналитик и ассистент.
Твоя задача — ответить на вопрос пользователя ИЛИ сделать красивый дайджест,
СТРОГО используя предоставленный ниже контекст из свежих новостей.

Правила:
1. Отвечай только на русском языке.
2. Пиши фактологично, структурированно (используй списки и выделения), без эмодзи.
3. Не придумывай фактов, которых нет в контексте.
4. Если в контексте нет ответа на вопрос, честно ответь: "К сожалению, за указанный период новостей по этой теме не найдено."
"""

_client: httpx.Client | None = None
_qdrant_client: QdrantClient | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    answer: str
    sources_count: int
    status: str


def _get_httpx_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(timeout=settings.groq_api_timeout)
    return _client


def _get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(host=settings.QDRANT_HOST, port=6333)
    return _qdrant_client


def fetch_news_context(
    query_text: str,
    days: int = 3,
    limit: int = 5,
    score_threshold: float = 0.35,
) -> tuple[str | None, int]:
    qdrant = _get_qdrant_client()
    query_vector = get_text_embedding(query_text)

    start_timestamp = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())

    try:
        results = qdrant.query_points(
            collection_name="news_feed",
            query=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="published_at",
                        range=Range(gte=start_timestamp),
                    )
                ]
            ),
            score_threshold=score_threshold,
            limit=limit,
        ).points
    except Exception as e:
        logger.error("Qdrant search error: %s", e)
        return None, 0

    if not results:
        return None, 0

    context_blocks = []
    for i, hit in enumerate(results, 1):
        payload = hit.payload or {}
        title = payload.get("title", "Без названия")
        summary = payload.get("summary", payload.get("text", ""))
        dt_str = datetime.fromtimestamp(
            payload.get("published_at", 0), tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M")

        context_blocks.append(
            f"Новость #{i} [{dt_str}]\nЗаголовок: {title}\nСуть: {summary}"
        )

    return "\n\n".join(context_blocks), len(results)


def answer_news_query(user_query: str, days: int = 3) -> ChatResponse:
    context, sources_count = fetch_news_context(user_query, days=days)

    if not context:
        return ChatResponse(
            answer=f"За последние {days} дня(ей) новостей по вашему запросу не найдено.",
            sources_count=0,
            status="no_context",
        )

    user_prompt = f"""КОНТЕКСТ СВЕЖИХ НОВОСТЕЙ:
---
{context}
---

ЗАПРОС ПОЛЬЗОВАТЕЛЯ: {user_query}

Дай развернутый и фактологичный ответ на запрос пользователя, опираясь исключительно на контекст новостей выше."""

    content = None

    for model_name in _CHAT_MODELS_FALLBACK:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                client = _get_httpx_client()
                resp = client.post(
                    _GROQ_URL,
                    headers={
                        "Authorization": f"Bearer {settings.groq_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": _CHAT_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.2,
                        "max_tokens": 1000,
                    },
                )

                if resp.status_code == 429:
                    time.sleep(_BACKOFF_BASE**attempt)
                    continue

                if resp.status_code != 200:
                    logger.warning(
                        "Chat RAG: Model %s HTTP %d", model_name, resp.status_code
                    )
                    break

                content = resp.json()["choices"][0]["message"]["content"].strip()
                break

            except httpx.HTTPError:
                if attempt < _MAX_RETRIES:
                    time.sleep(_BACKOFF_BASE**attempt)
                    continue
                break

        if content:
            break

    if not content:
        logger.error("Chat RAG: All Groq models failed for query '%s'", user_query)
        return ChatResponse(
            answer="Извините, сервис генерации ответов временно недоступен. Попробуйте позже.",
            sources_count=sources_count,
            status="failed",
        )

    return ChatResponse(
        answer=content,
        sources_count=sources_count,
        status="ok",
    )