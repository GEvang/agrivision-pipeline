"""Rewrite absolute paths in existing run records to project-relative ones.

Older versions stored absolute paths (``/home/<user>/.../output/runs/<id>/report.html``)
in run records, metadata and artifact summaries. This rewrites every such path
that points inside this project to its relative form (``output/runs/<id>/report.html``).
Paths outside the project are left untouched. Every file that changes is copied
into a zip backup first, and running it again changes nothing.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from agrivision.config.paths import resolve_project_path

SCANNED_FOLDERS = ("runtime", "data", "output")
BACKUP_FOLDER = Path("runtime") / "backups"
_ABSOLUTE = re.compile(r"^(/|[A-Za-z]:[\\/])")


@dataclass
class MigrationResult:
    files_scanned: int = 0
    files_changed: list[Path] = field(default_factory=list)
    paths_converted: int = 0
    paths_left: list[str] = field(default_factory=list)
    backup: Path | None = None


def _relative_form(value: str, root: Path) -> str | None:
    """Project-relative form of an absolute path inside this project, else None."""
    resolved = resolve_project_path(value, root)
    for candidate in (resolved, Path(value)):
        try:
            return candidate.resolve().relative_to(root).as_posix()
        except (ValueError, OSError):
            continue
    return None


def _convert(value: Any, root: Path, result: MigrationResult) -> Any:
    if isinstance(value, dict):
        return {key: _convert(item, root, result) for key, item in value.items()}
    if isinstance(value, list):
        return [_convert(item, root, result) for item in value]
    if isinstance(value, str) and _ABSOLUTE.match(value) and re.search(r"[\\/].*[\\/]", value):
        relative = _relative_form(value, root)
        if relative is not None:
            result.paths_converted += 1
            return relative
        result.paths_left.append(value)
    return value


def _json_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for folder in SCANNED_FOLDERS:
        base = root / folder
        if base.exists():
            files.extend(
                path for path in base.rglob("*.json")
                if (root / BACKUP_FOLDER) not in path.parents
            )
    return sorted(files)


def migrate_recorded_paths(project_root: Path, *, dry_run: bool = False) -> MigrationResult:
    root = project_root.resolve()
    result = MigrationResult()
    pending: list[tuple[Path, str, str]] = []
    for path in _json_files(root):
        try:
            original = path.read_text(encoding="utf-8")
            data = json.loads(original)
        except (OSError, ValueError):
            continue
        result.files_scanned += 1
        converted = _convert(data, root, result)
        if converted != data:
            pending.append((path, original, json.dumps(converted, indent=2, ensure_ascii=False)))
    result.files_changed = [path for path, _, _ in pending]
    if dry_run or not pending:
        return result

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    result.backup = root / BACKUP_FOLDER / f"path-migration-{stamp}.zip"
    result.backup.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(result.backup, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, original, _ in pending:
            archive.writestr(path.relative_to(root).as_posix(), original)
    for path, _, updated in pending:
        temp = path.with_name(f"{path.name}.tmp")
        temp.write_text(updated, encoding="utf-8")
        temp.replace(path)
    return result
