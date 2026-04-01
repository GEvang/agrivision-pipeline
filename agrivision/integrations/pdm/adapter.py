from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agrivision.config.settings import get_project_root, get_settings
from agrivision.services.pdm.bootstrap import bootstrap_pdm_context
from agrivision.services.pdm.catalog import get_pdm_model, get_models_for_crop
from agrivision.integrations.pdm.client import PdmClient, get_pdm_service_config, write_pdm_artifact


RISK_ORDER = {'low': 1, 'moderate': 2, 'medium': 2, 'high': 3}


def _artifact_dir() -> Path:
    settings = get_settings()
    path = get_project_root() / (settings.paths.output_root or 'output') / 'pdm'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(name: str, payload: dict[str, Any]) -> str:
    path = _artifact_dir() / name
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return str(path)


def _extract_risk_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    def _append_entry(item: dict[str, Any], parent: dict[str, Any] | None = None) -> None:
        timestamp = item.get('saref:hasTimestamp') or item.get('timestamp') or item.get('date') or item.get('datetime') or ''
        risk_level = (
            item.get('ocsm:hasRiskLevel')
            or item.get('risk_level')
            or item.get('probability_value')
            or item.get('value')
            or item.get('level')
            or item.get('label')
            or ''
        )
        if not timestamp and not risk_level:
            return
        parent = parent or {}
        entries.append(
            {
                'timestamp': str(timestamp or ''),
                'risk_level': str(risk_level or ''),
                'model_id': parent.get('@id') or parent.get('id') or item.get('model_id') or '',
                'eppo_code': parent.get('fsm:eppoCode') or parent.get('eppo_code') or item.get('eppo_code') or '',
                'description': parent.get('foodie:description') or parent.get('description') or item.get('description') or '',
            }
        )

    if not isinstance(payload, dict):
        return entries

    graph = payload.get('@graph', [])
    if isinstance(graph, list):
        for item in graph:
            if not isinstance(item, dict):
                continue
            risks = item.get('ocsm:hasPredictedInfestationRisks') or item.get('ocsm:hasPredictedInfestations') or []
            if isinstance(risks, list):
                for risk in risks:
                    if isinstance(risk, dict):
                        _append_entry(risk, item)

    for key in ('entries', 'elements', 'items', 'results', 'data', 'risks'):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _append_entry(item)

    if not entries:
        _append_entry(payload)
    return entries

def _summarize_risks(entries: list[dict[str, Any]], model: dict[str, Any], raw_payload: dict[str, Any] | None = None) -> tuple[str | None, list[str], str, dict[str, Any]]:
    if not entries:
        reasons = ['PDM service returned no explicit risk entries for the selected model and parcel; treating this as no reported risk matches for the selected period.']
        raw_text = str((raw_payload or {}).get('raw_text') or '').strip()
        if raw_text:
            reasons.append(f'Remote response: {raw_text[:200]}')
        return 'Low', reasons, model.get('default_recommendation', 'Maintain routine monitoring.'), {
            'counts': {'Low': 0, 'Moderate': 0, 'High': 0}, 'latest_timestamp': None, 'highest_timestamp': None
        }
    counts: dict[str, int] = {}
    highest = None
    latest_ts = None
    for item in entries:
        level = str(item.get('risk_level') or '').strip() or 'Unknown'
        normalized = 'Moderate' if level.lower() == 'medium' else level.title()
        counts[normalized] = counts.get(normalized, 0) + 1
        ts = item.get('timestamp')
        if ts and (latest_ts is None or str(ts) > str(latest_ts)):
            latest_ts = str(ts)
        compare_level = normalized.lower()
        if highest is None or RISK_ORDER.get(compare_level, 0) > RISK_ORDER.get(str(highest.get('risk_level')).lower(), 0):
            item = dict(item)
            item['risk_level'] = normalized
            highest = item
    risk_level = str(highest.get('risk_level')).title() if highest else None
    reasons = [f"Remote PDM returned {counts.get('High', 0)} High, {counts.get('Moderate', 0)} Moderate, {counts.get('Low', 0)} Low risk observations."]
    if highest and highest.get('timestamp'):
        reasons.append(f"Highest remote risk observed at {highest['timestamp']}.")
    recommendation = model.get('default_recommendation', 'Maintain routine monitoring.')
    for rule in model.get('risk_rules', []):
        if str(rule.get('label', '')).lower() == str(risk_level or '').lower():
            recommendation = str(rule.get('recommendation') or recommendation)
            break
    return risk_level, reasons, recommendation, {
        'counts': counts,
        'latest_timestamp': latest_ts,
        'highest_timestamp': highest.get('timestamp') if highest else None,
    }

def collect_pdm_snapshot(
    weather_summary: dict[str, Any] | None,
    *,
    enabled: bool = True,
    crop: str | None = None,
    model_key: str | None = None,
) -> dict[str, Any]:
    resolved_model = get_pdm_model(model_key)
    resolved_crop = (crop or resolved_model['crop']).strip().lower()
    available_for_crop = [item['key'] for item in get_models_for_crop(resolved_crop)]
    base_summary: dict[str, Any] = {
        'enabled': enabled,
        'status': 'disabled' if not enabled else 'pending',
        'service_status': {},
        'runtime_status': {},
        'crop': resolved_crop,
        'selected_model_key': resolved_model['key'],
        'available_model_keys': available_for_crop,
        'display_label': resolved_model['label'],
        'organism_name': resolved_model['organism_name'],
        'eppo_code': resolved_model['eppo_code'],
        'calculation_type': resolved_model['calculation_type'],
        'parcel_reference': {},
        'remote_parcel_id': '',
        'remote_model_id': '',
        'dataset_upload_id': '',
        'dataset_upload_succeeded': False,
        'time_window': {
            'start': (weather_summary or {}).get('history_start_date'),
            'end': (weather_summary or {}).get('history_end_date'),
            'observed_at': ((weather_summary or {}).get('current_weather') or {}).get('timestamp'),
        },
        'risk_level': None,
        'triggered_conditions': [],
        'recommendation': '',
        'notes': [],
        'warning_state': None,
        'raw_payload': {},
        'raw_payload_artifact': '',
        'bootstrap_artifact': '',
        'dataset_csv_artifact': '',
        'error_message': '',
        'evaluated_from_weather_service': False,
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }
    if not enabled:
        base_summary['notes'] = ['PDM disabled for this run.']
        base_summary['raw_payload_artifact'] = _write_json('summary.json', base_summary)
        return base_summary

    bootstrap = bootstrap_pdm_context(resolved_model['key'], resolved_crop, weather_summary)
    base_summary['service_status'] = bootstrap.get('service', {})
    base_summary['runtime_status'] = bootstrap.get('runtime', {})
    base_summary['parcel_reference'] = bootstrap.get('parcel', {})
    base_summary['remote_parcel_id'] = str((bootstrap.get('parcel') or {}).get('parcel_id') or '')
    base_summary['remote_model_id'] = str((bootstrap.get('resolved_model') or {}).get('remote_id') or '')
    base_summary['bootstrap_artifact'] = bootstrap.get('artifact_path') or bootstrap.get('bootstrap_artifact', '')
    base_summary['dataset_csv_artifact'] = bootstrap.get('dataset_csv_artifact', '')
    base_summary['dataset_upload_id'] = str(bootstrap.get('dataset_upload_id') or '')
    base_summary['dataset_upload_succeeded'] = bool(bootstrap.get('dataset_upload_succeeded'))

    if not base_summary['service_status'].get('reachable'):
        base_summary['status'] = 'failed'
        base_summary['warning_state'] = 'service_unreachable'
        base_summary['error_message'] = 'PDM service did not become reachable.'
        base_summary['notes'] = list(base_summary['service_status'].get('notes', [])) or ['PDM service was unreachable.']
        base_summary['raw_payload_artifact'] = _write_json('summary.json', base_summary)
        return base_summary

    client = PdmClient(get_pdm_service_config())
    client.login()
    raw_payload = client.calculate_risk_index(
        parcel_id=int(base_summary['remote_parcel_id']),
        model_ids=[base_summary['remote_model_id']],
        from_date=str(base_summary['time_window'].get('start') or ''),
        to_date=str(base_summary['time_window'].get('end') or ''),
        high_only=False,
    )
    entries = _extract_risk_entries(raw_payload)
    risk_level, reasons, recommendation, stats = _summarize_risks(entries, resolved_model, raw_payload)

    upload_succeeded = bool(bootstrap.get('dataset_upload_succeeded'))
    remote_completed = bool(raw_payload) or bool(entries) or bool(risk_level) or bool(recommendation)
    base_summary['status'] = 'success' if remote_completed else ('success' if upload_succeeded else 'partial')
    base_summary['warning_state'] = None if remote_completed or upload_succeeded else 'no_remote_results'
    base_summary['risk_level'] = risk_level
    base_summary['triggered_conditions'] = reasons
    base_summary['recommendation'] = recommendation
    base_summary['notes'] = [
        'Risk level comes from the remote OpenAgri PDM service.',
        f"Remote model id: {base_summary['remote_model_id']}",
        f"Remote parcel id: {base_summary['remote_parcel_id']}",
    ]
    if bootstrap.get('dataset_upload_succeeded'):
        uploaded_count = int((bootstrap.get('dataset_upload') or {}).get('record_count') or 0)
        base_summary['notes'].append(f'Weather data upload to PDM succeeded for {uploaded_count} record(s) before risk-index execution.')
    elif bootstrap.get('dataset_upload'):
        if remote_completed:
            base_summary['notes'].append('Weather upload response did not explicitly confirm success, but remote risk-index execution completed.')
        else:
            base_summary['notes'].append('Weather data upload to PDM was attempted before risk-index execution but did not report success.')
    base_summary['time_window'].update(
        {
            'remote_latest_timestamp': stats.get('latest_timestamp'),
            'remote_highest_timestamp': stats.get('highest_timestamp'),
        }
    )
    base_summary['raw_payload'] = {
        'bootstrap': bootstrap,
        'remote_result': raw_payload,
        'risk_entries': entries,
        'risk_stats': stats,
    }
    artifact_path = write_pdm_artifact('remote-result', base_summary['raw_payload'])
    base_summary['raw_payload_artifact'] = artifact_path
    _write_json('summary.json', base_summary)
    return base_summary
