"""Validation helpers for URLs fetched by production workers."""

import ipaddress
import socket
from urllib.parse import urlsplit


def validate_public_http_url(url: str, *, resolve_dns: bool = False) -> str:
    """Reject malformed URLs and destinations inside private/internal networks."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Source URL must use http or https")
    if not parsed.hostname:
        raise ValueError("Source URL must include a hostname")
    if parsed.username or parsed.password:
        raise ValueError("Source URL must not contain credentials")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("Local source URLs are not allowed")

    addresses: set[str] = set()
    try:
        addresses.add(str(ipaddress.ip_address(hostname)))
    except ValueError:
        if resolve_dns:
            try:
                addresses.update(
                    item[4][0]
                    for item in socket.getaddrinfo(
                        hostname,
                        parsed.port or (443 if parsed.scheme == "https" else 80),
                        type=socket.SOCK_STREAM,
                    )
                )
            except socket.gaierror as exc:
                raise ConnectionError(f"Could not resolve source host: {hostname}") from exc

    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            raise ValueError("Private, loopback, link-local, and reserved source addresses are not allowed")

    return url
