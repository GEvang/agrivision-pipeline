from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agrivision.config.settings import get_project_root, get_settings
from agrivision.integrations.pdm.client import (
    PdmClient,
    build_weather_dataset_csv,
    build_weather_dataset_records,
    ensure_pdm_service_available,
    ensure_remote_model,
    ensure_remote_parcel,
    get_pdm_service_config,
    write_pdm_artifact,
)
from agrivision.services.pdm.catalog import get_pdm_model


def _output_dir() -> Path:
    settings = get_settings()
    root = get_project_root() / (settings.paths.output_root or 'output') / 'pdm'
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_json(name: str, payload: dict[str, Any]) -> str:
    path = _output_dir() / name
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return str(path)


def bootstrap_pdm_context(
    selected_model_key: str | None,
    crop: str | None,
    weather_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    model = get_pdm_model(selected_model_key)
    client = PdmClient(get_pdm_service_config())
    runtime = ensure_pdm_service_available(timeout_seconds=max(settings.pdm.timeout_seconds, 120))
    service = client.probe()
    parcel_wkt = settings.irrigation.default_parcel_wkt

    client.login()
    parcel_state = ensure_remote_parcel(client, model_key=model['key'], geo_wkt=parcel_wkt)
    model_state = ensure_remote_model(client, model['key'], geo_wkt=parcel_wkt)

    dataset_upload: dict[str, Any] | None = None
    dataset_csv_artifact = ''
    if weather_summary and weather_summary.get('enabled'):
        csv_payload = build_weather_dataset_csv(weather_summary, parcel_reference=parcel_wkt)
        csv_path = _output_dir() / 'weather_dataset.csv'
        csv_path.write_text(csv_payload, encoding='utf-8')
        dataset_csv_artifact = str(csv_path)
        try:
            records = build_weather_dataset_records(weather_summary, parcel_reference=parcel_wkt)
            dataset_upload = client.upload_weather_dataset(parcel_id=int(parcel_state['parcel_id']), records=records)
            if isinstance(dataset_upload, dict):
                dataset_upload.setdefault('uploaded', True)
                dataset_upload.setdefault('record_count', len(records))
        except Exception as exc:  # noqa: BLE001
            dataset_upload = {'error': str(exc), 'uploaded': False, 'record_count': len(records) if 'records' in locals() else 0}

    payload = {
        'runtime': runtime,
        'service': service,
        'parcel': {
            'source': 'irrigation.default_parcel_wkt',
            'wkt': parcel_wkt,
            **parcel_state,
        },
        'resolved_model': {
            'key': model['key'],
            'crop': crop or model['crop'],
            'label': model['label'],
            'organism_name': model['organism_name'],
            'eppo_code': model['eppo_code'],
            'calculation_type': model['calculation_type'],
            **model_state,
        },
        'dataset_upload': dataset_upload or {},
        'dataset_upload_id': _extract_dataset_upload_id(dataset_upload),
        'dataset_upload_succeeded': bool(isinstance(dataset_upload, dict) and not dataset_upload.get('error')) if dataset_upload is not None else False,
        'dataset_csv_artifact': dataset_csv_artifact,
    }
    payload['artifact_path'] = _write_json('bootstrap.json', payload)
    payload['bootstrap_artifact'] = write_pdm_artifact('bootstrap', payload)
    return payload

def _extract_dataset_upload_id(payload: dict[str, Any] | None) -> str:
    preferred_keys = {
        'id',
        'upload_id',
        'dataset_id',
        'weather_id',
        'data_id',
        'datasetId',
        'weatherId',
        'dataId',
        'uploadId',
    }

    def _looks_like_identifier(value: Any) -> bool:
        if value in (None, ''):
            return False
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return False
            if len(stripped) >= 8:
                return True
        return False

    def _walk(value: Any) -> str:
        if isinstance(value, dict):
            for key in preferred_keys:
                candidate = value.get(key)
                if _looks_like_identifier(candidate):
                    return str(candidate)
            for key, candidate in value.items():
                if isinstance(key, str) and key.lower().endswith('_id') and _looks_like_identifier(candidate):
                    return str(candidate)
            for nested in value.values():
                found = _walk(nested)
                if found:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = _walk(item)
                if found:
                    return found
        return ''

    return _walk(payload)

