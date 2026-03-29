from __future__ import annotations

from typing import Any

from agrivision.services.irrigation.bootstrap import (
    ensure_irrigation_auth_parcel_and_eto,
)

from .mapper import summarize_irrigation_payload


def collect_irrigation_snapshot(*, write_artifacts: bool = True, verbose: bool = True) -> dict[str, Any]:
    payload = ensure_irrigation_auth_parcel_and_eto(write_artifacts=write_artifacts, verbose=verbose)
    payload["summary"] = summarize_irrigation_payload(payload)
    return payload
