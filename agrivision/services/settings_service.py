from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agrivision.app.schemas.settings import (
    CredentialsUpdateRequest,
    SettingsUpdateRequest,
)
from agrivision.config.runtime import get_runtime_config
from agrivision.config.settings import (
    DEFAULT_CONFIG,
    _deep_merge,
    _remove_yaml_secrets,
    get_config_path,
    load_local_env,
    load_raw_config,
)
from agrivision.services.runtime import mask_env_value, update_env_file


class SettingsService:
    SECRET_ENV_MAP = {
        'shared_username': ('WEATHER_USERNAME', 'IRRIGATION_EMAIL', 'PDM_USERNAME'),
        'shared_password': ('WEATHER_PASSWORD', 'IRRIGATION_PASSWORD', 'PDM_PASSWORD'),
        'openweather_api_key': ('OPENWEATHER_API_KEY',),
        'irrigation_token': ('IRRIGATION_TOKEN',),
        'pdm_token': ('PDM_TOKEN',),
    }

    def __init__(self, config_path: Path | None = None, env_path: Path | None = None) -> None:
        self.config_path = config_path or get_config_path()
        self.env_path = env_path or self.config_path.parent / '.env'

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
        payload = load_raw_config(self.config_path)
        config = _remove_yaml_secrets(_deep_merge(DEFAULT_CONFIG, payload or {}))
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
        return config

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
        payload = _deep_merge(DEFAULT_CONFIG, load_raw_config(self.config_path) or {})

        # do not persist secrets back into config.yaml from the settings UI
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

        self.config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding='utf-8')
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
        return self.get_settings_view()
