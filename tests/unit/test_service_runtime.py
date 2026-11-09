import subprocess
from pathlib import Path

import pytest

from agrivision.runtime import host_helper as host_service_helper
from agrivision.runtime import service_runtime as runtime
from agrivision.runtime.irrigation import _apply_compatibility_patches
from agrivision.runtime.service_runtime import (
    ServiceBootstrapError,
    base_env_values,
    update_env_file,
)


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


def test_clone_repo_checks_out_pinned_ref(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(runtime.subprocess, "run", lambda cmd, **kwargs: calls.append(cmd))
    repo_dir = tmp_path / "OpenAgri-Service"

    runtime.clone_repo_if_missing(repo_dir, "https://example.test/repo.git", "abc123")

    assert calls == [
        ["git", "clone", "https://example.test/repo.git", str(repo_dir)],
        ["git", "-C", str(repo_dir), "checkout", "--quiet", "abc123"],
    ]


def test_clone_repo_leaves_existing_checkout_untouched(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(runtime.subprocess, "run", lambda cmd, **kwargs: calls.append(cmd))

    runtime.clone_repo_if_missing(tmp_path, "https://example.test/repo.git", "abc123")

    assert calls == []


def test_irrigation_compatibility_patch_pins_unpinned_sqlalchemy(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("alembic==1.13.1 # DB migrations\nsqlalchemy\npsycopg2==2.9.9\n", encoding="utf-8")

    _apply_compatibility_patches(tmp_path)
    _apply_compatibility_patches(tmp_path)

    lines = requirements.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "alembic==1.13.1 # DB migrations"
    assert lines[1].startswith("SQLAlchemy==2.0.49")
    assert lines[2] == "psycopg2==2.9.9"
    assert len(lines) == 3


def test_irrigation_compatibility_patch_adds_missing_sqlalchemy_pin(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("alembic==1.13.1\npsycopg2==2.9.9 # PSQL driver\n", encoding="utf-8")

    _apply_compatibility_patches(tmp_path)

    lines = requirements.read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if line.lower().startswith("sqlalchemy")] == [
        lines[-1]
    ]
    assert lines[-1].startswith("SQLAlchemy==2.0.49")


def test_irrigation_compatibility_patch_keeps_exact_sqlalchemy_pin(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("SQLAlchemy==2.0.31\n", encoding="utf-8")

    _apply_compatibility_patches(tmp_path)

    assert requirements.read_text(encoding="utf-8") == "SQLAlchemy==2.0.31\n"


@pytest.mark.parametrize(
    "reported",
    [
        "/home/user/agrivision/runtime/service-helper/logs/req-1.log",
        r"C:\Users\user\agrivision\runtime\service-helper\logs\req-1.log",
    ],
)
def test_helper_log_path_maps_host_path_into_helper_folder(monkeypatch, tmp_path: Path, reported: str) -> None:
    monkeypatch.setattr(host_service_helper, "helper_root", lambda: tmp_path)

    assert host_service_helper._local_log_path(reported) == tmp_path / "logs" / "req-1.log"


def test_clone_repo_fetches_pinned_ref_missing_from_branches(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        calls.append(cmd)
        if cmd[-1] == "abc123" and "checkout" in cmd:
            raise subprocess.CalledProcessError(128, cmd)

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)
    repo_dir = tmp_path / "OpenAgri-Service"

    runtime.clone_repo_if_missing(repo_dir, "https://example.test/repo.git", "abc123")

    assert calls[-2:] == [
        ["git", "-C", str(repo_dir), "fetch", "--quiet", "origin", "abc123"],
        ["git", "-C", str(repo_dir), "checkout", "--quiet", "FETCH_HEAD"],
    ]


def test_clone_repo_removes_clone_when_pinned_ref_is_unavailable(monkeypatch, tmp_path: Path) -> None:
    repo_dir = tmp_path / "OpenAgri-Service"

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        if cmd[1] == "clone":
            repo_dir.mkdir()
            return
        raise subprocess.CalledProcessError(128, cmd)

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)

    with pytest.raises(ServiceBootstrapError, match="abc123"):
        runtime.clone_repo_if_missing(repo_dir, "https://example.test/repo.git", "abc123")

    assert not repo_dir.exists()
