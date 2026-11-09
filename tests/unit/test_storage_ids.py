from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agrivision.app import api
from agrivision.app import dependencies as deps
from agrivision.schemas.ids import InvalidStorageIdError, validate_storage_id
from agrivision.services.run_service import RunNotFoundError, RunService
from agrivision.services.storage_service import StorageService

TRAVERSAL_IDS = ["..", "../outside", "a/b", "a\\b", ".hidden", "", "x" * 81, "run id"]


@pytest.mark.parametrize("value", ["20260401T182808Z-28e38084", "run-1", "upload_seed"])
def test_safe_ids_are_accepted(value: str) -> None:
    assert validate_storage_id(value) == value


@pytest.mark.parametrize("value", TRAVERSAL_IDS)
def test_unsafe_ids_are_rejected(value: str) -> None:
    with pytest.raises(InvalidStorageIdError):
        validate_storage_id(value)


@pytest.mark.parametrize("value", TRAVERSAL_IDS)
def test_storage_folders_reject_unsafe_ids(tmp_path: Path, value: str) -> None:
    storage = StorageService(project_root=tmp_path)

    with pytest.raises(InvalidStorageIdError):
        storage.upload_dir(value)
    with pytest.raises(InvalidStorageIdError):
        storage.run_dir(value)
    assert not (tmp_path.parent / "outside").exists()


def test_load_run_treats_unsafe_ids_as_missing(tmp_path: Path) -> None:
    run_service = RunService(StorageService(project_root=tmp_path))

    with pytest.raises(RunNotFoundError):
        run_service.load_run("../../etc")


def test_api_rejects_traversal_in_run_requests(tmp_path: Path, monkeypatch) -> None:
    storage = StorageService(project_root=tmp_path)
    monkeypatch.setattr(deps, "storage_service", storage)
    monkeypatch.setattr(deps, "run_service", RunService(storage))
    client = TestClient(api.app)

    create = client.post(
        "/runs",
        json={"dataset_name": "x", "upload_run_id": "../../../home"},
    )
    source = client.post(
        "/runs",
        json={
            "dataset_name": "x",
            "upload_run_id": "upload-1",
            "parameters": {"source_orthophoto_run_id": "../other"},
        },
    )
    status = client.get("/runs/..%2F..%2Fetc/status")

    assert create.status_code == 422
    assert source.status_code == 422
    assert status.status_code == 404
    assert not (tmp_path.parent / "home").exists()


@pytest.mark.parametrize(
    "recorded",
    [
        "/app/runtime/runs/run-1/workspace/output/report/index.html",
        "/home/old-user/projects/renamed-checkout/runtime/runs/run-1/workspace/output/report/index.html",
        r"C:\Users\old\agrivision\runtime\runs\run-1\workspace\output\report\index.html",
    ],
)
def test_recorded_paths_are_rebased_on_this_project(tmp_path: Path, recorded: str) -> None:
    report = tmp_path / "runtime" / "runs" / "run-1" / "workspace" / "output" / "report" / "index.html"
    report.parent.mkdir(parents=True)
    report.write_text("ok", encoding="utf-8")
    (tmp_path / "output" / "report").mkdir(parents=True)
    (tmp_path / "output" / "report" / "index.html").write_text("wrong file", encoding="utf-8")

    assert StorageService(project_root=tmp_path).resolve_recorded_path(recorded) == report


def test_pages_render_with_runs_recorded_on_another_machine(tmp_path: Path, monkeypatch) -> None:
    """Records written by a host run, read in the container (or after a move)."""
    import json

    from agrivision.schemas.runs import RunCreateRequest
    from agrivision.services.report_service import ReportService

    storage = StorageService(project_root=tmp_path)
    run_service = RunService(storage)
    record = run_service.create_run_record(
        RunCreateRequest(dataset_name="Field", upload_run_id="upload-1", selected_steps={"run_odm": True, "fetch_weather": False, "run_irrigation": False, "run_pdm": False, "generate_report": False})
    )
    status_path = storage.run_dir(record.run_id) / "status.json"
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    foreign = "/home/someone-else/agrivision"
    payload.update(
        status="completed",
        run_dir=f"{foreign}/runtime/runs/{record.run_id}",
        input_path=f"{foreign}/data/uploads/upload-1",
        logs_path=f"{foreign}/runtime/runs/{record.run_id}/run.log",
        outputs={"orthophoto_rgb": f"{foreign}/data/odm_project_rgb/project/odm_orthophoto/odm_orthophoto.tif"},
    )
    status_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(deps, "storage_service", storage)
    monkeypatch.setattr(deps, "run_service", run_service)
    monkeypatch.setattr(deps, "report_service", ReportService(run_service=run_service))
    client = TestClient(api.app)

    assert client.get("/runs/orthophotos").status_code == 200
    assert client.get("/runs/analyze").status_code == 200
