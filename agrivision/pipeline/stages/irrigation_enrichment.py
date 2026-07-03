from __future__ import annotations

from pathlib import Path
from typing import Any

from agrivision.integrations.irrigation.adapter import collect_irrigation_snapshot


def default_irrigation_summary(base_url: str) -> dict[str, Any]:
    return {
        'enabled': True,
        'authenticated': False,
        'base_url': base_url,
        'email': '',
        'parcel_count': 0,
        'created_default_parcel': False,
        'eto': {'ok': False, 'http_status': None, 'method': 'get_calculations'},
        'notes': ['Irrigation integration not executed.'],
    }


def run_irrigation_enrichment(base_url: str, *, output_dir: Path | None = None) -> dict[str, Any]:
    irrigation_summary = default_irrigation_summary(base_url)
    try:
        return collect_irrigation_snapshot(write_artifacts=True, verbose=True, output_dir=output_dir)
    except Exception as exc:  # noqa: BLE001
        irrigation_summary['notes'] = [f'Irrigation integration failed: {exc}']
        return irrigation_summary
