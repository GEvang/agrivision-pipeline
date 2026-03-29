from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from agrivision.config.settings import get_project_root

JSONDict = dict[str, Any]


@dataclass(frozen=True)
class StorageLayout:
    project_root: Path
    data_root: Path
    runtime_root: Path
    uploads_root: Path
    runs_root: Path


class StorageService:
    def __init__(self, project_root: Path | None = None) -> None:
        root = (project_root or get_project_root()).resolve()
        self.layout = StorageLayout(
            project_root=root,
            data_root=root / 'data',
            runtime_root=root / 'runtime',
            uploads_root=root / 'data' / 'uploads',
            runs_root=root / 'runtime' / 'runs',
        )
        self.ensure_directories()

    def ensure_directories(self) -> None:
        for path in (
            self.layout.data_root,
            self.layout.runtime_root,
            self.layout.uploads_root,
            self.layout.runs_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def new_run_id(self) -> str:
        return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]

    def upload_dir(self, run_id: str) -> Path:
        path = self.layout.uploads_root / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def run_dir(self, run_id: str) -> Path:
        path = self.layout.runs_root / run_id
        (path / 'previews').mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, path: Path, payload: JSONDict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')

    def read_json(self, path: Path, default: JSONDict | None = None) -> JSONDict:
        if not path.exists():
            return default.copy() if default else {}
        return json.loads(path.read_text(encoding='utf-8'))

    def copy_tree(self, src: Path, dst: Path) -> None:
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    def safe_resolve_within(self, root: Path, relative_path: str) -> Path:
        candidate = (root / relative_path).resolve()
        if root.resolve() not in candidate.parents and candidate != root.resolve():
            raise ValueError('Requested path escapes storage root.')
        return candidate
