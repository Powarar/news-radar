import pytest

from app.core.url_security import validate_public_http_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8000",
        "http://10.0.0.1/internal",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "https://user:password@example.com",
    ],
)
def test_rejects_internal_or_unsafe_source_urls(url):
    with pytest.raises(ValueError):
        validate_public_http_url(url)


def test_accepts_public_http_url_without_dns_lookup():
    assert validate_public_http_url("https://example.com/feed") == "https://example.com/feed"
