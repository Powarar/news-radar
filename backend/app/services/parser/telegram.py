import random
import re

import httpx
from bs4 import BeautifulSoup

from app.core.text_utils import strip_emoji

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# Один клиент на весь процесс — соединение с t.me переиспользуется между задачами
_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(follow_redirects=True, timeout=15)
    return _client


def parse_channel(channel: str, limit: int = 20) -> list[dict]:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }

    try:
        r = _get_client().get(f"https://t.me/s/{channel}", headers=headers)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429 or e.response.status_code >= 500:
            raise ConnectionError(
                f"Temporary Telegram error for @{channel}: {e.response.status_code}"
            ) from e
        raise ValueError(f"Channel @{channel} not accessible: {e.response.status_code}")
    except httpx.RequestError as e:
        raise ConnectionError(f"Telegram request failed for @{channel}") from e

    soup = BeautifulSoup(r.text, "html.parser")
    messages = soup.find_all("div", class_="tgme_widget_message_wrap")

    results = []
    for msg in messages[-limit:]:
        text_el  = msg.find("div", class_="tgme_widget_message_text")
        time_el  = msg.find("time")
        link_el  = msg.find("a", class_="tgme_widget_message_date")
        photo_el = msg.find("a", class_="tgme_widget_message_photo_wrap")

        text = text_el.get_text(separator=" ", strip=True) if text_el else None
        url  = link_el.get("href") if link_el else None

        if not text or not url:
            continue

        text = strip_emoji(text)
        if not text:
            continue

        published_at = None
        if time_el and time_el.get("datetime"):
            published_at = time_el["datetime"]

        image_url = None
        if photo_el:
            style = photo_el.get("style", "")
            m = re.search(r"url\(['\"]?(https?://[^'\")\s]+)['\"]?\)", style)
            if m:
                image_url = m.group(1)

        results.append({
            "text": text,
            "url": url,
            "published_at": published_at,
            "image_url": image_url,
        })

    return results
