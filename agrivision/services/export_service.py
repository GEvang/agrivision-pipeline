from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from agrivision.config import load_config
from agrivision.services.run_service import RunService
from agrivision.services.storage_service import StorageService


class RunExportService:
    def __init__(self, run_service: RunService | None = None, storage: StorageService | None = None) -> None:
        self.run_service = run_service or RunService()
        self.storage = storage or self.run_service.storage

    def build_package(self, run_id: str) -> Path:
        run = self.run_service.load_run(run_id)
        package_dir = self.storage.layout.runtime_root / 'exports'
        package_dir.mkdir(parents=True, exist_ok=True)
        package_path = package_dir / f'{run_id}-package.zip'
        if package_path.exists():
            package_path.unlink()

        manifest: dict[str, object] = {
            'run_id': run.run_id,
            'run_name': run.run_name,
            'dataset_name': run.dataset_name,
            'status': run.status,
            'created_at': run.created_at.isoformat(),
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'files': [],
        }

        with zipfile.ZipFile(package_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path, arcname in self._artifact_candidates(run_id):
                if not path.exists() or not path.is_file():
                    continue
                archive.write(path, arcname)
                manifest['files'].append(arcname)  # type: ignore[union-attr]
            archive.writestr('manifest.json', json.dumps(manifest, indent=2, sort_keys=True))

        return package_path

    def _artifact_candidates(self, run_id: str) -> list[tuple[Path, str]]:
        run = self.run_service.load_run(run_id)
        run_dir = self.storage.layout.runs_root / run_id
        candidates: list[tuple[Path, str]] = [
            (run_dir / 'status.json', 'run/status.json'),
            (run_dir / 'params.json', 'run/params.json'),
            (run_dir / 'outputs.json', 'run/outputs.json'),
            (Path(run.logs_path), 'run/run.log'),
        ]

        for key, arcname in (
            ('report_html', 'report/report.html'),
            ('ndvi_metadata', 'quality/metadata.json'),
            ('grid_metadata', 'quality/grid_metadata.json'),
            ('ndvi_tif', 'rasters/vegetation_index.tif'),
            ('orthophoto_rgb', 'rasters/orthophoto_rgb.tif'),
            ('orthophoto_mapir', 'rasters/orthophoto_mapir.tif'),
        ):
            value = run.outputs.get(key)
            if value:
                candidates.append((Path(value), arcname))

        config = load_config()
        ndvi_dir = self.storage.layout.project_root / config['paths'].get('ndvi_output', 'output/ndvi')
        candidates.extend(
            [
                (ndvi_dir / 'ndvi_color.png', 'quality/vegetation_index.png'),
                (ndvi_dir / 'ndvi_grid_overlay.png', 'quality/grid_overlay.png'),
                (ndvi_dir / 'ndvi_grid_cells.csv', 'quality/grid_cells.csv'),
                (ndvi_dir / 'ndvi_grid_categories.csv', 'quality/grid_categories.csv'),
                (ndvi_dir / 'metadata.json', 'quality/metadata.json'),
                (ndvi_dir / 'grid_metadata.json', 'quality/grid_metadata.json'),
            ]
        )

        seen: set[str] = set()
        deduped: list[tuple[Path, str]] = []
        for path, arcname in candidates:
            if arcname in seen:
                continue
            seen.add(arcname)
            deduped.append((path, arcname))
        return deduped
