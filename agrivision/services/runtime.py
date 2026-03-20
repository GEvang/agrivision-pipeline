from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Iterable, Mapping
from urllib.parse import urlparse

import requests


def parse_port_from_base_url(base_url: str, default: int) -> int:
    try:
        parsed = urlparse(base_url)
        if parsed.port is not None:
            return int(parsed.port)
    except Exception:
        pass
    return default


def clone_repo_if_missing(repo_dir: Path, clone_url: str) -> bool:
    if repo_dir.exists():
        return False
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", clone_url, str(repo_dir)], check=True)
    return True


def find_existing_file(directory: Path, candidates: Iterable[str]) -> Path | None:
    for name in candidates:
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None


def ensure_env_file(repo_dir: Path, template_candidates: Iterable[str]) -> Path:
    env_path = repo_dir / ".env"
    if env_path.exists():
        return env_path

    template = find_existing_file(repo_dir, template_candidates)
    if template is not None:
        env_path.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        env_path.write_text("", encoding="utf-8")
    return env_path


def upsert_env_values(env_path: Path, values: Mapping[str, str]) -> None:
    existing: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            existing[key] = value

    for key, value in values.items():
        existing[key] = value

    lines = [f"{key}={value}" for key, value in sorted(existing.items())]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def compose_up(repo_dir: Path, compose_file: Path, force_recreate: bool = True) -> None:
    base_cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d"]
    if force_recreate:
        base_cmd.append("--force-recreate")

    cmds = [base_cmd, ["sudo", "-n", *base_cmd]]
    last_error: str | None = None
    for cmd in cmds:
        try:
            subprocess.run(
                cmd,
                cwd=str(repo_dir),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return
        except Exception as exc:
            last_error = str(exc)
    raise RuntimeError(f"docker compose up failed: {last_error}")


def http_ok(url: str, timeout: int = 3) -> bool:
    try:
        response = requests.get(url, timeout=timeout)
        return 200 <= response.status_code < 500
    except requests.RequestException:
        return False


def wait_for_http(url: str, seconds: int = 75, interval: float = 2.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if http_ok(url):
            return True
        time.sleep(interval)
    return False


def replace_or_append_line(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^(?P<key>{re.escape(key)})=.*$", re.MULTILINE)
    line = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(line, text)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + line + "\n"
