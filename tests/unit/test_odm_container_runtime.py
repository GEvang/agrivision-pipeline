from pathlib import Path

from agrivision.pipeline.stages import odm


def test_resolve_odm_bind_source_uses_host_project_root(monkeypatch, tmp_path: Path) -> None:
    host_root = tmp_path / "host-project"
    container_root = Path("/workspace")
    project_root = container_root / "data" / "odm_project_rgb"

    host_root.mkdir(parents=True)
    monkeypatch.setenv("HOST_PROJECT_ROOT", str(host_root))
    monkeypatch.setenv("APP_CONTAINER_PROJECT_ROOT", str(container_root))

    resolved = odm._resolve_odm_bind_source(project_root)

    assert resolved == host_root / "data" / "odm_project_rgb"


def test_resolve_odm_bind_source_falls_back_without_container_mapping(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "data" / "odm_project_rgb"
    monkeypatch.delenv("HOST_PROJECT_ROOT", raising=False)
    monkeypatch.delenv("APP_CONTAINER_PROJECT_ROOT", raising=False)

    resolved = odm._resolve_odm_bind_source(project_root)

    assert resolved == project_root.resolve()
