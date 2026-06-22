from __future__ import annotations

from agrivision.integrations.pdm.adapter import (
    _extract_risk_entries,
    _find_crop,
    _find_threat_model,
    _summarize_risks,
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
