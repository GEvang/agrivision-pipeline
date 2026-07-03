from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agrivision.app.schemas.settings import (
    CredentialsUpdateRequest,
    SettingsUpdateRequest,
)
from agrivision.config.runtime import get_runtime_config
from agrivision.config.settings import (
    DEFAULT_CONFIG,
    _apply_local_service_defaults,
    _deep_merge,
    _remove_yaml_secrets,
    get_config_path,
    get_runtime_settings_path,
    load_local_env,
    load_raw_config,
    load_runtime_settings,
)
from agrivision.services import service_control
from agrivision.services.irrigation import runtime as irrigation_runtime
from agrivision.services.pdm import runtime as pdm_runtime
from agrivision.services.runtime import mask_env_value, update_env_file
from agrivision.services.weather import client as weather_client


class SettingsService:
    SECRET_ENV_MAP = {
        'shared_username': ('WEATHER_USERNAME', 'IRRIGATION_EMAIL', 'PDM_USERNAME'),
        'shared_password': ('WEATHER_PASSWORD', 'IRRIGATION_PASSWORD', 'PDM_PASSWORD'),
        'openweather_api_key': ('OPENWEATHER_API_KEY',),
        'irrigation_token': ('IRRIGATION_TOKEN',),
        'pdm_token': ('PDM_TOKEN',),
    }

    def __init__(
        self,
        config_path: Path | None = None,
        env_path: Path | None = None,
        runtime_settings_path: Path | None = None,
    ) -> None:
        self.config_path = config_path or get_config_path()
        self.runtime_settings_path = runtime_settings_path or get_runtime_settings_path()
        self.env_path = env_path or self.runtime_settings_path.with_name('app-secrets.env')
        self.ensure_runtime_settings_file()

    def ensure_runtime_settings_file(self) -> None:
        payload = load_runtime_settings(self.runtime_settings_path)
        merged = _remove_yaml_secrets(_deep_merge(DEFAULT_CONFIG, payload or {}))
        self.runtime_settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_settings_path.write_text(json.dumps(merged, indent=2), encoding='utf-8')

    def _env_values(self) -> dict[str, str]:
        if not self.env_path.exists():
            return {}
        data: dict[str, str] = {}
        for raw_line in self.env_path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            data[key] = value.strip().strip('"').strip("'")
        return data

    def _load_config(self) -> dict[str, Any]:
        load_local_env(self.env_path)
        file_payload = load_raw_config(self.config_path)
        runtime_payload = load_runtime_settings(self.runtime_settings_path)
        config = _deep_merge(DEFAULT_CONFIG, file_payload or {})
        config = _remove_yaml_secrets(_deep_merge(config, runtime_payload or {}))
        env_values = self._env_values()
        mapping = {
            'WEATHER_USERNAME': ('weather', 'username'),
            'WEATHER_PASSWORD': ('weather', 'password'),
            'OPENWEATHER_API_KEY': ('weather', 'openweather_api_key'),
            'IRRIGATION_EMAIL': ('irrigation', 'auth', 'email'),
            'IRRIGATION_PASSWORD': ('irrigation', 'auth', 'password'),
            'IRRIGATION_TOKEN': ('irrigation', 'token'),
            'PDM_USERNAME': ('pdm', 'auth', 'username'),
            'PDM_PASSWORD': ('pdm', 'auth', 'password'),
            'PDM_TOKEN': ('pdm', 'token'),
        }
        for env_name, path in mapping.items():
            value = env_values.get(env_name)
            if value in (None, ''):
                continue
            current = config
            for key in path[:-1]:
                current = current.setdefault(key, {})
            current[path[-1]] = value
        return _apply_local_service_defaults(config)

    def get_settings_view(self) -> dict[str, Any]:
        config = self._load_config()
        return {
            'non_secret': {
                'location_name': config.get('location', {}).get('name', ''),
                'location_lat': config.get('location', {}).get('lat', ''),
                'location_lon': config.get('location', {}).get('lon', ''),
                'weather_base_url': config.get('weather', {}).get('base_url', ''),
                'irrigation_base_url': config.get('irrigation', {}).get('base_url', ''),
                'pdm_base_url': config.get('pdm', {}).get('base_url', ''),
                'pdm_enabled_by_default': config.get('pdm', {}).get('enabled_by_default', True),
                'pdm_default_crop': config.get('pdm', {}).get('default_crop', 'grapevine'),
                'pdm_default_model_key': config.get('pdm', {}).get('default_model_key', 'grapevine_powdery_mildew_risk_v1'),
                'resize_max_long_edge': config.get('resize', {}).get('max_long_edge', ''),
                'orthophoto_resolution_cm': config.get('orthophoto', {}).get('orthophoto_resolution_cm', ''),
                'settings_file': str(self.runtime_settings_path),
                'deployment_mode': config.get('app', {}).get('deployment_mode', 'local'),
                'public_url': config.get('app', {}).get('public_url', ''),
                'min_free_disk_gb': config.get('app', {}).get('min_free_disk_gb', 50),
                'max_active_odm_runs': config.get('app', {}).get('max_active_odm_runs', 1),
                'external_access_protection_confirmed': config.get('app', {}).get('external_access_protection_confirmed', False),
            },
            'credentials': self.masked_credentials(),
            'diagnostics': get_runtime_config(),
        }

    def masked_credentials(self) -> dict[str, str]:
        config = self._load_config()
        shared_username = (
            config.get('irrigation', {}).get('auth', {}).get('email')
            or config.get('pdm', {}).get('auth', {}).get('username')
            or config.get('weather', {}).get('username', '')
        )
        shared_password = (
            config.get('irrigation', {}).get('auth', {}).get('password')
            or config.get('pdm', {}).get('auth', {}).get('password')
            or config.get('weather', {}).get('password', '')
        )
        values = {
            'shared_username': shared_username,
            'shared_password': shared_password,
            'openweather_api_key': config.get('weather', {}).get('openweather_api_key', ''),
            'weather_username': config.get('weather', {}).get('username', ''),
            'weather_password': config.get('weather', {}).get('password', ''),
            'irrigation_email': config.get('irrigation', {}).get('auth', {}).get('email', ''),
            'irrigation_password': config.get('irrigation', {}).get('auth', {}).get('password', ''),
            'pdm_username': config.get('pdm', {}).get('auth', {}).get('username', ''),
            'pdm_password': config.get('pdm', {}).get('auth', {}).get('password', ''),
        }
        return {key: mask_env_value(str(value or '')) for key, value in values.items()}

    def update_non_secret_settings(self, request: SettingsUpdateRequest) -> dict[str, Any]:
        payload = _deep_merge(DEFAULT_CONFIG, load_runtime_settings(self.runtime_settings_path) or {})

        # do not persist secrets back into runtime settings from the settings UI
        payload.setdefault('weather', {}).pop('username', None)
        payload.setdefault('weather', {}).pop('password', None)
        payload.setdefault('weather', {}).pop('openweather_api_key', None)
        payload.setdefault('irrigation', {}).setdefault('auth', {}).pop('email', None)
        payload.setdefault('irrigation', {}).setdefault('auth', {}).pop('password', None)
        payload.setdefault('irrigation', {}).pop('token', None)
        payload.setdefault('pdm', {}).setdefault('auth', {}).pop('username', None)
        payload.setdefault('pdm', {}).setdefault('auth', {}).pop('password', None)
        payload.setdefault('pdm', {}).pop('token', None)

        if request.location_name is not None:
            payload.setdefault('location', {})['name'] = request.location_name
        if request.location_lat is not None:
            payload.setdefault('location', {})['lat'] = request.location_lat
        if request.location_lon is not None:
            payload.setdefault('location', {})['lon'] = request.location_lon
        if request.weather_base_url is not None:
            payload.setdefault('weather', {})['base_url'] = request.weather_base_url
        if request.irrigation_base_url is not None:
            payload.setdefault('irrigation', {})['base_url'] = request.irrigation_base_url
        if request.pdm_base_url is not None:
            payload.setdefault('pdm', {})['base_url'] = request.pdm_base_url
        if request.pdm_enabled_by_default is not None:
            payload.setdefault('pdm', {})['enabled_by_default'] = request.pdm_enabled_by_default
        if request.pdm_default_crop is not None:
            payload.setdefault('pdm', {})['default_crop'] = request.pdm_default_crop
        if request.pdm_default_model_key is not None:
            payload.setdefault('pdm', {})['default_model_key'] = request.pdm_default_model_key
        if request.resize_max_long_edge is not None:
            payload.setdefault('resize', {})['max_long_edge'] = request.resize_max_long_edge
        if request.orthophoto_resolution_cm is not None:
            payload.setdefault('orthophoto', {})['orthophoto_resolution_cm'] = request.orthophoto_resolution_cm
        if request.deployment_mode is not None:
            payload.setdefault('app', {})['deployment_mode'] = request.deployment_mode
        if request.public_url is not None:
            payload.setdefault('app', {})['public_url'] = request.public_url
        if request.min_free_disk_gb is not None:
            payload.setdefault('app', {})['min_free_disk_gb'] = request.min_free_disk_gb
        if request.max_active_odm_runs is not None:
            payload.setdefault('app', {})['max_active_odm_runs'] = request.max_active_odm_runs
        if request.external_access_protection_confirmed is not None:
            payload.setdefault('app', {})['external_access_protection_confirmed'] = request.external_access_protection_confirmed

        self.runtime_settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_settings_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        return self.get_settings_view()

    def update_credentials(self, request: CredentialsUpdateRequest) -> dict[str, Any]:
        shared_username = (
            request.shared_username
            or request.irrigation_email
            or request.pdm_username
            or request.weather_username
        )
        shared_password = (
            request.shared_password
            or request.irrigation_password
            or request.pdm_password
            or request.weather_password
        )

        values: dict[str, str] = {}
        if shared_username not in (None, ''):
            for env_name in self.SECRET_ENV_MAP['shared_username']:
                values[env_name] = shared_username
        if shared_password not in (None, ''):
            for env_name in self.SECRET_ENV_MAP['shared_password']:
                values[env_name] = shared_password
        if request.openweather_api_key not in (None, ''):
            values['OPENWEATHER_API_KEY'] = request.openweather_api_key
        if request.irrigation_token not in (None, ''):
            values['IRRIGATION_TOKEN'] = request.irrigation_token
        if request.pdm_token not in (None, ''):
            values['PDM_TOKEN'] = request.pdm_token
        if values:
            update_env_file(self.env_path, values)
            for env_name, value in values.items():
                __import__('os').environ[env_name] = value
            self._sync_changed_service_credentials(values)
        return self.get_settings_view()

    def _sync_changed_service_credentials(self, values: dict[str, str]) -> None:
        service_keys: list[str] = []
        if any(
            env_name in values
            for env_name in ('WEATHER_USERNAME', 'WEATHER_PASSWORD', 'OPENWEATHER_API_KEY')
        ):
            weather_client.prepare_weather_repo_and_env()
            service_keys.append('weather')
        if any(
            env_name in values
            for env_name in ('IRRIGATION_EMAIL', 'IRRIGATION_PASSWORD', 'IRRIGATION_TOKEN')
        ):
            irrigation_runtime.prepare_repo_and_env()
            service_keys.append('irrigation')
        if any(
            env_name in values
            for env_name in ('PDM_USERNAME', 'PDM_PASSWORD', 'PDM_TOKEN')
        ):
            pdm_runtime.prepare_repo_and_env()
            service_keys.append('pdm')

        controls = service_control.service_controls()
        if not controls.get('available'):
            return

        for service_key in service_keys:
            try:
                service_control.restart_service(service_key, timeout_seconds=240)
            except Exception:
                # Persisting credentials should still succeed even if the companion service
                # cannot be restarted immediately. The next explicit start/restart will
                # pick up the synchronized .env file.
                continue
