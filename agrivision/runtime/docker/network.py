from __future__ import annotations

from urllib.parse import urlparse


def service_port_from_url(url: str) -> int | None:
    parsed = urlparse(url)
    return parsed.port
