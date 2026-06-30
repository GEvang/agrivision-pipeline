from __future__ import annotations

from pathlib import Path

from agrivision.integrations.pdm.adapter import (
    _extract_risk_entries,
    _find_crop,
    _find_threat_model,
    _summarize_risks,
    collect_pdm_snapshot,
)


def test_extracts_fuzzy_jsonld_risk_score_and_class() -> None:
    payload = {
        '@graph': [
            {
                'observedProperty': {'name': 'Uncinula necator'},
                'hasMember': [
                    {
                        'phenomenonTime': '2026-05-25',
                        'hasSimpleResult': '88.9',
                        'riskClass': 'Critical',
                        'meta': 'best_rule=High',
                    }
                ],
            }
        ]
    }

    entries = _extract_risk_entries(payload)
    risk_level, reasons, _, stats = _summarize_risks(entries, {'risk_rules': [], 'default_recommendation': 'Monitor'})

    assert entries[0]['risk_score'] == '88.9'
    assert risk_level == 'Critical'
    assert stats['highest_score'] == '88.9'
    assert any('Critical' in reason for reason in reasons)


def test_matches_openagri_crop_and_threat_model_aliases() -> None:
    crop = _find_crop([{'id': '1', 'name': 'Vineyard'}], 'vineyard')
    threat = _find_threat_model(
        [{'id': '2', 'scientific_name': 'Uncinula necator', 'common_name': 'Uncinula necator'}],
        {
            'label': 'Grapevine Powdery Mildew',
            'organism_name': 'Erysiphe necator',
            'fuzzy_scientific_names': ['Uncinula necator', 'Erysiphe necator'],
        },
    )

    assert crop == {'id': '1', 'name': 'Vineyard'}
    assert threat and threat['id'] == '2'


def test_collect_pdm_snapshot_logs_in_before_risk_index(monkeypatch, tmp_path: Path) -> None:
    class FakeClient:
        login_called = False

        def __init__(self, config) -> None:
            self.config = config

        def login(self) -> dict[str, bool]:
            self.login_called = True
            return {'authenticated': True}

        def calculate_risk_index(self, **kwargs):
            assert self.login_called is True
            return {'entries': []}

    monkeypatch.setattr('agrivision.integrations.pdm.adapter.PdmClient', FakeClient)
    monkeypatch.setattr('agrivision.integrations.pdm.adapter.get_pdm_service_config', lambda: object())
    monkeypatch.setattr(
        'agrivision.integrations.pdm.adapter.get_pdm_model',
        lambda _key: {
            'key': 'grapevine_powdery_mildew_risk_v1',
            'crop': 'grapevine',
            'label': 'Grapevine Powdery Mildew',
            'organism_name': 'Erysiphe necator',
            'eppo_code': 'UNCINE',
            'calculation_type': 'risk_index',
            'risk_rules': [],
            'default_recommendation': 'Monitor',
        },
    )
    monkeypatch.setattr(
        'agrivision.integrations.pdm.adapter.get_models_for_crop',
        lambda _crop: [{'key': 'grapevine_powdery_mildew_risk_v1'}],
    )
    monkeypatch.setattr(
        'agrivision.integrations.pdm.adapter.bootstrap_pdm_context',
        lambda *args, **kwargs: {
            'service': {'reachable': True},
            'runtime': {'ready': True},
            'parcel': {'parcel_id': '12'},
            'resolved_model': {'remote_id': 'model-5'},
            'artifact_path': str(tmp_path / 'bootstrap.json'),
            'dataset_csv_artifact': '',
            'dataset_upload_id': '',
            'dataset_upload_succeeded': False,
            'dataset_upload': {},
        },
    )
    monkeypatch.setattr(
        'agrivision.integrations.pdm.adapter.write_pdm_artifact',
        lambda *args, **kwargs: str(tmp_path / 'artifact.json'),
    )

    summary = collect_pdm_snapshot(None, artifact_dir=tmp_path)

    assert summary['status'] == 'success'
    assert summary['remote_parcel_id'] == '12'
    assert summary['remote_model_id'] == 'model-5'
