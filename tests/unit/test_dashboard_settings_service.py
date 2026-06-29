from __future__ import annotations

import os
from pathlib import Path

from agrivision.app.schemas.settings import (
    CredentialsUpdateRequest,
    SettingsUpdateRequest,
)
from agrivision.services.settings_service import SettingsService
from agrivision.config import settings as config_settings


def test_settings_masking_and_updates(tmp_path: Path) -> None:
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('weather:\n  base_url: http://example\n', encoding='utf-8')
    env_path = tmp_path / '.env'
    runtime_settings_path = tmp_path / 'runtime' / 'settings.json'
    service = SettingsService(config_path=config_path, env_path=env_path, runtime_settings_path=runtime_settings_path)

    service.update_credentials(CredentialsUpdateRequest(weather_password='secret-pass'))
    masked = service.masked_credentials()
    assert masked['weather_password'].startswith('se')
    assert 'secret-pass' not in masked['weather_password']

    view = service.update_non_secret_settings(SettingsUpdateRequest(location_name='Demo Farm', location_lat=35.26, location_lon=25.6))
    assert view['non_secret']['location_name'] == 'Demo Farm'
    assert view['non_secret']['location_lat'] == 35.26
    assert view['non_secret']['location_lon'] == 25.6
    assert runtime_settings_path.exists()


def test_update_deployment_settings(tmp_path: Path) -> None:
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('app:\n  deployment_mode: local\n', encoding='utf-8')
    service = SettingsService(config_path=config_path, env_path=tmp_path / '.env')

    view = service.update_non_secret_settings(
        SettingsUpdateRequest(
            deployment_mode='self_hosted',
            public_url='https://agrivision.example.com',
            min_free_disk_gb=75,
            max_active_odm_runs=2,
            external_access_protection_confirmed=True,
        )
    )

    assert view['non_secret']['deployment_mode'] == 'self_hosted'
    assert view['non_secret']['public_url'] == 'https://agrivision.example.com'
    assert view['non_secret']['min_free_disk_gb'] == 75
    assert view['non_secret']['max_active_odm_runs'] == 2
    assert view['non_secret']['external_access_protection_confirmed'] is True


def test_update_credentials_refreshes_runtime_environment(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('weather:\n  base_url: http://example\n', encoding='utf-8')
    env_path = tmp_path / '.env'
    service = SettingsService(config_path=config_path, env_path=env_path, runtime_settings_path=tmp_path / 'runtime' / 'settings.json')

    monkeypatch.delenv('WEATHER_USERNAME', raising=False)
    monkeypatch.delenv('WEATHER_PASSWORD', raising=False)

    service.update_credentials(CredentialsUpdateRequest(weather_username='demo-user', weather_password='secret-pass'))

    assert os.environ['WEATHER_USERNAME'] == 'demo-user'
    assert os.environ['WEATHER_PASSWORD'] == 'secret-pass'


def test_settings_service_creates_runtime_settings_on_first_launch(tmp_path: Path) -> None:
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('weather:\n  base_url: http://example\n', encoding='utf-8')
    runtime_settings_path = tmp_path / 'runtime' / 'settings.json'

    service = SettingsService(
        config_path=config_path,
        env_path=tmp_path / '.env',
        runtime_settings_path=runtime_settings_path,
    )

    assert runtime_settings_path.exists()
    assert service.get_settings_view()['non_secret']['settings_file'] == str(runtime_settings_path)


def test_settings_view_uses_default_service_credentials_when_env_is_missing(tmp_path: Path) -> None:
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('weather:\n  base_url: http://example\n', encoding='utf-8')
    service = SettingsService(
        config_path=config_path,
        env_path=tmp_path / '.env',
        runtime_settings_path=tmp_path / 'runtime' / 'settings.json',
    )

    masked = service.masked_credentials()

    assert masked['shared_username'] == 'du***om'
    assert masked['shared_password'] == 'St***1@'
    assert config_settings.DEFAULT_SERVICE_USERNAME == 'dummy@email.com'
