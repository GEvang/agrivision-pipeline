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


def test_docker_user_args_are_empty_when_uid_gid_are_unavailable(monkeypatch) -> None:
    monkeypatch.delattr(odm.os, "getuid", raising=False)
    monkeypatch.delattr(odm.os, "getgid", raising=False)

    assert odm._docker_user_args() == []


def test_odm_dataset_mount_args_use_volumes_from_inside_app_container(monkeypatch) -> None:
    project_root = Path("/workspace/data/odm_project_rgb")
    monkeypatch.setenv("APP_CONTAINER_PROJECT_ROOT", "/workspace")
    monkeypatch.setenv("AGRIVISION_APP_CONTAINER_NAME", "agrivision-pipeline")

    mount_args, project_path = odm._odm_dataset_mount_args(project_root)

    assert mount_args == ["--volumes-from", "agrivision-pipeline"]
    assert project_path == str(project_root)
