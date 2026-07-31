import httpx
import pytest

from app.services.parser import web


class FakeClient:
    is_closed = False

    def __init__(self, responses: list[httpx.Response]):
        self.responses = iter(responses)
        self.requested_urls: list[str] = []

    def get(self, url: str, **_kwargs) -> httpx.Response:
        self.requested_urls.append(url)
        return next(self.responses)


def _response(status_code: int, url: str, **headers: str) -> httpx.Response:
    return httpx.Response(
        status_code,
        headers=headers,
        request=httpx.Request("GET", url),
    )


def test_fetch_validates_redirect_destination_before_following(monkeypatch):
    client = FakeClient([
        _response(302, "https://1.1.1.1/feed", location="http://127.0.0.1/admin"),
    ])
    monkeypatch.setattr(web, "_client", client)

    with pytest.raises(ValueError, match="not allowed"):
        web._fetch_public_response("https://1.1.1.1/feed")

    assert client.requested_urls == ["https://1.1.1.1/feed"]


def test_fetch_accepts_relative_redirect_after_validation(monkeypatch):
    client = FakeClient([
        _response(302, "https://example.com/feed", location="/rss.xml"),
        _response(200, "https://example.com/rss.xml"),
    ])
    validated: list[str] = []
    monkeypatch.setattr(web, "_client", client)
    monkeypatch.setattr(
        web,
        "validate_public_http_url",
        lambda url, **_kwargs: validated.append(url) or url,
    )

    response = web._fetch_public_response("https://example.com/feed")

    assert response.status_code == 200
    assert validated == [
        "https://example.com/feed",
        "https://example.com/rss.xml",
    ]


@pytest.mark.parametrize("raw_url", ["javascript:alert(1)", "file:///etc/passwd", ""])
def test_article_links_reject_non_http_schemes(raw_url):
    assert web._normalise_article_url("https://example.com/feed", raw_url) is None


def test_article_links_resolve_relative_paths():
    assert (
        web._normalise_article_url("https://example.com/news/feed", "../story/1")
        == "https://example.com/story/1"
    )
