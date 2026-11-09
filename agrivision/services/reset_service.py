"""Reset parts of an AgriVision install, cautiously.

Three levels, each a superset of the one before it in what it removes:

- ``outputs``: runs, uploads, reports and exports. Settings, credentials and
  the OpenAgri services stay.
- ``services``: one service (or all three): its containers and Docker
  volumes, i.e. its database, and its cloned folder. The next start clones it
  again at the pinned commit with a fresh database.
- ``all``: both of the above plus dashboard settings and saved credentials,
  i.e. a first-run state.

Docker images are kept unless asked for, so the next start does not download
them again. A reset is planned first and only executed after confirmation;
it refuses to run while a pipeline run is active.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from agrivision.config.settings import get_project_root, get_runtime_settings_path
from agrivision.runtime.service_runtime import compose_down, detect_compose_file

RESET_LEVELS = ("outputs", "services", "all")
SERVICE_DIRS = {
    "weather": "OpenAgri-WeatherService",
    "irrigation": "OpenAgri-IrrigationManagement",
    "pdm": "OpenAgri-PestAndDiseaseManagement",
}
# Relative to the project root; removed by the outputs level.
OUTPUT_PATHS = ("output", "data/uploads", "runtime/runs", "runtime/exports", "runtime/archived_runs")
# Worth keeping in a backup: run records, saved orthophotos/reports, raw uploads.
BACKUP_PATHS = ("output/runs", "data/uploads", "runtime/runs", "runtime/archived_runs")


class ResetRefused(RuntimeError):
    pass


@dataclass
class ResetPlan:
    level: str
    project_root: Path
    delete_paths: list[Path] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    remove_images: bool = False
    containers: dict[str, list[str]] = field(default_factory=dict)

    def describe(self) -> list[str]:
        lines = [f"Reset level: {self.level}"]
        for service_key in self.services:
            lines.append(
                f"  - {service_key}: remove containers and volumes (its database)"
                + (" and images" if self.remove_images else "")
                + f", then delete {SERVICE_DIRS[service_key]}/"
            )
            names = self.containers.get(service_key)
            if names:
                lines.append(f"      containers: {', '.join(names)}")
        for path in self.delete_paths:
            lines.append(f"  - delete {path.relative_to(self.project_root)}")
        if len(lines) == 1:
            lines.append("  (nothing to remove)")
        lines.append("This cannot be undone.")
        return lines


def compose_project_name(repo_dir: Path) -> str:
    """Docker Compose names a project after its folder, lower-cased."""
    return re.sub(r"[^a-z0-9_-]", "", repo_dir.name.lower())


def project_containers(project: str) -> list[str]:
    """Containers Compose would remove for this project, from any folder of that name.

    Shown before a reset because two checkouts with the same folder names
    share their service containers and volumes.
    """
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={project}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return sorted(line for line in result.stdout.splitlines() if line.strip())


def active_runs(project_root: Path) -> list[str]:
    active: list[str] = []
    for status_path in sorted((project_root / "runtime" / "runs").glob("*/status.json")):
        try:
            status = json.loads(status_path.read_text(encoding="utf-8")).get("status")
        except (OSError, ValueError):
            continue
        if status in {"queued", "running"}:
            active.append(status_path.parent.name)
    return active


def plan_reset(
    level: str,
    *,
    service: str | None = None,
    remove_images: bool = False,
    project_root: Path | None = None,
) -> ResetPlan:
    if level not in RESET_LEVELS:
        raise ValueError(f"Unknown reset level {level!r}; choose one of {', '.join(RESET_LEVELS)}.")
    if service is not None and service not in SERVICE_DIRS:
        raise ValueError(f"Unknown service {service!r}; choose one of {', '.join(SERVICE_DIRS)}.")
    if service is not None and level != "services":
        raise ValueError("--service can only be used with the services level.")

    root = (project_root or get_project_root()).resolve()
    plan = ResetPlan(level=level, project_root=root, remove_images=remove_images)
    if level in {"outputs", "all"}:
        plan.delete_paths += [root / relative for relative in OUTPUT_PATHS if (root / relative).exists()]
    if level in {"services", "all"}:
        keys = [service] if service else list(SERVICE_DIRS)
        plan.services = [key for key in keys if (root / SERVICE_DIRS[key]).exists()]
        plan.containers = {
            key: project_containers(compose_project_name(root / SERVICE_DIRS[key])) for key in plan.services
        }
    if level == "all":
        runtime_settings = get_runtime_settings_path()
        for path in (
            runtime_settings,
            runtime_settings.with_name("app-secrets.env"),
            root / "runtime" / "service-helper" / "services",
        ):
            if path.exists() and root in path.resolve().parents:
                plan.delete_paths.append(path)
    return plan


def write_backup(project_root: Path, destination: Path) -> Path:
    """Zip runs, saved outputs and uploads before they are deleted."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for relative in BACKUP_PATHS:
            source = project_root / relative
            if not source.exists():
                continue
            for path in sorted(source.rglob("*")):
                # ODM working folders are large and can be rebuilt from uploads.
                if path.is_file() and "workspace" not in path.relative_to(source).parts:
                    archive.write(path, path.relative_to(project_root).as_posix())
    return destination


def default_backup_path(project_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return project_root.parent / f"agrivision-backup-{stamp}.zip"


def execute_reset(plan: ResetPlan, *, backup_to: Path | None = None) -> list[str]:
    blocking = active_runs(plan.project_root)
    if blocking:
        raise ResetRefused(
            f"Run(s) {', '.join(blocking)} are still active. Stop them in the dashboard before resetting."
        )
    done: list[str] = []
    if backup_to is not None:
        done.append(f"Backup written to {write_backup(plan.project_root, backup_to)}")

    for service_key in plan.services:
        repo_dir = plan.project_root / SERVICE_DIRS[service_key]
        try:
            compose_down(detect_compose_file(repo_dir), repo_dir, remove_images=plan.remove_images)
        except Exception as exc:  # noqa: BLE001
            # Keep the folder so the containers can still be removed by hand.
            raise ResetRefused(
                f"Could not remove the {service_key} containers ({exc}); its folder was kept."
            ) from exc
        shutil.rmtree(repo_dir)
        done.append(f"Removed {service_key} containers, volumes and {SERVICE_DIRS[service_key]}/")

    for path in plan.delete_paths:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        done.append(f"Deleted {path.relative_to(plan.project_root)}")
    return done
