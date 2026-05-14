from __future__ import annotations

from typing import Any

from agrivision.integrations.pdm.adapter import collect_pdm_snapshot


def default_pdm_summary(base_url: str, crop: str, model_key: str, enabled: bool) -> dict[str, Any]:
    return {
        'enabled': enabled,
        'status': 'disabled' if not enabled else 'pending',
        'service_status': {'base_url': base_url},
        'crop': crop,
        'selected_model_key': model_key,
        'display_label': '',
        'organism_name': '',
        'eppo_code': '',
        'calculation_type': 'risk_index',
        'parcel_reference': {},
        'time_window': {},
        'risk_level': None,
        'triggered_conditions': [],
        'recommendation': '',
        'notes': ['PDM integration not executed.'],
        'warning_state': None,
        'raw_payload': {},
        'raw_payload_artifact': '',
        'bootstrap_artifact': '',
        'error_message': '',
        'evaluated_from_weather_service': False,
    }


def run_pdm_enrichment(
    *,
    base_url: str,
    weather_summary: dict[str, Any] | None,
    enabled: bool,
    crop: str,
    model_key: str,
) -> dict[str, Any]:
    pdm_summary = default_pdm_summary(base_url, crop, model_key, enabled)
    try:
        return collect_pdm_snapshot(weather_summary, enabled=enabled, crop=crop, model_key=model_key)
    except Exception as exc:  # noqa: BLE001
        pdm_summary['status'] = 'failed'
        pdm_summary['error_message'] = str(exc)
        pdm_summary['notes'] = [f'PDM integration failed: {exc}']
        return pdm_summary
