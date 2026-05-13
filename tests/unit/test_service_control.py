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

    statuses = service_control.service_statuses()

    assert {item['key'] for item in statuses} == {'weather', 'irrigation', 'pdm'}
    assert all(item['state'] == 'missing' for item in statuses)
    assert all(item['repo_exists'] is False for item in statuses)
