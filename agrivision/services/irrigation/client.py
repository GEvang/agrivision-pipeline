#!/usr/bin/env python3
"""
agrivision.services.irrigation.client

Client for the OpenAgri Irrigation Management Service (IRM).

This client now self-heals the local IRM dependency by:
  - cloning OpenAgri-IrrigationManagement if missing
  - creating/updating its .env with sane defaults
  - starting docker compose when the service is unreachable
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

import requests

from agrivision.services.irrigation.runtime import (
    get_irrigation_settings,
    start_service_if_needed,
)


@dataclass
class Location:
    id: Any
    raw: Dict[str, Any]


@dataclass
class EtoResult:
    location_id: Any
    from_date: date
    to_date: date
    raw: Dict[str, Any]


@dataclass
class DatasetCreateResult:
    dataset_id: Any
    raw: Dict[str, Any]


@dataclass
class SoilAnalysisResult:
    dataset_id: Any
    raw: Dict[str, Any]


_TOKEN_CACHE: str | None = None
_TOKEN_OBTAINED_AT_UTC: datetime | None = None


def _json_or_text(resp: requests.Response) -> Dict[str, Any]:
    ct = resp.headers.get("content-type", "")
    if ct.startswith("application/json"):
        payload = resp.json()
        if isinstance(payload, dict):
            return payload
        return {"payload": payload}
    return {"text": resp.text}


def _extract_id(obj: Any) -> Any:
    if not isinstance(obj, dict):
        return None
    return obj.get("id") or obj.get("@id") or obj.get("location_id") or obj.get("dataset_id")


def _auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def get_access_token(force_refresh: bool = False) -> str:
    global _TOKEN_CACHE, _TOKEN_OBTAINED_AT_UTC

    settings = get_irrigation_settings()
    static_token = settings["token"] or os.getenv("IRRIGATION_TOKEN") or None
    email = settings["email"]
    password = settings["password"]
    base_url = str(settings["base_url"])
    timeout_seconds = int(settings["timeout_seconds"])

    if static_token and not force_refresh:
        return str(static_token)
    if _TOKEN_CACHE and not force_refresh:
        return _TOKEN_CACHE

    if not email or not password:
        raise RuntimeError(
            "\n[Irrigation] Missing credentials.\n"
            "Provide either:\n"
            "  - env var IRRIGATION_TOKEN='...'\n"
            "  - or config.yaml -> irrigation.token: '...'\n"
            "  - or config.yaml -> irrigation.auth.email + irrigation.auth.password\n"
        )

    start_service_if_needed(verbose=True)

    url = f"{base_url}/api/v1/login/access-token"
    form = {
        "username": email,
        "password": password,
    }

    resp = requests.post(
        url,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout_seconds,
    )
    if resp.status_code != 200:
        payload = _json_or_text(resp)
        raise RuntimeError(
            "\n[Irrigation] Login failed.\n"
            f"POST {url}\n"
            f"HTTP {resp.status_code}\n"
            f"Response: {payload}\n"
        )

    payload = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    access = payload.get("access_token") or payload.get("token") or payload.get("jwt_token")
    if not access:
        raise RuntimeError(
            "\n[Irrigation] Login succeeded but no access_token found in response.\n"
            f"Response: {payload}\n"
        )

    _TOKEN_CACHE = str(access)
    _TOKEN_OBTAINED_AT_UTC = datetime.utcnow()
    return _TOKEN_CACHE


def _request(method: str, path: str, *, json_body: Any = None, params: Dict[str, Any] | None = None) -> requests.Response:
    settings = get_irrigation_settings()
    base_url = str(settings["base_url"])
    timeout_seconds = int(settings["timeout_seconds"])
    static_token = settings["token"] or os.getenv("IRRIGATION_TOKEN") or None

    token = get_access_token()
    url = f"{base_url}{path}"
    resp = requests.request(
        method,
        url,
        json=json_body,
        params=params,
        headers=_auth_headers(token),
        timeout=timeout_seconds,
    )

    if resp.status_code in (401, 403) and not static_token:
        token = get_access_token(force_refresh=True)
        resp = requests.request(
            method,
            url,
            json=json_body,
            params=params,
            headers=_auth_headers(token),
            timeout=timeout_seconds,
        )

    return resp


def list_locations() -> List[Location]:
    resp = _request("GET", "/api/v1/location/")
    resp.raise_for_status()
    payload = _json_or_text(resp)

    items: Any = payload
    if isinstance(payload, dict):
        items = payload.get("data") or payload.get("results") or payload.get("items") or payload

    if isinstance(items, dict):
        return [Location(id=_extract_id(items), raw=items)]
    if not isinstance(items, list):
        return []

    out: List[Location] = []
    for it in items:
        if isinstance(it, dict):
            out.append(Location(id=_extract_id(it), raw=it))
        else:
            out.append(Location(id=it, raw={"value": it}))
    return out


def create_location_from_wkt(wkt_polygon: str) -> Location:
    resp = _request("POST", "/api/v1/location/parcel-wkt/", json_body={"coordinates": wkt_polygon})
    resp.raise_for_status()
    payload = _json_or_text(resp)
    return Location(id=_extract_id(payload), raw=payload)


def get_eto_calculations(location_id: Any, from_date: date, to_date: date) -> EtoResult:
    path = f"/api/v1/eto/get-calculations/{location_id}/from/{from_date.isoformat()}/to/{to_date.isoformat()}/"
    resp = _request("GET", path)
    resp.raise_for_status()
    payload = _json_or_text(resp)
    return EtoResult(location_id=location_id, from_date=from_date, to_date=to_date, raw=payload)


def upload_dataset(payload: Dict[str, Any]) -> DatasetCreateResult:
    resp = _request("POST", "/api/v1/dataset/", json_body=payload)
    resp.raise_for_status()
    out = _json_or_text(resp)
    ds_id = _extract_id(out) or out.get("dataset_id") or out.get("id")
    return DatasetCreateResult(dataset_id=ds_id, raw=out)


def get_dataset(dataset_id: Any) -> Dict[str, Any]:
    resp = _request("GET", f"/api/v1/dataset/{dataset_id}/")
    resp.raise_for_status()
    return _json_or_text(resp)


def list_dataset_ids() -> Dict[str, Any]:
    resp = _request("GET", "/api/v1/dataset/")
    resp.raise_for_status()
    return _json_or_text(resp)


def get_soil_analysis(dataset_id: Any) -> SoilAnalysisResult:
    resp = _request("GET", f"/api/v1/dataset/{dataset_id}/analysis/")
    resp.raise_for_status()
    payload = _json_or_text(resp)
    return SoilAnalysisResult(dataset_id=dataset_id, raw=payload)


def _print_locations(locs: List[Location]) -> None:
    print(f"[Irrigation] Locations returned: {len(locs)}")
    for i, loc in enumerate(locs[:10], start=1):
        print(f"  {i:02d}. id={loc.id}")


if __name__ == "__main__":
    settings = get_irrigation_settings()
    print(f"[Irrigation] BASE_URL = {settings['base_url']}")
    tok = get_access_token()
    print("[Irrigation] Access token acquired (length):", len(tok))
    locs = list_locations()
    _print_locations(locs)
    if settings["default_parcel_wkt"]:
        print("[Irrigation] default_parcel_wkt is set; creating location from WKT...")
        loc = create_location_from_wkt(str(settings["default_parcel_wkt"]))
        print(f"[Irrigation] Created location id={loc.id}")
    if locs:
        today = date.today()
        from_d = today - timedelta(days=7)
        to_d = today
        print(f"[Irrigation] Fetching ETo for location {locs[0].id} from {from_d} to {to_d} ...")
        eto = get_eto_calculations(locs[0].id, from_d, to_d)
        print("[Irrigation] ETo response keys:", list(eto.raw.keys())[:20])
