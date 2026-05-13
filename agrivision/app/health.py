from __future__ import annotations

import subprocess
from urllib.error import URLError
from urllib.request import Request as UrlRequest, urlopen

from agrivision.config import load_config


def url_health(name: str, base_url: str, paths: tuple[str, ...] = ('/health', '/docs', '/openapi.json')) -> dict[str, str]:
    for path in paths:
        url = base_url.rstrip('/') + path
        try:
            request = UrlRequest(url, method='GET')
            with urlopen(request, timeout=0.8) as response:
                if 200 <= response.status < 500:
                    state = 'ok' if response.status < 400 else 'warn'
                    return {'name': name, 'state': state, 'detail': f'HTTP {response.status}', 'target': url}
        except (OSError, URLError):
            continue
    return {'name': name, 'state': 'down', 'detail': 'Not reachable', 'target': base_url}


def docker_health() -> dict[str, str]:
    try:
        result = subprocess.run(
            ['docker', 'version', '--format', '{{.Server.Version}}'],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {'name': 'Docker', 'state': 'down', 'detail': 'Unavailable', 'target': 'docker'}
    version = result.stdout.strip()
    if result.returncode == 0 and version:
        return {'name': 'Docker', 'state': 'ok', 'detail': version, 'target': 'docker'}
    return {'name': 'Docker', 'state': 'warn', 'detail': 'Installed, daemon unavailable', 'target': 'docker'}


def service_health() -> list[dict[str, str]]:
    config = load_config()
    return [
        docker_health(),
        url_health('Weather', config.get('weather', {}).get('base_url', '')),
        url_health('Irrigation', config.get('irrigation', {}).get('base_url', '')),
        url_health('PDM', config.get('pdm', {}).get('base_url', '')),
    ]
