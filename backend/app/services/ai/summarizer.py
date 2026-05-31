"""
Multilingual summarization via HuggingFace (csebuetnlp/mT5_multilingual_XLSum).
Supports 45+ languages including Russian and English.
"""

import logging

import aiohttp

from app.core.config import settings

logger = logging.getLogger(__name__)

_MAX_CHARS = 1024

_session: aiohttp.ClientSession | None = None


def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {settings.huggingface_api_token}",
                "Content-Type": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=60),
        )
    return _session


async def summarize(text: str, retries: int = 3) -> str:
    payload = {"inputs": text[:_MAX_CHARS]}
    session = _get_session()
    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            async with session.post(settings.hf_summarizer_model_url, json=payload) as resp:
                if resp.status == 503:
                    import asyncio
                    data = await resp.json()
                    wait = float(data.get("estimated_time", 20))
                    logger.warning("HF model loading, waiting %.1fs (attempt %d)", wait, attempt + 1)
                    await asyncio.sleep(min(wait, 60))
                    continue

                resp.raise_for_status()
                data = await resp.json()

        except aiohttp.ClientError as exc:
            import asyncio
            last_exc = exc
            backoff = 2 ** attempt
            logger.warning("HF request failed (attempt %d): %s — retrying in %ds", attempt + 1, exc, backoff)
            await asyncio.sleep(backoff)
            continue

        return data[0]["summary_text"]

    raise RuntimeError(f"summarize failed after {retries} attempts") from last_exc
