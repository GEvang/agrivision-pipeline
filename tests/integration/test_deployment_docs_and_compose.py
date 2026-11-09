import tomllib
from pathlib import Path


def test_root_compose_tags_image_with_project_version() -> None:
    root_compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    version = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert f"image: agrivision-pipeline:{version}" in root_compose
    assert "dockerfile: Dockerfile" in root_compose


def test_service_helpers_reuse_the_dashboard_image() -> None:
    for name in ("scripts/service-helper-posix.sh", "scripts/service-helper-windows.ps1"):
        script = Path(name).read_text(encoding="utf-8")
        assert "agrivision-pipeline:" not in script, f"{name} must not hard-code the image tag"
        assert "{{.Config.Image}}" in script


def test_root_compose_runs_as_launcher_supplied_user() -> None:
    root_compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert 'user: "${AGRIVISION_UID:-0}:${AGRIVISION_GID:-0}"' in root_compose
    assert '"${AGRIVISION_DOCKER_GID:-0}"' in root_compose


def test_posix_launchers_are_executable_and_lf() -> None:
    attributes = Path(".gitattributes").read_text(encoding="utf-8")
    assert "*.sh        text eol=lf" in attributes
    assert "*.command   text eol=lf" in attributes
    for name in (
        "Start AgriVision Linux.sh",
        "Start AgriVision macOS.command",
        "scripts/service-helper-posix.sh",
        "docker-entrypoint.sh",
    ):
        path = Path(name)
        assert path.stat().st_mode & 0o111, f"{name} must be executable"
        assert b"\r\n" not in path.read_bytes(), f"{name} must use LF line endings"
