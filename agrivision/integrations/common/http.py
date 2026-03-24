from __future__ import annotations

import requests

DEFAULT_TIMEOUT = 20


def request_json(method: str, url: str, *, timeout: int = DEFAULT_TIMEOUT, **kwargs):
    response = requests.request(method, url, timeout=timeout, **kwargs)
    response.raise_for_status()
    return response.json()
