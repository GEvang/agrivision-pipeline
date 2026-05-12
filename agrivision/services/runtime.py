from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import requests

from agrivision.config.settings import get_project_root


class ServiceBootstrapError(RuntimeError):
    """Raised when an external service cannot be prepared or started."""


@dataclass(frozen=True)
class EnvSyncResult:
    """Describe how a service .env file changed during reconciliation."""

    env_path: Path
    changed: bool
    changed_keys: tuple[str, ...]


@dataclass(frozen=True)
class ServiceRuntimeState:
    """Describe what happened while reconciling a sibling service."""

    repo_dir: Path
    env_sync: EnvSyncResult
    compose_file: Path
    was_reachable: bool
    restarted: bool
    started: bool
    ready: bool
    readiness_urls: tuple[str, ...]


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


def _parse_env_file(env_path: Path) -> tuple[list[str], dict[str, str]]:
    lines: list[str] = []
    existing: dict[str, str] = {}
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            existing[key] = value
    return lines, existing


def update_env_file(env_path: Path, values: Mapping[str, str]) -> EnvSyncResult:
    lines, existing = _parse_env_file(env_path)
    merged = dict(existing)
    changed_keys: list[str] = []
    for key, value in values.items():
        if value is None:
            continue
        current = merged.get(key)
        merged[key] = value
        if current != value:
            changed_keys.append(key)

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

    rendered = "\n".join(out_lines).rstrip() + "\n"
    previous = env_path.read_text(encoding="utf-8") if env_path.exists() else None
    if previous != rendered:
        env_path.write_text(rendered, encoding="utf-8")
        return EnvSyncResult(env_path=env_path, changed=True, changed_keys=tuple(changed_keys))
    return EnvSyncResult(env_path=env_path, changed=False, changed_keys=tuple())


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
    docker = shutil.which("docker")
    docker_compose = shutil.which("docker-compose")
    if docker is None and docker_compose is None:
        raise ServiceBootstrapError(
            "Docker Compose was not found on PATH. Install Docker Desktop, Docker Engine "
            "with the compose plugin, or standalone `docker-compose`."
        )

    commands = []
    if docker:
        commands.append([docker, "compose", "-f", str(compose_file), *args])
    if docker_compose:
        commands.append([docker_compose, "-f", str(compose_file), *args])

    sudo = shutil.which("sudo")
    sudo_enabled = os.getenv("AGRIVISION_ALLOW_SUDO_DOCKER", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }
    if sudo and sudo_enabled:
        if docker:
            commands.append([sudo, "-n", docker, "compose", "-f", str(compose_file), *args])
        if docker_compose:
            commands.append([sudo, "-n", docker_compose, "-f", str(compose_file), *args])

    last_error: Exception | None = None
    attempted = []
    for cmd in commands:
        attempted.append(" ".join(cmd))
        try:
            subprocess.run(cmd, cwd=str(repo_dir), check=True)
            return
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:  # pragma: no cover
            last_error = exc
    raise ServiceBootstrapError(
        f"Failed to run docker compose for {compose_file}: {last_error}. "
        f"Attempted: {'; '.join(attempted)}"
    )


def compose_up(
    compose_file: Path,
    repo_dir: Path,
    *,
    force_recreate: bool = False,
    build: bool = False,
) -> None:
    args = ["up", "-d"]
    if build:
        args.append("--build")
    if force_recreate:
        args.append("--force-recreate")
    _run_compose_command(compose_file, repo_dir, args)


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


def check_first_reachable_url(urls: Sequence[str]) -> bool:
    for url in urls:
        try:
            response = requests.get(url, timeout=3)
            if response.status_code < 500:
                return True
        except requests.RequestException:
            continue
    return False


def mask_env_value(value: str) -> str:
    if value == "":
        return "<empty>"
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}***{value[-2:]}"


def summarize_env_changes(values: Mapping[str, str], sync: EnvSyncResult) -> list[str]:
    if not sync.changed:
        return [f"No changes detected in {sync.env_path}."]
    summary: list[str] = [f"Updated {sync.env_path}."]
    for key in sync.changed_keys:
        raw = values.get(key, "")
        looks_secret = any(token in key for token in ("KEY", "TOKEN", "PASSWORD", "SECRET"))
        rendered = mask_env_value(raw) if looks_secret else raw
        summary.append(f"  - {key} -> {rendered}")
    return summary


def reconcile_service_runtime(
    *,
    repo_dir: Path,
    repo_url: str,
    env_values: Mapping[str, str],
    compose_candidates: Iterable[str] | None,
    readiness_urls: Sequence[str],
    timeout_seconds: int = 90,
    build_on_recreate: bool = False,
) -> ServiceRuntimeState:
    clone_repo_if_missing(repo_dir, repo_url)
    env_path = ensure_env_file(repo_dir)
    env_sync = update_env_file(env_path, env_values)
    compose_file = detect_compose_file(repo_dir, compose_candidates)
    was_reachable = check_first_reachable_url(readiness_urls)

    restarted = False
    started = False
    if env_sync.changed:
        compose_up(compose_file, repo_dir, force_recreate=True, build=build_on_recreate)
        restarted = True
    elif not was_reachable:
        compose_up(compose_file, repo_dir)
        started = True

    ready = wait_for_any_url(readiness_urls, timeout_seconds=timeout_seconds) if (env_sync.changed or not was_reachable) else True
    if not ready:
        raise ServiceBootstrapError(
            f"Service in {repo_dir} did not become reachable. Checked: {', '.join(readiness_urls)}"
        )

    return ServiceRuntimeState(
        repo_dir=repo_dir,
        env_sync=env_sync,
        compose_file=compose_file,
        was_reachable=was_reachable,
        restarted=restarted,
        started=started,
        ready=ready,
        readiness_urls=tuple(readiness_urls),
    )


def base_env_values() -> dict[str, str]:
    return {
        "DOCKER_REGISTRY": os.getenv("DOCKER_REGISTRY", "openagri-eu"),
        "TAG": os.getenv("TAG", "latest"),
    }
