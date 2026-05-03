"""
Topic classification via HuggingFace zero-shot (facebook/bart-large-mnli).
Returns topic → confidence score dict.
"""

import asyncio
import logging

import aiohttp

from app.core.config import settings

logger = logging.getLogger(__name__)

# bart-large-mnli tokenizer limit ~1024 tokens; ~4 chars/token is a safe proxy
_MAX_CHARS = 3000

TOPICS = [
    "politics",
    "military",
    "technology",
    "health",
    "science",
    "business",
    "sports",
    "culture",
    "environment",
]

async def classify(text: str, retries: int = 3) -> dict[str, float]:
    payload = {
        "inputs": text[:_MAX_CHARS],
        "parameters": {"candidate_labels": TOPICS},
    }
    headers = {
        "Authorization": f"Bearer {settings.huggingface_api_token}",
        "Content-Type": "application/json",
    }

    last_exc: Exception | None = None
    async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as session:
        for attempt in range(retries):
            try:
                async with session.post(settings.hf_classifier_model_url, json=payload) as resp:
                    if resp.status == 503:
                        data = await resp.json()
                        wait = float(data.get("estimated_time", 20))
                        logger.warning("HF model loading, waiting %.1fs (attempt %d)", wait, attempt + 1)
                        await asyncio.sleep(min(wait, 60))
                        continue

                    resp.raise_for_status()
                    data = await resp.json()

            except aiohttp.ClientError as exc:
                last_exc = exc
                backoff = 2**attempt
                logger.warning("HF request failed (attempt %d): %s — retrying in %ds", attempt + 1, exc, backoff)
                await asyncio.sleep(backoff)
                continue

            if isinstance(data, list):
                return {item["label"]: item["score"] for item in data}
            return dict(zip(data["labels"], data["scores"]))

        raise RuntimeError(f"classify failed after {retries} attempts") from last_exc
