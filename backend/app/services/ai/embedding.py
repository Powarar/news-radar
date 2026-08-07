import logging
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.core.config import settings

logger = logging.getLogger(__name__)

_model: TextEmbedding | None = None
_qdrant_client: QdrantClient | None = None


def get_text_embedding(text: str) -> list[float]:
    """Generate a vector embedding for the given text using fastembed."""
    global _model
    if _model is None:
        logger.info("Initializing fastembed TextEmbedding model...")
        _model = TextEmbedding(
            model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            cache_dir="/tmp/fastembed_cache"
        )
    
    embeddings = list(_model.embed([text]))
    return [float(x) for x in embeddings[0]]


def _get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(host=settings.qdrant_host, port=6333)
    return _qdrant_client


def index_news_to_qdrant(news_id: int, title: str, text: str, summary: str | None, published_at: int):
    """Ensure news_feed collection exists and upsert the news item embedding to Qdrant."""
    client = _get_qdrant_client()
    collection_name = "news_feed"

    try:
        # Create collection if it doesn't exist
        if not client.collection_exists(collection_name):
            logger.info("Creating news_feed collection in Qdrant...")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
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
