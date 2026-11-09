from __future__ import annotations

import json
import zipfile
from pathlib import Path

from agrivision.config.paths import resolve_project_path, to_project_path
from agrivision.services.path_migration import migrate_recorded_paths


def _setup(root: Path) -> Path:
    report = root / "output" / "runs" / "run-1" / "report.html"
    report.parent.mkdir(parents=True)
    report.write_text("ok", encoding="utf-8")
    status = root / "runtime" / "runs" / "run-1" / "status.json"
    status.parent.mkdir(parents=True)
    status.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "run_dir": str(root / "runtime" / "runs" / "run-1"),
                "outputs": {
                    "report_html": "/home/old-user/elsewhere/output/runs/run-1/report.html",
                    "container": "/app/output/runs/run-1/report.html",
                },
                "external": "/mnt/usb/flight-photos/img1.jpg",
                "already": "output/runs/run-1/report.html",
            }
        ),
        encoding="utf-8",
    )
    return status


def test_migration_converts_project_paths_and_backs_up(tmp_path: Path) -> None:
    status = _setup(tmp_path)
    original = status.read_text(encoding="utf-8")

    result = migrate_recorded_paths(tmp_path)

    data = json.loads(status.read_text(encoding="utf-8"))
    assert data["run_dir"] == "runtime/runs/run-1"
    assert data["outputs"] == {
        "report_html": "output/runs/run-1/report.html",
        "container": "output/runs/run-1/report.html",
    }
    assert data["external"] == "/mnt/usb/flight-photos/img1.jpg"
    assert data["already"] == "output/runs/run-1/report.html"
    assert result.paths_converted == 3
    assert result.paths_left == ["/mnt/usb/flight-photos/img1.jpg"]
    backup = zipfile.ZipFile(result.backup)
    assert backup.read("runtime/runs/run-1/status.json").decode("utf-8") == original


def test_migration_is_idempotent_and_dry_run_writes_nothing(tmp_path: Path) -> None:
    status = _setup(tmp_path)
    before = status.read_text(encoding="utf-8")

    preview = migrate_recorded_paths(tmp_path, dry_run=True)
    assert status.read_text(encoding="utf-8") == before
    assert preview.backup is None and preview.paths_converted == 3

    migrate_recorded_paths(tmp_path)
    second = migrate_recorded_paths(tmp_path)

    assert second.files_changed == [] and second.paths_converted == 0


def test_relative_paths_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "runtime" / "runs" / "run-1" / "run.log"

    stored = to_project_path(target, tmp_path)

    assert stored == "runtime/runs/run-1/run.log"
    assert resolve_project_path(stored, tmp_path) == target
    assert to_project_path("/somewhere/else.txt", tmp_path) == "/somewhere/else.txt"
