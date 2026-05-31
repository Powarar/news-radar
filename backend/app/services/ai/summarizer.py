"""
Multilingual summarization via HuggingFace (csebuetnlp/mT5_multilingual_XLSum).
Supports 45+ languages including Russian and English.
"""

import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_MAX_CHARS = 1024

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            headers={
                "Authorization": f"Bearer {settings.huggingface_api_token}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )
    return _client


def summarize(text: str, retries: int = 3) -> str:
    payload = {"inputs": text[:_MAX_CHARS]}
    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            resp = _get_client().post(settings.hf_summarizer_model_url, json=payload)

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

        return data[0]["summary_text"]

    raise RuntimeError(f"summarize failed after {retries} attempts") from last_exc
