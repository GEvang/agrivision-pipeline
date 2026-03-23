from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Iterable, Mapping

import requests

from agrivision.config.settings import get_project_root


class ServiceBootstrapError(RuntimeError):
    """Raised when an external service cannot be prepared or started."""


def project_service_dir(dirname: str) -> Path:
    return get_project_root() / dirname


def clone_repo_if_missing(repo_dir: Path, repo_url: str) -> None:
    if repo_dir.exists():
        return
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", repo_url, str(repo_dir)], check=True)


def ensure_env_file(repo_dir: Path) -> Path:
    env_path = repo_dir / ".env"
    if env_path.exists():
        return env_path
    for candidate in ("env.example", ".env.example"):
        template = repo_dir / candidate
        if template.exists():
            shutil.copyfile(template, env_path)
            return env_path
    env_path.write_text("", encoding="utf-8")
    return env_path


def update_env_file(env_path: Path, values: Mapping[str, str]) -> None:
    existing: dict[str, str] = {}
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            existing[key] = value

    merged = dict(existing)
    for key, value in values.items():
        if value is not None:
            merged[key] = value

    seen: set[str] = set()
    out_lines: list[str] = []
    for line in lines:
        if not line or line.lstrip().startswith("#") or "=" not in line:
            out_lines.append(line)
            continue
        key, _ = line.split("=", 1)
        if key in merged:
            out_lines.append(f"{key}={merged[key]}")
            seen.add(key)
        else:
            out_lines.append(line)

    for key, value in merged.items():
        if key not in seen:
            out_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")


def detect_compose_file(repo_dir: Path, candidates: Iterable[str] | None = None) -> Path:
    names = list(
        candidates
        or [
            "docker-compose-x86_64.yml",
            "docker-compose-arm64.yml",
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
            "compose.yaml",
        ]
    )
    for name in names:
        path = repo_dir / name
        if path.exists():
            return path
    raise ServiceBootstrapError(
        f"No compose file found in {repo_dir}. Tried: {', '.join(names)}"
    )


def _run_compose_command(compose_file: Path, repo_dir: Path, args: list[str]) -> None:
    commands = [
        ["docker", "compose", "-f", str(compose_file), *args],
        ["sudo", "-n", "docker", "compose", "-f", str(compose_file), *args],
    ]
    last_error: Exception | None = None
    for cmd in commands:
        try:
            subprocess.run(cmd, cwd=str(repo_dir), check=True)
            return
        except Exception as exc:  # pragma: no cover
            last_error = exc
    raise ServiceBootstrapError(
        f"Failed to run docker compose for {compose_file}: {last_error}"
    )


def compose_up(compose_file: Path, repo_dir: Path) -> None:
    _run_compose_command(compose_file, repo_dir, ["up", "-d"])


def wait_for_any_url(urls: Iterable[str], timeout_seconds: int = 90) -> bool:
    deadline = time.time() + timeout_seconds
    url_list = list(urls)
    while time.time() < deadline:
        for url in url_list:
            try:
                response = requests.get(url, timeout=3)
                if response.status_code < 500:
                    return True
            except requests.RequestException:
                pass
        time.sleep(2)
    return False


def base_env_values() -> dict[str, str]:
    return {
        "DOCKER_REGISTRY": os.getenv("DOCKER_REGISTRY", "ghcr.io"),
        "TAG": os.getenv("TAG", "latest"),
    }
