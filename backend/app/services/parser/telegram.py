import random
import httpx
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


def parse_channel(channel: str, limit: int = 20) -> list[dict]:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }

    try:
        r = httpx.get(
            f"https://t.me/s/{channel}",
            headers=headers,
            follow_redirects=True,
            timeout=15,
        )
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise ValueError(f"Channel @{channel} not accessible: {e.response.status_code}")
    except httpx.RequestError:
        return []

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

        published_at = None
        if time_el and time_el.get("datetime"):
            published_at = time_el["datetime"]

        image_url = None
        if photo_el:
            style = photo_el.get("style", "")
            if "url(" in style:
                image_url = style.split("url('")[1].split("')")[0]

        results.append({
            "text": text,
            "url": url,
            "published_at": published_at,
            "image_url": image_url,
        })

    return results
