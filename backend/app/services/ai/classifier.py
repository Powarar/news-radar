"""
Topic classification via HuggingFace zero-shot (facebook/bart-large-mnli).
Returns topic → confidence score dict.
"""

import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_MAX_CHARS = 3000

TOPICS = [
    "politics", "military", "technology", "health",
    "science", "business", "sports", "culture", "environment",
]

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            headers={
                "Authorization": f"Bearer {settings.huggingface_api_token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
    return _client


def classify(text: str, retries: int = 3) -> dict[str, float]:
    payload = {
        "inputs": text[:_MAX_CHARS],
        "parameters": {"candidate_labels": TOPICS},
    }
    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            resp = _get_client().post(settings.hf_classifier_model_url, json=payload)

            if resp.status_code == 503:
                data = resp.json()
                wait = min(float(data.get("estimated_time", 20)), 60)
                logger.warning("HF model loading, waiting %.1fs (attempt %d)", wait, attempt + 1)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()

        except httpx.HTTPError as exc:
            last_exc = exc
            backoff = 2 ** attempt
            logger.warning("HF request failed (attempt %d): %s — retrying in %ds", attempt + 1, exc, backoff)
            time.sleep(backoff)
            continue

        if isinstance(data, list):
            return {item["label"]: item["score"] for item in data}
        return dict(zip(data["labels"], data["scores"]))

    raise RuntimeError(f"classify failed after {retries} attempts") from last_exc
