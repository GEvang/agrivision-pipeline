from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from agrivision.app.schemas.runs import RunCreateRequest
from agrivision.config import get_project_root, load_config
from agrivision.services.storage_service import StorageService


class PreflightService:
    def __init__(self, storage: StorageService | None = None) -> None:
        self.storage = storage or StorageService()

    def validate(self, request: RunCreateRequest) -> dict[str, object]:
        checks: list[dict[str, str]] = []
        blockers: list[str] = []
        warnings: list[str] = []

        manifest = self.storage.read_json(self.storage.upload_dir(request.upload_run_id) / 'manifest.json', default={})
        rgb_count = len(manifest.get('rgb_files', []))
        mapir_count = len(manifest.get('mapir_files', []))
        if rgb_count < 2:
            blockers.append('Upload must contain at least 2 RGB images.')
            checks.append(self._check('RGB images', 'error', f'{rgb_count} found'))
        else:
            checks.append(self._check('RGB images', 'ok', f'{rgb_count} found'))
        if mapir_count < 2:
            warnings.append('MAPIR upload has fewer than 2 images; vegetation index may fall back to RGB/pseudo mode.')
            checks.append(self._check('MAPIR images', 'warn', f'{mapir_count} found'))
        else:
            checks.append(self._check('MAPIR images', 'ok', f'{mapir_count} found'))

        config = load_config()
        if request.selected_steps.run_odm:
            disk_check = self._disk_space_check(config)
            checks.append(disk_check)
            if disk_check['state'] == 'error':
                blockers.append(disk_check['detail'])
            docker_check = self._docker_check()
            checks.append(docker_check)
            if docker_check['state'] != 'ok':
                blockers.append('Docker must be running to run ODM.')
        else:
            source_run_id = request.parameters.source_orthophoto_run_id
            ortho_checks = self._saved_orthophoto_checks(source_run_id) if source_run_id else self._existing_orthophoto_checks(config)
            checks.extend(ortho_checks)
            if not any(item['state'] == 'ok' for item in ortho_checks):
                blockers.append('Existing orthophoto mode needs an RGB or MAPIR orthophoto already generated.')

        if request.selected_steps.fetch_weather:
            self._append_service_check(checks, blockers, 'Weather', config.get('weather', {}).get('base_url', ''))

        if request.selected_steps.run_irrigation:
            self._append_service_check(checks, warnings, 'Irrigation', config.get('irrigation', {}).get('base_url', ''))

        if request.selected_steps.run_pdm:
            self._append_service_check(checks, blockers, 'PDM', config.get('pdm', {}).get('base_url', ''))

        return {
            'ok': not blockers,
            'blockers': blockers,
            'warnings': warnings,
            'checks': checks,
        }

    def _check(self, name: str, state: str, detail: str) -> dict[str, str]:
        return {'name': name, 'state': state, 'detail': detail}

    def _docker_check(self) -> dict[str, str]:
        try:
            result = subprocess.run(
                ['docker', 'version', '--format', '{{.Server.Version}}'],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return self._check('Docker', 'error', 'Unavailable')
        version = result.stdout.strip()
        if result.returncode == 0 and version:
            return self._check('Docker', 'ok', version)
        return self._check('Docker', 'error', 'Daemon unavailable')

    def _disk_space_check(self, config: dict) -> dict[str, str]:
        app_cfg = config.get('app', {}) if isinstance(config.get('app'), dict) else {}
        min_free_gb = self._as_int(app_cfg.get('min_free_disk_gb'), 50)
        project_root = get_project_root()
        try:
            usage = shutil.disk_usage(project_root)
        except OSError:
            return self._check('Free disk space', 'warn', 'Could not check disk space')
        free_gb = usage.free / (1024**3)
        detail = f'{free_gb:.1f} GB free; minimum {min_free_gb} GB'
        if free_gb < min_free_gb:
            return self._check('Free disk space', 'error', detail)
        warn_threshold = max(min_free_gb * 1.5, min_free_gb + 20)
        if free_gb < warn_threshold:
            return self._check('Free disk space', 'warn', detail)
        return self._check('Free disk space', 'ok', detail)

    def _as_int(self, value: object, fallback: int) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return fallback

    def _url_check(self, name: str, base_url: str) -> dict[str, str]:
        for path in ('/health', '/docs', '/openapi.json'):
            url = base_url.rstrip('/') + path
            try:
                request = UrlRequest(url, method='GET')
                with urlopen(request, timeout=1.0) as response:
                    if 200 <= response.status < 500:
                        state = 'ok' if response.status < 400 else 'warn'
                        return self._check(name, state, f'HTTP {response.status}')
            except (OSError, URLError):
                continue
        return self._check(name, 'error', 'Not reachable')

    def _append_service_check(
        self,
        checks: list[dict[str, str]],
        messages: list[str],
        name: str,
        base_url: str,
    ) -> None:
        check = self._url_check(name, base_url)
        checks.append(check)
        if check['state'] == 'error':
            messages.append(f'{name} service is not reachable at {base_url}.')

    def _existing_orthophoto_checks(self, config: dict) -> list[dict[str, str]]:
        project_root = get_project_root()
        paths = config.get('paths', {})
        candidates = (
            ('RGB orthophoto', project_root / paths.get('odm_project_root_rgb', 'data/odm_project_rgb') / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif'),
            ('MAPIR orthophoto', project_root / paths.get('odm_project_root_mapir', 'data/odm_project_mapir') / 'project' / 'odm_orthophoto' / 'odm_orthophoto.tif'),
        )
        checks: list[dict[str, str]] = []
        for name, path in candidates:
            state = 'ok' if Path(path).exists() else 'error'
            detail = 'Found' if state == 'ok' else 'Missing'
            checks.append(self._check(name, state, detail))
        return checks

    def _saved_orthophoto_checks(self, run_id: str) -> list[dict[str, str]]:
        status = self.storage.read_json(self.storage.run_dir(run_id) / 'status.json', default={})
        outputs = status.get('outputs', {}) if isinstance(status, dict) else {}
        candidates = (
            ('Saved RGB orthophoto', outputs.get('orthophoto_rgb')),
            ('Saved MAPIR orthophoto', outputs.get('orthophoto_mapir')),
        )
        checks: list[dict[str, str]] = []
        for name, path in candidates:
            exists = bool(path) and Path(str(path)).exists()
            checks.append(self._check(name, 'ok' if exists else 'error', 'Found' if exists else 'Missing'))
        return checks
