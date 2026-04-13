"""
Website parser: RSS feeds first, fallback to HTML scraping.
"""
import feedparser
import httpx
from bs4 import BeautifulSoup


async def fetch_rss(url: str) -> list[dict]:
    feed = feedparser.parse(url)
    return [
        {
            "title": e.get("title"),
            "body": e.get("summary", ""),
            "url": e.get("link"),
            "published_at": e.get("published"),
        }
        for e in feed.entries
    ]


async def fetch_html(url: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    # TODO: site-specific extraction logic
    return []
