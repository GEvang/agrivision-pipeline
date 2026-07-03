from __future__ import annotations

from pathlib import Path

from agrivision.services import service_control


def test_service_status_reports_missing_repos(tmp_path: Path, monkeypatch) -> None:
    class Weather:
        base_url = 'http://127.0.0.1:8010'

    class Irrigation:
        base_url = 'http://127.0.0.1:8004'
        service_dir = 'OpenAgri-IrrigationManagement'

    class Pdm:
        base_url = 'http://127.0.0.1:8006'
        service_dir = 'OpenAgri-PestAndDiseaseManagement'

    class Settings:
        weather = Weather()
        irrigation = Irrigation()
        pdm = Pdm()

    monkeypatch.setattr(service_control, 'get_settings', lambda: Settings())
    monkeypatch.setattr(service_control, 'project_service_dir', lambda name: tmp_path / name)
    monkeypatch.setattr(service_control, 'check_first_reachable_url', lambda urls: False)
    monkeypatch.setattr(service_control.shutil, 'which', lambda name: None)
    monkeypatch.delenv('APP_CONTAINER_PROJECT_ROOT', raising=False)

    statuses = service_control.service_statuses()

    keyed = {item['key']: item for item in statuses}
    assert set(keyed) == {'weather', 'irrigation', 'pdm', 'odm'}
    assert keyed['weather']['state'] == 'missing'
    assert keyed['weather']['installed_label'] == 'Not installed'
    assert keyed['weather']['connection_label'] == 'Not connected'
    assert keyed['weather']['status_label'] == 'Not installed'
    assert keyed['weather']['primary_action_label'] == 'Install'
    assert keyed['pdm']['state'] == 'missing'
    assert keyed['odm']['installed_label'] == 'Not available'
    assert keyed['odm']['connection_label'] == 'Not tested'


def test_missing_service_repos_reports_only_absent_dirs(tmp_path: Path, monkeypatch) -> None:
    existing_weather = tmp_path / 'OpenAgri-WeatherService'
    existing_weather.mkdir()

    class Weather:
        base_url = 'http://127.0.0.1:8010'

    class Irrigation:
        base_url = 'http://127.0.0.1:8004'
        service_dir = 'OpenAgri-IrrigationManagement'

    class Pdm:
        base_url = 'http://127.0.0.1:8006'
        service_dir = 'OpenAgri-PestAndDiseaseManagement'

    class Settings:
        weather = Weather()
        irrigation = Irrigation()
        pdm = Pdm()

    monkeypatch.setattr(service_control, 'get_settings', lambda: Settings())
    monkeypatch.setattr(service_control, 'project_service_dir', lambda name: tmp_path / name)
    monkeypatch.delenv('APP_CONTAINER_PROJECT_ROOT', raising=False)

    missing = service_control.missing_service_repos()

    assert {item['key'] for item in missing} == {'irrigation', 'pdm'}


def test_service_status_hides_container_only_repo_from_user(tmp_path: Path, monkeypatch) -> None:
    weather_repo = tmp_path / 'OpenAgri-WeatherService'
    weather_repo.mkdir()

    class Weather:
        base_url = 'http://127.0.0.1:8010'

    class Irrigation:
        base_url = 'http://127.0.0.1:8004'
        service_dir = 'OpenAgri-IrrigationManagement'

    class Pdm:
        base_url = 'http://127.0.0.1:8006'
        service_dir = 'OpenAgri-PestAndDiseaseManagement'

    class Settings:
        weather = Weather()
        irrigation = Irrigation()
        pdm = Pdm()

    monkeypatch.setattr(service_control, 'get_settings', lambda: Settings())
    monkeypatch.setattr(service_control, 'project_service_dir', lambda name: tmp_path / name)
    monkeypatch.setattr(service_control, 'check_first_reachable_url', lambda urls: False)
    monkeypatch.setattr(service_control, 'installed_service_state', lambda service_key: {})
    monkeypatch.setenv('APP_CONTAINER_PROJECT_ROOT', '/app')

    statuses = service_control.service_statuses()
    keyed = {item['key']: item for item in statuses}

    assert keyed['weather']['repo_exists'] is False
    assert keyed['weather']['installed_label'] == 'Not installed'
    assert keyed['weather']['status_label'] == 'Not installed'
    assert keyed['weather']['primary_action'] == ''
    assert keyed['weather']['controls_available'] is False
    assert 'host helper' in keyed['weather']['controls_reason']

    missing = service_control.missing_service_repos()
    assert {item['key'] for item in missing} == {'weather', 'irrigation', 'pdm'}


def test_odm_status_reports_available_with_container_socket(monkeypatch) -> None:
    monkeypatch.setenv('APP_CONTAINER_PROJECT_ROOT', '/app')
    monkeypatch.setattr(service_control.shutil, 'which', lambda name: '/usr/bin/docker')

    class FakeSocketPath:
        def exists(self) -> bool:
            return True

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        return None

    monkeypatch.setattr(service_control, 'Path', lambda value: FakeSocketPath())
    monkeypatch.setattr(service_control.subprocess, 'run', fake_run)

    status = next(item for item in service_control.service_statuses() if item['key'] == 'odm')

    assert status['installed_label'] == 'Available'
    assert status['connection_label'] == 'Available'
    assert status['state'] == 'ok'
