import logging

import httpx
from pydantic import BaseModel, ConfigDict
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import settings

logger = logging.getLogger(__name__)

_http_client: httpx.Client | None = None
_qdrant_client: QdrantClient | None = None


class EmbeddingServiceError(RuntimeError):
    """The dedicated embedding service could not return a valid vector."""


class _EmbeddingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dimension: int
    embeddings: list[list[float]]


def _get_http_client() -> httpx.Client:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.Client(
            base_url=settings.embedding_service_url.rstrip("/"),
            timeout=settings.embedding_service_timeout,
        )
    return _http_client


def get_text_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate vectors through the shared embedding service."""
    if not texts or any(not text.strip() for text in texts):
        raise ValueError("texts must contain at least one non-empty string")

    try:
        response = _get_http_client().post("/v1/embeddings", json={"texts": texts})
        response.raise_for_status()
        payload = _EmbeddingResponse.model_validate(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        raise EmbeddingServiceError("embedding service request failed") from exc

    if payload.dimension != settings.embedding_dimension:
        raise EmbeddingServiceError(
            f"embedding dimension mismatch: {payload.dimension} != {settings.embedding_dimension}"
        )
    if len(payload.embeddings) != len(texts):
        raise EmbeddingServiceError("embedding service returned an unexpected vector count")
    if any(len(vector) != settings.embedding_dimension for vector in payload.embeddings):
        raise EmbeddingServiceError("embedding service returned an invalid vector dimension")
    return payload.embeddings


def get_text_embedding(text: str) -> list[float]:
    return get_text_embeddings([text])[0]


def _get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(host=settings.qdrant_host, port=6333)
    return _qdrant_client


def index_news_to_qdrant(
    news_id: int,
    title: str,
    text: str,
    summary: str | None,
    published_at: int,
) -> None:
    """Ensure news_feed collection exists and upsert the news item embedding to Qdrant."""
    client = _get_qdrant_client()
    collection_name = "news_feed"

    try:
        # Create collection if it doesn't exist
        if not client.collection_exists(collection_name):
            logger.info("Creating news_feed collection in Qdrant...")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=settings.embedding_dimension,
                    distance=Distance.COSINE,
                ),
            )

        # Generate embedding for the news content
        content_to_embed = f"{title}\n{text}".strip()
        if not content_to_embed:
            logger.warning("Empty content for news_id=%d, skipping indexing", news_id)
            return

        vector = get_text_embedding(content_to_embed)

        # Upsert point to Qdrant
        client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=news_id,
                    vector=vector,
                    payload={
                        "title": title,
                        "text": text,
                        "summary": summary,
                        "published_at": published_at,
                    },
                )
            ],
        )
        logger.info("Successfully indexed news_id=%d in Qdrant", news_id)

    except Exception as e:
        logger.error("Failed to index news_id=%d to Qdrant: %s", news_id, e)
        raise
