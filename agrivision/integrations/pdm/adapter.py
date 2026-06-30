from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agrivision.config.settings import get_project_root, get_settings, load_config
from agrivision.integrations.pdm.client import (
    PdmClient,
    get_pdm_service_config,
    write_pdm_artifact,
)
from agrivision.services.pdm.bootstrap import bootstrap_pdm_context
from agrivision.services.pdm.catalog import get_models_for_crop, get_pdm_model

RISK_ORDER = {'low': 1, 'moderate': 2, 'medium': 2, 'high': 3, 'critical': 4}


def _artifact_dir() -> Path:
    settings = get_settings()
    path = get_project_root() / (settings.paths.output_root or 'output') / 'pdm'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(name: str, payload: dict[str, Any], *, artifact_dir: Path | None = None) -> str:
    path = (artifact_dir or _artifact_dir())
    path.mkdir(parents=True, exist_ok=True)
    path = path / name
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return str(path)


def _extract_risk_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    def _append_entry(item: dict[str, Any], parent: dict[str, Any] | None = None) -> None:
        timestamp = (
            item.get('phenomenonTime')
            or item.get('saref:hasTimestamp')
            or item.get('timestamp')
            or item.get('date')
            or item.get('datetime')
            or ''
        )
        risk_level = (
            item.get('riskClass')
            or item.get('ocsm:hasRiskLevel')
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
                'risk_score': item.get('hasSimpleResult') or item.get('risk_score') or item.get('score') or '',
                'meta': item.get('meta') or '',
                'model_id': parent.get('@id') or parent.get('id') or item.get('model_id') or '',
                'eppo_code': parent.get('fsm:eppoCode') or parent.get('eppo_code') or item.get('eppo_code') or '',
                'description': (
                    parent.get('foodie:description')
                    or parent.get('description')
                    or ((parent.get('observedProperty') or {}).get('name') if isinstance(parent.get('observedProperty'), dict) else '')
                    or item.get('description')
                    or ''
                ),
            }
        )

    if not isinstance(payload, dict):
        return entries

    graph = payload.get('@graph', [])
    if isinstance(graph, list):
        for item in graph:
            if not isinstance(item, dict):
                continue
            risks = (
                item.get('hasMember')
                or item.get('ocsm:hasPredictedInfestationRisks')
                or item.get('ocsm:hasPredictedInfestations')
                or []
            )
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
            'counts': {'Low': 0, 'Moderate': 0, 'High': 0, 'Critical': 0},
            'latest_timestamp': None,
            'highest_timestamp': None,
            'highest_score': None,
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
    reasons = [
        (
            f"Remote PDM returned {counts.get('Critical', 0)} Critical, "
            f"{counts.get('High', 0)} High, {counts.get('Moderate', 0)} Moderate, "
            f"{counts.get('Low', 0)} Low risk observations."
        )
    ]
    if highest and highest.get('timestamp'):
        reasons.append(f"Highest remote risk observed at {highest['timestamp']}.")
    if highest and highest.get('risk_score') not in (None, ''):
        reasons.append(f"Highest fuzzy risk score: {highest['risk_score']}/100.")
    recommendation = model.get('default_recommendation', 'Maintain routine monitoring.')
    for rule in model.get('risk_rules', []):
        if str(rule.get('label', '')).lower() == str(risk_level or '').lower():
            recommendation = str(rule.get('recommendation') or recommendation)
            break
    return risk_level, reasons, recommendation, {
        'counts': counts,
        'latest_timestamp': latest_ts,
        'highest_timestamp': highest.get('timestamp') if highest else None,
        'highest_score': highest.get('risk_score') if highest else None,
    }


def _service_crop_name(model: dict[str, Any], crop: str) -> str:
    if model.get('fuzzy_crop_name'):
        return str(model['fuzzy_crop_name'])
    mapping = {'grapevine': 'Vineyard', 'grape': 'Vineyard', 'olive': 'Olive'}
    return mapping.get(crop.strip().lower(), crop.strip().title())


def _find_crop(crops: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    wanted = name.strip().lower()
    return next((crop for crop in crops if str(crop.get('name', '')).strip().lower() == wanted), None)


def _find_threat_model(threat_models: list[dict[str, Any]], model: dict[str, Any]) -> dict[str, Any] | None:
    aliases = [str(item).lower() for item in model.get('fuzzy_scientific_names', [])]
    aliases.extend([str(model.get('organism_name', '')).lower(), str(model.get('label', '')).lower()])
    aliases = [alias for alias in aliases if alias]
    for threat in threat_models:
        haystack = ' '.join(
            str(threat.get(key) or '')
            for key in ('scientific_name', 'common_name', 'label', 'note')
        ).lower()
        if any(alias in haystack for alias in aliases):
            return threat
    return None


def _location_lat_lon() -> tuple[float, float]:
    location = load_config().get('location', {})
    return float(location.get('lat', 0.0)), float(location.get('lon', 0.0))


def _ensure_fuzzy_parcel(client: PdmClient, *, model_key: str) -> dict[str, Any]:
    lat, lon = _location_lat_lon()
    name = f'agrivision-fuzzy-{model_key}-parcel'
    for parcel in client.list_parcels():
        if str(parcel.get('name') or '') == name:
            return {'parcel': parcel, 'parcel_id': str(parcel.get('id')), 'source': 'existing', 'latitude': lat, 'longitude': lon}
    try:
        client.create_parcel_lat_lon(name=name, latitude=lat, longitude=lon)
    except Exception:
        # The new PDM service may seed historical weather during parcel creation
        # and exceed the client timeout even though the parcel is eventually saved.
        pass
    for parcel in client.list_parcels():
        if str(parcel.get('name') or '') == name:
            return {'parcel': parcel, 'parcel_id': str(parcel.get('id')), 'source': 'created', 'latitude': lat, 'longitude': lon}
    raise RuntimeError(f'PDM fuzzy parcel {name} could not be created or resolved.')


def _collect_fuzzy_snapshot(
    client: PdmClient,
    weather_summary: dict[str, Any] | None,
    base_summary: dict[str, Any],
    resolved_model: dict[str, Any],
    resolved_crop: str,
) -> dict[str, Any]:
    service_crop_name = _service_crop_name(resolved_model, resolved_crop)
    crop = _find_crop(client.list_crops(), service_crop_name)
    if not crop:
        raise RuntimeError(f'PDM fuzzy crop {service_crop_name!r} is not available.')
    threat_models = client.list_threat_models(crop_id=str(crop['id']))
    threat_model = _find_threat_model(threat_models, resolved_model) or (threat_models[0] if threat_models else None)
    if not threat_model:
        raise RuntimeError(f'No PDM fuzzy threat models are available for {service_crop_name}.')
    parcel = _ensure_fuzzy_parcel(client, model_key=resolved_model['key'])

    start = str((weather_summary or {}).get('history_start_date') or '')
    end = str((weather_summary or {}).get('history_end_date') or '')
    mode = 'historical' if start and end else 'forecast'
    try:
        raw_payload = client.calculate_fuzzy_risk(
            parcel_id=int(parcel['parcel_id']),
            threat_model_ids=[str(threat_model['id'])],
            from_date=start or None,
            to_date=end or None,
            mode=mode,
        )
    except Exception as exc:
        raw_payload = client.calculate_fuzzy_risk(
            parcel_id=int(parcel['parcel_id']),
            threat_model_ids=[str(threat_model['id'])],
            mode='forecast',
        )
        raw_payload.setdefault('_fallback_reason', str(exc))
        mode = 'forecast'

    entries = _extract_risk_entries(raw_payload)
    risk_level, reasons, recommendation, stats = _summarize_risks(entries, resolved_model, raw_payload)
    base_summary.update(
        {
            'status': 'success',
            'calculation_type': 'fuzzy_risk',
            'risk_level': risk_level,
            'risk_score': stats.get('highest_score'),
            'triggered_conditions': reasons,
            'recommendation': recommendation,
            'remote_parcel_id': str(parcel['parcel_id']),
            'remote_model_id': str(threat_model['id']),
            'parcel_reference': parcel,
            'dataset_upload_succeeded': mode == 'historical',
            'evaluated_from_weather_service': True,
            'notes': [
                'Risk level comes from the OpenAgri PDM fuzzy risk engine.',
                f'PDM crop: {service_crop_name}',
                f"PDM threat model: {threat_model.get('common_name') or threat_model.get('scientific_name')}",
                f'Fuzzy risk mode: {mode}',
            ],
            'raw_payload': {
                'crop': crop,
                'threat_model': threat_model,
                'remote_result': raw_payload,
                'risk_entries': entries,
                'risk_stats': stats,
            },
        }
    )
    base_summary['time_window'].update(
        {
            'remote_latest_timestamp': stats.get('latest_timestamp'),
            'remote_highest_timestamp': stats.get('highest_timestamp'),
        }
    )
    base_summary['raw_payload_artifact'] = write_pdm_artifact('fuzzy-result', base_summary['raw_payload'])
    _write_json('summary.json', base_summary)
    return base_summary

def collect_pdm_snapshot(
    weather_summary: dict[str, Any] | None,
    *,
    enabled: bool = True,
    crop: str | None = None,
    model_key: str | None = None,
    artifact_dir: Path | None = None,
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
        base_summary['raw_payload_artifact'] = _write_json('summary.json', base_summary, artifact_dir=artifact_dir)
        return base_summary

    bootstrap = bootstrap_pdm_context(
        resolved_model['key'],
        resolved_crop,
        weather_summary,
        artifact_dir=artifact_dir,
    )
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
        base_summary['raw_payload_artifact'] = _write_json('summary.json', base_summary, artifact_dir=artifact_dir)
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
    artifact_path = write_pdm_artifact('remote-result', base_summary['raw_payload'], artifact_dir=artifact_dir)
    base_summary['raw_payload_artifact'] = artifact_path
    _write_json('summary.json', base_summary, artifact_dir=artifact_dir)
    return base_summary
