from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from agrivision.services.run_service import RunService
from agrivision.services.storage_service import StorageService


class RunExportService:
    def __init__(self, run_service: RunService | None = None, storage: StorageService | None = None) -> None:
        self.run_service = run_service or RunService()
        self.storage = storage or self.run_service.storage

    def build_package(self, run_id: str) -> Path:
        run = self.run_service.load_run(run_id)
        workspace = self.run_service.workspace_for_run(run_id)
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
            report_html = run.outputs.get('report_html')
            if report_html:
                report_path = Path(report_html)
                if report_path.exists() and report_path.is_file():
                    archive.writestr('report/report.html', self._packaged_report_html(report_path))
                    manifest['files'].append('report/report.html')  # type: ignore[union-attr]
            for path, arcname in self._artifact_candidates(run_id):
                if not path.exists() or not path.is_file():
                    continue
                archive.write(path, arcname)
                manifest['files'].append(arcname)  # type: ignore[union-attr]
            for path, arcname in self._report_asset_candidates(workspace.output_root):
                if not path.exists() or not path.is_file():
                    continue
                archive.write(path, arcname)
                manifest['files'].append(arcname)  # type: ignore[union-attr]
            archive.writestr('manifest.json', json.dumps(manifest, indent=2, sort_keys=True))
            archive.writestr(
                'metadata/run_metadata.jsonld',
                json.dumps(self._run_jsonld(run.run_id, manifest), indent=2, sort_keys=True),
            )

        return package_path

    def _run_jsonld(self, run_id: str, manifest: dict[str, object]) -> dict[str, object]:
        run = self.run_service.load_run(run_id)
        files = [str(item) for item in manifest.get('files', []) if str(item).strip()]
        artifact_nodes = [
            {
                '@id': f'urn:openagri:agrivision:artifact:{run.run_id}:{index + 1}',
                '@type': 'DigitalDocument',
                'name': arcname,
                'contentUrl': arcname,
                'encodingFormat': self._encoding_format(arcname),
            }
            for index, arcname in enumerate(files)
        ]
        selected_steps = [
            {'name': key, 'value': value}
            for key, value in run.selected_steps.model_dump().items()
        ]
        parameters = [
            {'name': key, 'value': value}
            for key, value in run.parameters.items()
            if value is not None
        ]
        return {
            '@context': {
                'schema': 'https://schema.org/',
                'ocsm': 'https://w3id.org/openagri/ocsm#',
                'AgriParcel': 'ocsm:AgriParcel',
                'AgriculturalDataset': 'ocsm:AgriculturalDataset',
                'DigitalDocument': 'schema:DigitalDocument',
                'SoftwareApplication': 'schema:SoftwareApplication',
                'actionStatus': 'schema:actionStatus',
                'contentUrl': 'schema:contentUrl',
                'dateCreated': 'schema:dateCreated',
                'dateModified': 'schema:dateModified',
                'encodingFormat': 'schema:encodingFormat',
                'hasPart': 'schema:hasPart',
                'identifier': 'schema:identifier',
                'name': 'schema:name',
                'softwareVersion': 'schema:softwareVersion',
            },
            '@id': f'urn:openagri:agrivision:run:{run.run_id}',
            '@type': ['SoftwareApplication', 'ocsm:AgriVisionRun'],
            'identifier': run.run_id,
            'name': run.run_name or run.dataset_name,
            'softwareVersion': '1.0.0',
            'actionStatus': run.status,
            'dateCreated': run.created_at.isoformat(),
            'dateModified': run.updated_at.isoformat() if run.updated_at else None,
            'dataset': {
                '@id': f'urn:openagri:agrivision:dataset:{run.run_id}',
                '@type': 'AgriculturalDataset',
                'name': run.dataset_name,
                'identifier': Path(run.input_path).name,
            },
            'selectedSteps': selected_steps,
            'parameters': parameters,
            'hasPart': artifact_nodes,
        }

    def _encoding_format(self, arcname: str) -> str:
        suffix = Path(arcname).suffix.lower()
        return {
            '.csv': 'text/csv',
            '.html': 'text/html',
            '.json': 'application/json',
            '.jsonld': 'application/ld+json',
            '.log': 'text/plain',
            '.png': 'image/png',
            '.tif': 'image/tiff',
            '.tiff': 'image/tiff',
        }.get(suffix, 'application/octet-stream')

    def _packaged_report_html(self, report_path: Path) -> str:
        html = report_path.read_text(encoding='utf-8')
        base_tag = '<base href="../report-assets/">'
        if '</head>' in html:
            return html.replace('</head>', f'  {base_tag}\n</head>', 1)
        return base_tag + html

    def _report_asset_candidates(self, output_root: Path) -> list[tuple[Path, str]]:
        if not output_root.exists():
            return []
        candidates: list[tuple[Path, str]] = []
        for path in sorted(output_root.rglob('*')):
            if not path.is_file():
                continue
            relative = path.relative_to(output_root).as_posix()
            candidates.append((path, f'report-assets/{relative}'))
        return candidates

    def _artifact_candidates(self, run_id: str) -> list[tuple[Path, str]]:
        run = self.run_service.load_run(run_id)
        workspace = self.run_service.workspace_for_run(run_id)
        run_dir = self.storage.layout.runs_root / run_id
        candidates: list[tuple[Path, str]] = [
            (run_dir / 'status.json', 'run/status.json'),
            (run_dir / 'params.json', 'run/params.json'),
            (run_dir / 'outputs.json', 'run/outputs.json'),
            (run_dir / 'artifacts.json', 'run/artifacts.json'),
            (Path(run.logs_path), 'run/run.log'),
        ]

        for key, arcname in (
            ('vegetation_index_metadata', 'quality/metadata.json'),
            ('grid_metadata', 'quality/grid_metadata.json'),
            ('disease_risk_summary', 'risk/disease_risk_summary.json'),
            ('vegetation_index_tif', 'rasters/vegetation_index.tif'),
            ('orthophoto_rgb', 'rasters/orthophoto_rgb.tif'),
            ('orthophoto_mapir', 'rasters/orthophoto_mapir.tif'),
            ('orthophoto_thermal', 'rasters/orthophoto_thermal.tif'),
        ):
            value = run.outputs.get(key)
            if value:
                candidates.append((Path(value), arcname))

        candidates.extend(
            [
                (workspace.vegetation_index_output / 'vegetation_index_color.png', 'quality/vegetation_index.png'),
                (workspace.vegetation_index_output / 'vegetation_index_grid_overlay.png', 'quality/grid_overlay.png'),
                (workspace.vegetation_index_output / 'vegetation_index_grid_cells.csv', 'quality/grid_cells.csv'),
                (workspace.vegetation_index_output / 'vegetation_index_grid_categories.csv', 'quality/grid_categories.csv'),
                (workspace.vegetation_index_output / 'metadata.json', 'quality/metadata.json'),
                (workspace.vegetation_index_output / 'grid_metadata.json', 'quality/grid_metadata.json'),
                (workspace.vegetation_index_output / 'disease_risk' / 'summary.json', 'risk/disease_risk_summary.json'),
            ]
        )
        risk_dir = workspace.vegetation_index_output / 'disease_risk'
        if risk_dir.exists():
            for path in sorted(risk_dir.glob('*_overlay.png')):
                candidates.append((path, f'risk/{path.name}'))
            for path in sorted(risk_dir.glob('*_cells.csv')):
                candidates.append((path, f'risk/{path.name}'))

        seen: set[str] = set()
        deduped: list[tuple[Path, str]] = []
        for path, arcname in candidates:
            if arcname in seen:
                continue
            seen.add(arcname)
            deduped.append((path, arcname))
        return deduped
