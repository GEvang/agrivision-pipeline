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
    _apply_env_overrides,
    _deep_merge,
    get_config_path,
)
from agrivision.services.runtime import mask_env_value, update_env_file


class SettingsService:
    SECRET_ENV_MAP = {
        'weather_username': 'WEATHER_USERNAME',
        'weather_password': 'WEATHER_PASSWORD',
        'openweather_api_key': 'OPENWEATHER_API_KEY',
        'irrigation_email': 'IRRIGATION_EMAIL',
        'irrigation_password': 'IRRIGATION_PASSWORD',
        'irrigation_token': 'IRRIGATION_TOKEN',
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
        payload = yaml.safe_load(self.config_path.read_text(encoding='utf-8')) if self.config_path.exists() else {}
        config = _deep_merge(DEFAULT_CONFIG, payload or {})
        env_values = self._env_values()
        for field_name, env_name in self.SECRET_ENV_MAP.items():
            if env_name in env_values:
                # write to process env proxy config shape
                if field_name == 'weather_username':
                    config.setdefault('weather', {})['username'] = env_values[env_name]
                elif field_name == 'weather_password':
                    config.setdefault('weather', {})['password'] = env_values[env_name]
                elif field_name == 'openweather_api_key':
                    config.setdefault('weather', {})['openweather_api_key'] = env_values[env_name]
                elif field_name == 'irrigation_email':
                    config.setdefault('irrigation', {}).setdefault('auth', {})['email'] = env_values[env_name]
                elif field_name == 'irrigation_password':
                    config.setdefault('irrigation', {}).setdefault('auth', {})['password'] = env_values[env_name]
                elif field_name == 'irrigation_token':
                    config.setdefault('irrigation', {})['token'] = env_values[env_name]
        return _apply_env_overrides(config)

    def get_settings_view(self) -> dict[str, Any]:
        config = self._load_config()
        return {
            'non_secret': {
                'location_name': config.get('location', {}).get('name', ''),
                'weather_base_url': config.get('weather', {}).get('base_url', ''),
                'irrigation_base_url': config.get('irrigation', {}).get('base_url', ''),
                'resize_max_long_edge': config.get('resize', {}).get('max_long_edge', ''),
                'orthophoto_resolution_cm': config.get('orthophoto', {}).get('orthophoto_resolution_cm', ''),
            },
            'credentials': self.masked_credentials(),
            'diagnostics': get_runtime_config(),
        }

    def masked_credentials(self) -> dict[str, str]:
        config = self._load_config()
        values = {
            'weather_username': config.get('weather', {}).get('username', ''),
            'weather_password': config.get('weather', {}).get('password', ''),
            'openweather_api_key': config.get('weather', {}).get('openweather_api_key', ''),
            'irrigation_email': config.get('irrigation', {}).get('auth', {}).get('email', ''),
            'irrigation_password': config.get('irrigation', {}).get('auth', {}).get('password', ''),
            'irrigation_token': config.get('irrigation', {}).get('token', ''),
        }
        return {key: mask_env_value(str(value or '')) for key, value in values.items()}

    def update_non_secret_settings(self, request: SettingsUpdateRequest) -> dict[str, Any]:
        payload = yaml.safe_load(self.config_path.read_text(encoding='utf-8')) if self.config_path.exists() else {}
        payload = payload or {}

        if request.location_name is not None:
            payload.setdefault('location', {})['name'] = request.location_name
        if request.weather_base_url is not None:
            payload.setdefault('weather', {})['base_url'] = request.weather_base_url
        if request.irrigation_base_url is not None:
            payload.setdefault('irrigation', {})['base_url'] = request.irrigation_base_url
        if request.resize_max_long_edge is not None:
            payload.setdefault('resize', {})['max_long_edge'] = request.resize_max_long_edge
        if request.orthophoto_resolution_cm is not None:
            payload.setdefault('orthophoto', {})['orthophoto_resolution_cm'] = request.orthophoto_resolution_cm

        self.config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding='utf-8')
        return self.get_settings_view()

    def update_credentials(self, request: CredentialsUpdateRequest) -> dict[str, Any]:
        values = {
            env_name: value
            for field_name, env_name in self.SECRET_ENV_MAP.items()
            if (value := getattr(request, field_name)) not in (None, '')
        }
        if values:
            update_env_file(self.env_path, values)
        return self.get_settings_view()
