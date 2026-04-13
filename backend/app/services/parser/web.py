
import random
import feedparser
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def fetch_rss(url: str) -> list[dict]:
    feed = feedparser.parse(url, agent=random.choice(USER_AGENTS))

    if feed.bozo and not feed.entries:
        return []

    results = []
    for entry in feed.entries:
        body = ""
        if hasattr(entry, "content"):
            body = entry.content[0].value
        elif hasattr(entry, "summary"):
            body = entry.summary

        if "<" in body:
            body = BeautifulSoup(body, "html.parser").get_text(separator=" ", strip=True)

        if not body:
            continue

        published_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()

        results.append({
            "title": getattr(entry, "title", None),
            "text": body,
            "url": getattr(entry, "link", None),
            "published_at": published_at,
            "image_url": None,
        })

    return results


def fetch_html(url: str) -> list[dict]:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }

    try:
        r = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
        r.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    articles = (
        soup.find_all("article") or
        soup.find_all("div", class_=lambda c: c and "news" in c.lower()) or
        soup.find_all("div", class_=lambda c: c and "article" in c.lower())
    )

    results = []
    for article in articles[:20]:
        title_el = article.find(["h1", "h2", "h3"])
        link_el  = article.find("a", href=True)
        text_el  = article.find("p")

        title = title_el.get_text(strip=True) if title_el else None
        text  = text_el.get_text(strip=True) if text_el else None
        link  = link_el["href"] if link_el else None

        if not text or not link:
            continue

        if link.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            link = f"{parsed.scheme}://{parsed.netloc}{link}"

        results.append({
            "title": title,
            "text": text,
            "url": link,
            "published_at": None,
            "image_url": None,
        })

    return results


def fetch_site(url: str) -> list[dict]:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    rss_candidates = [
        url,                    # может быть уже RSS URL
        f"{base}/rss",
        f"{base}/rss.xml",
        f"{base}/feed",
        f"{base}/feed.xml",
        f"{base}/index.xml",
    ]

    for rss_url in rss_candidates:
        try:
            items = fetch_rss(rss_url)
            if items:
                return items
        except Exception:
            continue

    return fetch_html(url)
