
import logging
import random
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.core.text_utils import strip_emoji
from app.core.url_security import validate_public_http_url

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(follow_redirects=False, timeout=15)
    return _client


def _fetch_public_response(url: str, headers: dict | None = None) -> httpx.Response:
    """Fetch a public URL and validate every redirect destination."""
    current_url = url
    for _ in range(5):
        validate_public_http_url(current_url, resolve_dns=True)
        response = _get_client().get(current_url, headers=headers)
        if not response.is_redirect:
            response.raise_for_status()
            return response

        location = response.headers.get("location")
        if not location:
            raise ConnectionError(f"Redirect without Location header: {current_url}")
        current_url = urljoin(current_url, location)

    raise ConnectionError(f"Too many redirects while fetching {url}")


def _normalise_article_url(base_url: str, raw_url: object) -> str | None:
    if not isinstance(raw_url, str) or not raw_url.strip():
        return None
    candidate = urljoin(base_url, raw_url.strip())
    try:
        return validate_public_http_url(candidate)
    except ValueError:
        return None


def fetch_rss(url: str) -> list[dict]:
    response = _fetch_public_response(
        url,
        headers={"User-Agent": random.choice(USER_AGENTS)},
    )
    feed = feedparser.parse(response.content)

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

        body = strip_emoji(body)
        if not body:
            continue

        published_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()

        title = getattr(entry, "title", None)
        if title:
            title = strip_emoji(title)

        article_url = _normalise_article_url(str(response.url), getattr(entry, "link", None))
        if not article_url:
            continue

        results.append({
            "title": title,
            "text": body,
            "url": article_url,
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
        r = _fetch_public_response(url, headers=headers)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429 or e.response.status_code >= 500:
            raise ConnectionError(
                f"Temporary HTTP error for {url}: {e.response.status_code}"
            ) from e
        logger.warning("fetch_html rejected %s: HTTP %d", url, e.response.status_code)
        return []
    except httpx.RequestError as e:
        raise ConnectionError(f"Website request failed for {url}") from e

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
        link = _normalise_article_url(str(r.url), link_el["href"] if link_el else None)

        if not text or not link:
            continue

        text = strip_emoji(text)
        if title:
            title = strip_emoji(title)

        results.append({
            "title": title,
            "text": text,
            "url": link,
            "published_at": None,
            "image_url": None,
        })

    return results


def fetch_site(url: str) -> list[dict]:
    validate_public_http_url(url, resolve_dns=True)
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
        except Exception as exc:  # noqa: BLE001 — try the next candidate on any parser failure
            logger.debug("RSS candidate failed for %s: %s", rss_url, exc)
            continue

    return fetch_html(url)
