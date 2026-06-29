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

    statuses = service_control.service_statuses()

    keyed = {item['key']: item for item in statuses}
    assert set(keyed) == {'weather', 'irrigation', 'pdm', 'odm'}
    assert keyed['weather']['state'] == 'missing'
    assert keyed['weather']['installed_label'] == 'Not installed'
    assert keyed['weather']['connection_label'] == 'Not connected'
    assert keyed['pdm']['state'] == 'missing'
    assert keyed['odm']['installed_label'] == 'Not available'
    assert keyed['odm']['connection_label'] == 'Not tested'
