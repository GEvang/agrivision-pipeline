from pathlib import Path
import subprocess

import pytest

from agrivision.services import runtime
from agrivision.services.irrigation.runtime import _apply_compatibility_patches
from agrivision.services.runtime import ServiceBootstrapError, base_env_values, update_env_file


def test_update_env_file_reports_changed_keys(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("A=1\nB=2\n", encoding="utf-8")

    sync = update_env_file(env_path, {"A": "1", "B": "3", "C": "4"})

    assert sync.changed is True
    assert set(sync.changed_keys) == {"B", "C"}
    assert env_path.read_text(encoding="utf-8") == "A=1\nB=3\nC=4\n"


def test_update_env_file_noop_when_values_match(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("A=1\n", encoding="utf-8")

    sync = update_env_file(env_path, {"A": "1"})

    assert sync.changed is False
    assert sync.changed_keys == ()


def test_run_compose_command_skips_missing_sudo(monkeypatch, tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        return "docker.exe" if name == "docker" else None

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        calls.append(cmd)
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(runtime.shutil, "which", fake_which)
    monkeypatch.setattr(runtime.subprocess, "run", fake_run)

    with pytest.raises(ServiceBootstrapError) as exc:
        runtime._run_compose_command(compose_file, tmp_path, ["up", "-d"])

    assert len(calls) == 1
    assert calls[0][0] == "docker.exe"
    assert "sudo" not in str(exc.value)


def test_run_compose_command_can_use_sudo_when_available(monkeypatch, tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        return {"docker": "/usr/bin/docker", "sudo": "/usr/bin/sudo"}.get(name)

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        calls.append(cmd)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(runtime.shutil, "which", fake_which)
    monkeypatch.setattr(runtime.subprocess, "run", fake_run)

    runtime._run_compose_command(compose_file, tmp_path, ["up", "-d"])

    assert calls[0][0] == "/usr/bin/docker"
    assert calls[1][:3] == ["/usr/bin/sudo", "-n", "/usr/bin/docker"]


def test_run_compose_command_supports_standalone_docker_compose(monkeypatch, tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        return "docker-compose.exe" if name == "docker-compose" else None

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        calls.append(cmd)

    monkeypatch.setattr(runtime.shutil, "which", fake_which)
    monkeypatch.setattr(runtime.subprocess, "run", fake_run)

    runtime._run_compose_command(compose_file, tmp_path, ["up", "-d"])

    assert calls == [["docker-compose.exe", "-f", str(compose_file), "up", "-d"]]


def test_run_compose_command_reports_missing_compose(monkeypatch, tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(runtime.shutil, "which", lambda name: None)

    with pytest.raises(ServiceBootstrapError, match="Docker Compose was not found"):
        runtime._run_compose_command(compose_file, tmp_path, ["up", "-d"])


def test_base_env_values_use_openagri_registry_by_default(monkeypatch) -> None:
    monkeypatch.delenv("DOCKER_REGISTRY", raising=False)

    assert base_env_values()["DOCKER_REGISTRY"] == "openagri-eu"


def test_irrigation_compatibility_patch_adds_missing_imports(tmp_path: Path) -> None:
    main_path = tmp_path / "app" / "main.py"
    main_path.parent.mkdir()
    main_path.write_text("from fastapi import FastAPI\nlogger = logging.getLogger(__name__)\n", encoding="utf-8")

    _apply_compatibility_patches(tmp_path)

    text = main_path.read_text(encoding="utf-8")
    assert "import logging\n" in text
    assert "import time\n" in text
