
import httpx
from bs4 import BeautifulSoup


async def parse_telegram_channel(channel: str, limit: int = 10) -> list[dict]:
    url = f"https://t.me/s/{channel}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, follow_redirects=True)

    soup = BeautifulSoup(r.text, "html.parser")
    messages = soup.find_all("div", class_="tgme_widget_message_wrap")

    results = []
    for msg in messages[-limit:]:
        text_el = msg.find("div", class_="tgme_widget_message_text")
        time_el = msg.find("time")
        link_el = msg.find("a", class_="tgme_widget_message_date")

        text = text_el.get_text(separator=" ", strip=True) if text_el else None
        time = time_el.get("datetime") if time_el else None
        link = link_el.get("href") if link_el else None

        if text:
            results.append({
                "source": channel,
                "time": time,
                "text": text,
                "link": link
            })

    return results


# Запуск
import asyncio


async def main():
    posts = await parse_telegram_channel("meduzalive", limit=3)
    for p in posts:
        print(f"[{p['time']}] {p['text']}")
        print(f"  → {p['link']}\n")

asyncio.run(main())