from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from agrivision.services import reset_service


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    for relative in ("output/runs/run-1", "data/uploads/up-1", "runtime/runs/run-1/workspace", "runtime/exports"):
        (root / relative).mkdir(parents=True)
    (root / "output/runs/run-1/report.html").write_text("report", encoding="utf-8")
    (root / "data/uploads/up-1/rgb.jpg").write_text("img", encoding="utf-8")
    (root / "runtime/runs/run-1/status.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    (root / "runtime/runs/run-1/workspace/odm.tif").write_text("big", encoding="utf-8")
    (root / "runtime/settings.json").write_text("{}", encoding="utf-8")
    (root / "runtime/app-secrets.env").write_text("WEATHER_PASSWORD=x\n", encoding="utf-8")
    for folder in reset_service.SERVICE_DIRS.values():
        (root / folder).mkdir()
        (root / folder / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    return root


@pytest.fixture
def project(tmp_path: Path, monkeypatch) -> Path:
    root = _project(tmp_path)
    monkeypatch.setattr(reset_service, "get_runtime_settings_path", lambda: root / "runtime" / "settings.json")
    return root


def _relative(plan: reset_service.ResetPlan) -> set[str]:
    return {path.relative_to(plan.project_root).as_posix() for path in plan.delete_paths}


def test_outputs_level_keeps_settings_credentials_and_services(project: Path) -> None:
    plan = reset_service.plan_reset("outputs", project_root=project)

    assert _relative(plan) == {"output", "data/uploads", "runtime/runs", "runtime/exports"}
    assert plan.services == []


def test_single_service_level_touches_only_that_service(project: Path) -> None:
    plan = reset_service.plan_reset("services", service="irrigation", project_root=project)

    assert plan.services == ["irrigation"]
    assert plan.delete_paths == []


def test_all_level_adds_settings_and_credentials(project: Path) -> None:
    plan = reset_service.plan_reset("all", project_root=project)

    assert {"runtime/settings.json", "runtime/app-secrets.env"} <= _relative(plan)
    assert plan.services == ["weather", "irrigation", "pdm"]


def test_service_option_only_applies_to_services_level(project: Path) -> None:
    with pytest.raises(ValueError):
        reset_service.plan_reset("all", service="pdm", project_root=project)


def test_reset_refuses_while_a_run_is_active(project: Path) -> None:
    (project / "runtime/runs/run-1/status.json").write_text(json.dumps({"status": "running"}), encoding="utf-8")
    plan = reset_service.plan_reset("outputs", project_root=project)

    with pytest.raises(reset_service.ResetRefused, match="run-1"):
        reset_service.execute_reset(plan)
    assert (project / "output").exists()


def test_service_reset_removes_volumes_then_folder(project: Path, monkeypatch) -> None:
    calls: list[tuple[Path, bool]] = []
    monkeypatch.setattr(
        reset_service, "compose_down", lambda compose_file, repo_dir, remove_images: calls.append((repo_dir, remove_images))
    )
    plan = reset_service.plan_reset("services", service="pdm", project_root=project)

    reset_service.execute_reset(plan)

    assert calls == [(project / "OpenAgri-PestAndDiseaseManagement", False)]
    assert not (project / "OpenAgri-PestAndDiseaseManagement").exists()
    assert (project / "OpenAgri-WeatherService").exists()


def test_failed_compose_down_keeps_the_service_folder(project: Path, monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("docker not reachable")

    monkeypatch.setattr(reset_service, "compose_down", fail)
    plan = reset_service.plan_reset("services", service="weather", project_root=project)

    with pytest.raises(reset_service.ResetRefused, match="weather"):
        reset_service.execute_reset(plan)
    assert (project / "OpenAgri-WeatherService").exists()


def test_backup_keeps_runs_and_uploads_but_not_odm_workspaces(project: Path, tmp_path: Path) -> None:
    plan = reset_service.plan_reset("outputs", project_root=project)

    reset_service.execute_reset(plan, backup_to=tmp_path / "backup.zip")

    names = set(zipfile.ZipFile(tmp_path / "backup.zip").namelist())
    assert {"output/runs/run-1/report.html", "data/uploads/up-1/rgb.jpg", "runtime/runs/run-1/status.json"} <= names
    assert not any("workspace" in name for name in names)
    assert not (project / "output").exists()
    assert (project / "runtime/settings.json").exists()


def test_cli_cancel_changes_nothing(project: Path, monkeypatch, capsys) -> None:
    from agrivision.app import cli

    monkeypatch.setattr(reset_service, "get_project_root", lambda: project)
    answers = iter(["n", "no"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    args = cli.build_parser().parse_args(["--reset", "outputs"])

    cli._reset(args)

    assert "Reset cancelled" in capsys.readouterr().out
    assert (project / "output/runs/run-1/report.html").exists()


def test_cli_requires_backup_choice_without_confirmation(project: Path, monkeypatch) -> None:
    from agrivision.app import cli

    monkeypatch.setattr(reset_service, "get_project_root", lambda: project)
    args = cli.build_parser().parse_args(["--reset", "all", "--yes"])

    with pytest.raises(SystemExit, match="--backup"):
        cli._reset(args)
    assert (project / "output").exists()


def test_plan_lists_the_containers_a_service_reset_removes(project: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        reset_service,
        "project_containers",
        lambda name: ["openagri-pestanddiseasemanagement-pdm-1"] if name == "openagri-pestanddiseasemanagement" else [],
    )

    plan = reset_service.plan_reset("services", service="pdm", project_root=project)

    assert "containers: openagri-pestanddiseasemanagement-pdm-1" in "\n".join(plan.describe())
