#!/usr/bin/env python3
"""
agrivision.services.irrigation.bootstrap

Bootstraps OpenAgri Irrigation Management Service auth + parcels + ETo (official workflow).

Self-healing:
- Reuse the shared irrigation runtime reconciler to clone the repo if missing,
  sync the service .env, detect the compose file, start/restart containers, and
  wait until the service is reachable.

Official ETo workflow (no GateKeeper required):
  GET /api/v1/eto/get-calculations/{location_id}/from/{from_date}/to/{to_date}/

Config-driven (config.yaml):
  irrigation.base_url
  irrigation.auth.email
  irrigation.auth.password
  irrigation.default_parcel_wkt
  irrigation.eto.location_id
  irrigation.eto.days_back

Artifacts written:
  output/irrigation/auth_token.json
  output/irrigation/parcel.json
  output/irrigation/eto.json
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agrivision.config.settings import get_project_root, get_settings
from agrivision.services.irrigation.runtime import ensure_service_available
from agrivision.services.weather.client import fetch_history_daily


def _get_bootstrap_paths(output_dir: Path | None = None) -> dict[str, Path]:
    settings = get_settings()
    project_root = get_project_root()
    resolved_output_dir = output_dir
    if resolved_output_dir is None:
        output_root = str(getattr(settings.paths, "output_root", "output") or "output")
        resolved_output_dir = project_root / output_root / "irrigation"
    token_path = resolved_output_dir / "auth_token.json"
    parcel_path = resolved_output_dir / "parcel.json"
    eto_path = resolved_output_dir / "eto.json"
    weather_debug_path = resolved_output_dir / "weather_debug.json"
    return {
        "project_root": project_root,
        "output_dir": resolved_output_dir,
        "token_path": token_path,
        "parcel_path": parcel_path,
        "eto_path": eto_path,
        "weather_debug_path": weather_debug_path,
    }


def _ensure_output_dir(output_dir: Path | None = None) -> None:
    paths = _get_bootstrap_paths(output_dir=output_dir)
    paths["output_dir"].mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_token_artifact(base_url: str, token_type: str, access_token: str, email: str, *, output_dir: Path | None = None) -> None:
    paths = _get_bootstrap_paths(output_dir=output_dir)
    _write_json(
        paths["token_path"],
        {
            "base_url": base_url,
            "token_type": token_type,
            "access_token": access_token,
            "email": email,
        },
    )


def _write_parcel_artifact(payload: Dict[str, Any], *, output_dir: Path | None = None) -> None:
    paths = _get_bootstrap_paths(output_dir=output_dir)
    _write_json(paths["parcel_path"], payload)


def _write_eto_artifact(payload: Dict[str, Any], *, output_dir: Path | None = None) -> None:
    paths = _get_bootstrap_paths(output_dir=output_dir)
    _write_json(paths["eto_path"], payload)


def _write_weather_debug_artifact(payload: Dict[str, Any], *, output_dir: Path | None = None) -> None:
    paths = _get_bootstrap_paths(output_dir=output_dir)
    _write_json(paths["weather_debug_path"], payload)


def _extract_lat_lon_from_wkt(wkt: str) -> tuple[float, float] | None:
    text = (wkt or "").strip()
    if not text.upper().startswith("POINT"):
        return None
    try:
        coords = text[text.index("(") + 1 : text.rindex(")")].replace(",", " ").split()
        lat = float(coords[0])
        lon = float(coords[1])
        return lat, lon
    except (IndexError, ValueError):
        return None


def _count_eto_values(payload: Any) -> Optional[int]:
    if isinstance(payload, list):
        return len(payload)
    if not isinstance(payload, dict):
        return None
    for key in ("@graph", "calculations", "eto", "data", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
    return None


def _summarize_eto_values(payload: Any) -> Dict[str, Any]:
    entries: list[Any] = []
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        for key in ("@graph", "calculations", "eto", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                entries = value
                break

    values: list[float] = []
    dates: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        raw_value = (
            item.get("hasSimpleResult")
            or item.get("eto")
            or item.get("value")
            or item.get("calculation")
            or item.get("result")
        )
        try:
            values.append(float(raw_value))
        except (TypeError, ValueError):
            pass
        raw_date = item.get("resultTime") or item.get("date") or item.get("day")
        if raw_date:
            dates.append(str(raw_date))

    if not values:
        return {}
    return {
        "min_mm": round(min(values), 3),
        "max_mm": round(max(values), 3),
        "average_mm": round(sum(values) / len(values), 3),
        "dates": sorted(set(dates)),
    }


# ----------------------------
# HTTP helpers
# ----------------------------
def _http_json(
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 12,
) -> Tuple[int, Any]:
    body = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=body, method=method, headers=req_headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            data = resp.read().decode("utf-8", errors="replace")
            if data.strip() == "":
                return status, {}
            try:
                return status, json.loads(data)
            except Exception:
                return status, data
    except urllib.error.HTTPError as e:
        status = e.code
        data = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(data) if data.strip() else {}
        except Exception:
            parsed = {"raw": data}
        return status, parsed
    except urllib.error.URLError as e:
        raise ConnectionError(f"Failed to connect to {url}: {e}") from e


def _http_form(
    url: str,
    form_fields: Dict[str, str],
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 12,
) -> Tuple[int, Any]:
    encoded = urllib.parse.urlencode(form_fields).encode("utf-8")
    req_headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url=url, data=encoded, method="POST", headers=req_headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            data = resp.read().decode("utf-8", errors="replace")
            if data.strip() == "":
                return status, {}
            try:
                return status, json.loads(data)
            except Exception:
                return status, data
    except urllib.error.HTTPError as e:
        status = e.code
        data = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(data) if data.strip() else {}
        except Exception:
            parsed = {"raw": data}
        return status, parsed
    except urllib.error.URLError as e:
        raise ConnectionError(f"Failed to connect to {url}: {e}") from e


# ----------------------------
# Service up / self-heal
# ----------------------------
def _ensure_service_up(base_url: str, seconds: int = 75, verbose: bool = True) -> None:
    ensure_service_available(timeout_seconds=seconds, verbose=verbose)


# ----------------------------
# API operations
# ----------------------------
def _register_user(base_url: str, email: str, password: str) -> Tuple[int, Any]:
    return _http_json("POST", f"{base_url}/api/v1/user/register/", payload={"email": email, "password": password})


def _login(base_url: str, email: str, password: str) -> Tuple[int, Any]:
    return _http_form(
        f"{base_url}/api/v1/login/access-token/",
        form_fields={"username": email, "password": password},
    )


def _token_valid(base_url: str, token: str) -> Tuple[bool, Any]:
    status, resp = _http_json(
        "GET",
        f"{base_url}/api/v1/user/me/",
        headers={"Authorization": f"Bearer {token}"},
    )
    return (200 <= status < 300), resp


def _list_locations(base_url: str, token: str) -> Tuple[int, Any]:
    return _http_json(
        "GET",
        f"{base_url}/api/v1/location/",
        headers={"Authorization": f"Bearer {token}"},
    )


def _create_default_parcel(base_url: str, token: str, wkt: str) -> Tuple[int, Any]:
    return _http_json(
        "POST",
        f"{base_url}/api/v1/location/parcel-wkt/",
        payload={"coordinates": wkt},
        headers={"Authorization": f"Bearer {token}"},
    )


def fetch_eto_get_calculations(
    *,
    base_url: str,
    token: str,
    location_id: int,
    from_date: str,
    to_date: str,
    formatting: str = "JSON",
) -> Tuple[int, Any]:
    url = f"{base_url}/api/v1/eto/get-calculations/{int(location_id)}/from/{from_date}/to/{to_date}/"
    if formatting:
        url = f"{url}?{urllib.parse.urlencode({'formatting': formatting})}"
    return _http_json("GET", url, headers={"Authorization": f"Bearer {token}"})


def fetch_and_store_eto(
    *,
    base_url: str,
    token: str,
    location_id: int,
    latitude: float,
    longitude: float,
    from_date: str,
    to_date: str,
    formatting: str = "JSON-LD",
) -> Tuple[int, Any]:
    params = {
        "location_id": int(location_id),
        "latitude": latitude,
        "longitude": longitude,
        "from_date": from_date,
        "to_date": to_date,
        "formatting": formatting,
    }
    url = f"{base_url}/api/v1/eto/fetch-and-store-eto/?{urllib.parse.urlencode(params)}"
    return _http_json("GET", url, headers={"Authorization": f"Bearer {token}"})


def fetch_eto_options(*, base_url: str, token: str) -> Tuple[int, Any]:
    return _http_json("GET", f"{base_url}/api/v1/eto/option-types/", headers={"Authorization": f"Bearer {token}"})


def fetch_soil_moisture(
    *,
    base_url: str,
    token: str,
    parcel_id: int,
    from_date: str,
    to_date: str,
) -> Tuple[int, Any]:
    url = f"{base_url}/api/v1/dataset/soil-moisture/{int(parcel_id)}/from/{from_date}/to/{to_date}"
    return _http_json("GET", url, headers={"Authorization": f"Bearer {token}"})


# ----------------------------
# Parcel management helper
# ----------------------------
def _ensure_parcel_state(
    *,
    base_url: str,
    token: str,
    email: str,
    wkt: str,
    write_artifacts: bool = True,
    output_dir: Path | None = None,
) -> Dict[str, Any]:
    """
    Ensure parcel state exists and return parcel summary for the caller.

    Returns:
        {
            "ok": bool,
            "parcel_count": int,
            "created_default_parcel": bool,
            "notes": list[str],
            "error_summary": dict | None (full response if parcel flow failed)
        }
    """
    notes: List[str] = []
    locations_list: List[dict] = []
    created_default = False
    paths = _get_bootstrap_paths(output_dir=output_dir)

    status, locations_resp = _list_locations(base_url, token)
    if not (200 <= status < 300):
        error_summary = _build_bootstrap_failure_summary(
            base_url=base_url,
            authenticated=True,
            email=email,
            parcel_count=0,
            created_default_parcel=False,
            notes=[f"Failed to list locations (HTTP {status}): {locations_resp}"],
        )
        return {
            "ok": False,
            "parcel_count": 0,
            "created_default_parcel": False,
            "notes": notes,
            "locations": locations_list,
            "error_summary": error_summary,
        }

    
    if isinstance(locations_resp, dict) and isinstance(locations_resp.get("locations"), list):
        locations_list = locations_resp["locations"]
    else:
        notes.append("Location list returned unexpected schema; cannot derive parcel_count reliably.")

    parcel_count = len(locations_list)

    if parcel_count == 0:
        status, parcel_resp = _create_default_parcel(base_url, token, wkt)
        if not (200 <= status < 300):
            error_summary = _build_bootstrap_failure_summary(
                base_url=base_url,
                authenticated=True,
                email=email,
                parcel_count=0,
                created_default_parcel=False,
                notes=[f"Failed to create default parcel (HTTP {status}): {parcel_resp}"],
            )
            return {
                "ok": False,
                "parcel_count": 0,
                "created_default_parcel": False,
                "notes": notes,
                "error_summary": error_summary,
            }
        created_default = True
        if write_artifacts:
            _write_parcel_artifact(parcel_resp, output_dir=output_dir)

        status, locations_resp = _list_locations(base_url, token)
        if isinstance(locations_resp, dict) and isinstance(locations_resp.get("locations"), list):
            locations_list = locations_resp["locations"]
            parcel_count = len(locations_list)

    if write_artifacts and not paths["parcel_path"].exists():
        _write_parcel_artifact({"message": "Parcel already existed; no creation performed."}, output_dir=output_dir)

    return {
        "ok": True,
        "parcel_count": parcel_count,
        "created_default_parcel": created_default,
        "notes": notes,
        "locations": locations_list,
        "error_summary": None,
    }


def _select_effective_location_id(
    *,
    configured_location_id: int,
    locations: List[dict[str, Any]],
    created_default_parcel: bool,
    notes: List[str],
) -> int:
    """Resolve a safe location_id for ETo requests from the live location list."""
    valid_ids: List[int] = []
    for item in locations:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("id")
        try:
            valid_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not valid_ids:
        return int(configured_location_id)

    if int(configured_location_id) in valid_ids:
        return int(configured_location_id)

    if created_default_parcel:
        selected = valid_ids[-1]
        notes.append(
            f"Configured irrigation.eto.location_id={configured_location_id} was not found; "
            f"using newly available parcel location_id={selected}."
        )
        return selected

    if len(valid_ids) == 1:
        selected = valid_ids[0]
        notes.append(
            f"Configured irrigation.eto.location_id={configured_location_id} was not found; "
            f"using the only visible parcel location_id={selected}."
        )
        return selected

    selected = valid_ids[-1]
    notes.append(
        f"Configured irrigation.eto.location_id={configured_location_id} was not found among visible parcels {valid_ids}; "
        f"using most recent visible location_id={selected}."
    )
    return selected


def _run_weather_debug_probe(
    *,
    from_date_str: str,
    to_date_str: str,
    write_artifacts: bool = True,
    output_dir: Path | None = None,
) -> Dict[str, Any]:
    """
    Probe the Weather service history endpoint so ETo failures can be separated from weather-data availability.
    """
    paths = _get_bootstrap_paths(output_dir=output_dir)
    try:
        history_payload = fetch_history_daily(from_date_str, to_date_str)
        ok = True
        error = None
    except Exception as exc:  # noqa: BLE001
        history_payload = {"error": str(exc)}
        ok = False
        error = str(exc)

    if write_artifacts:
        _write_weather_debug_artifact(
            {
                "requested": {"from_date": from_date_str, "to_date": to_date_str},
                "ok": ok,
                "response": history_payload,
            },
            output_dir=output_dir,
        )

    preview = json.dumps(history_payload, indent=2)[:900] if isinstance(history_payload, (dict, list)) else str(history_payload)[:900]
    return {
        "ok": ok,
        "artifact_path": str(paths["weather_debug_path"]),
        "preview": preview,
        "response": history_payload,
        "error": error,
    }


# ----------------------------
# Authentication helper
# ----------------------------
def _authenticate_irrigation(
    base_url: str,
    email: str,
    password: str,
    write_artifacts: bool = True,
    verbose: bool = True,
    output_dir: Path | None = None,
) -> Dict[str, Any]:
    """
    Acquire and validate irrigation token.

    Returns:
        {
            "ok": bool,
            "token": str | None,
            "email": str,
            "me": dict (user info from _token_valid),
            "notes": list[str],
            "error_summary": dict | None (full response if auth failed)
        }
    """
    notes: List[str] = []
    locations_list: List[dict] = []
    token: Optional[str] = None
    paths = _get_bootstrap_paths(output_dir=output_dir)

    # Try to use existing token file
    if paths["token_path"].exists():
        try:
            token_obj = json.loads(paths["token_path"].read_text(encoding="utf-8"))
            token = token_obj.get("access_token")
        except Exception:
            notes.append("Existing token file unreadable; will re-login.")
            token = None

    # Validate existing token if present
    if token:
        ok, me = _token_valid(base_url, token)
        if not ok:
            notes.append("Existing token invalid/expired; re-login required.")
            token = None
        else:
            if verbose:
                print(f"[Irrigation] Existing token valid for: {me.get('email', email)}")
            return {
                "ok": True,
                "token": token,
                "email": me.get("email", email),
                "me": me,
                "notes": notes,
                "error_summary": None,
            }

    # Existing token invalid or missing; perform register + login
    status, _ = _register_user(base_url, email, password)
    if not (200 <= status < 300):
        notes.append(f"Register returned HTTP {status}: continuing (user may already exist).")

    status, login_resp = _login(base_url, email, password)
    if not (200 <= status < 300):
        error_summary = _build_bootstrap_failure_summary(
            base_url=base_url,
            authenticated=False,
            email="",
            parcel_count=0,
            created_default_parcel=False,
            notes=[f"Irrigation login failed (HTTP {status}): {login_resp}"],
        )
        return {
            "ok": False,
            "token": None,
            "email": "",
            "me": {},
            "notes": notes,
            "locations": locations_list,
            "error_summary": error_summary,
        }

    token = (login_resp or {}).get("access_token")
    if not token:
        error_summary = _build_bootstrap_failure_summary(
            base_url=base_url,
            authenticated=False,
            email="",
            parcel_count=0,
            created_default_parcel=False,
            notes=[f"Irrigation login response missing access_token: {login_resp}"],
        )
        return {
            "ok": False,
            "token": None,
            "email": "",
            "me": {},
            "notes": notes,
            "error_summary": error_summary,
        }

    token_type = (login_resp or {}).get("token_type", "bearer")

    if write_artifacts:
        _write_token_artifact(base_url, token_type, token, email, output_dir=output_dir)

    if verbose:
        print("[Irrigation] Logged in and token stored")

    # Validate newly acquired token
    ok, me = _token_valid(base_url, token)
    if not ok:
        error_summary = _build_bootstrap_failure_summary(
            base_url=base_url,
            authenticated=False,
            email="",
            parcel_count=0,
            created_default_parcel=False,
            notes=["Token validation failed after login."],
        )
        return {
            "ok": False,
            "token": None,
            "email": "",
            "me": {},
            "notes": notes,
            "error_summary": error_summary,
        }

    return {
        "ok": True,
        "token": token,
        "email": me.get("email", email),
        "me": me,
        "notes": notes,
        "locations": locations_list,
        "error_summary": None,
    }


def _resolve_bootstrap_config(
    *,
    eto_location_id: Optional[int] = None,
    eto_days_back: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Load and validate irrigation bootstrap config, then resolve effective ETo inputs.
    """
    settings = get_settings()

    base_url = str(settings.irrigation.base_url).rstrip("/")
    email = str(settings.irrigation.auth.email)
    password = str(settings.irrigation.auth.password)
    wkt = str(settings.irrigation.default_parcel_wkt)

    missing: List[str] = []
    if not base_url:
        missing.append("irrigation.base_url")
    if not email:
        missing.append("irrigation.auth.email")
    if not password:
        missing.append("irrigation.auth.password")
    if not wkt:
        missing.append("irrigation.default_parcel_wkt")

    if missing:
        raise ValueError("Missing required config keys in config.yaml: " + ", ".join(missing))

    eto_location_id_cfg = settings.irrigation.eto.location_id
    eto_days_back_cfg = settings.irrigation.eto.days_back

    try:
        cfg_location_id = int(eto_location_id_cfg)
    except (TypeError, ValueError):
        cfg_location_id = 1

    try:
        cfg_days_back = int(eto_days_back_cfg) if eto_days_back_cfg is not None else 7
    except (TypeError, ValueError):
        cfg_days_back = 7

    effective_location_id = int(eto_location_id) if eto_location_id is not None else cfg_location_id
    effective_days_back = int(eto_days_back) if eto_days_back is not None else cfg_days_back

    return {
        "base_url": base_url,
        "email": email,
        "password": password,
        "wkt": wkt,
        "effective_location_id": effective_location_id,
        "effective_days_back": effective_days_back,
    }


def _fetch_eto_state(
    *,
    base_url: str,
    token: str,
    effective_location_id: int,
    effective_days_back: int,
    write_artifacts: bool = True,
    verbose: bool = True,
    output_dir: Path | None = None,
) -> Dict[str, Any]:
    """
    Fetch ETo via get-calculations and return summary components for orchestration.
    """
    notes: List[str] = []
    paths = _get_bootstrap_paths(output_dir=output_dir)

    to_d = date.today()
    from_d = to_d - timedelta(days=max(1, int(effective_days_back)))
    from_date_str = from_d.isoformat()
    to_date_str = to_d.isoformat()

    if verbose:
        print(
            f"[Irrigation] Fetching ETo via get-calculations for location_id={effective_location_id} "
            f"({from_date_str} â†’ {to_date_str})..."
        )

    eto_status, eto_resp = fetch_eto_get_calculations(
        base_url=base_url,
        token=token,
        location_id=int(effective_location_id),
        from_date=from_date_str,
        to_date=to_date_str,
        formatting="JSON-LD",
    )
    eto_ok = 200 <= eto_status < 300

    eto_count = _count_eto_values(eto_resp)
    stored_eto_resp: Any = None
    stored_eto_status: Optional[int] = None
    lat_lon = _extract_lat_lon_from_wkt(str(get_settings().irrigation.default_parcel_wkt))
    if eto_ok and eto_count == 0 and lat_lon:
        stored_eto_status, stored_eto_resp = fetch_and_store_eto(
            base_url=base_url,
            token=token,
            location_id=int(effective_location_id),
            latitude=lat_lon[0],
            longitude=lat_lon[1],
            from_date=from_date_str,
            to_date=to_date_str,
            formatting="JSON-LD",
        )
        if 200 <= stored_eto_status < 300:
            eto_resp = stored_eto_resp
            eto_status = stored_eto_status
            eto_count = _count_eto_values(eto_resp)
            notes.append("ETo was fetched and stored from weather data because no stored calculations existed yet.")

    options_status, options_resp = fetch_eto_options(base_url=base_url, token=token)
    options_summary = options_resp if 200 <= options_status < 300 and isinstance(options_resp, dict) else {}
    soil_status, soil_resp = fetch_soil_moisture(
        base_url=base_url,
        token=token,
        parcel_id=int(effective_location_id),
        from_date=from_date_str,
        to_date=to_date_str,
    )

    if write_artifacts:
        _write_eto_artifact(
            {
                "requested": {
                    "method": "get_calculations",
                    "location_id": int(effective_location_id),
                    "from_date": from_date_str,
                    "to_date": to_date_str,
                    "formatting": "JSON-LD",
                },
                "http_status": eto_status,
                "response": eto_resp,
                "fetch_and_store": {
                    "http_status": stored_eto_status,
                    "response": stored_eto_resp,
                },
                "option_types": {
                    "http_status": options_status,
                    "response": options_resp,
                },
                "soil_moisture": {
                    "http_status": soil_status,
                    "response": soil_resp,
                },
            },
            output_dir=output_dir,
        )

    if not eto_ok:
        notes.append(f"ETo get-calculations failed (HTTP {eto_status}). See output/irrigation/eto.json for details.")

    weather_debug: Optional[Dict[str, Any]] = None
    if not eto_ok or eto_count == 0:
        weather_debug = _run_weather_debug_probe(
            from_date_str=from_date_str,
            to_date_str=to_date_str,
            write_artifacts=write_artifacts,
            output_dir=output_dir,
        )
        if weather_debug["ok"]:
            notes.append(
                "Weather debug probe succeeded via WeatherService /api/v1/history/daily; "
                "compare output/irrigation/weather_debug.json with the irrigation ETo response to isolate ingestion gaps."
            )
        else:
            notes.append(
                "Weather debug probe failed; see output/irrigation/weather_debug.json for direct WeatherService diagnostics."
            )

    try:
        eto_preview = json.dumps(eto_resp, indent=2)[:900] if isinstance(eto_resp, (dict, list)) else str(eto_resp)[:900]
    except Exception:
        eto_preview = ""

    return {
        "ok": True,
        "notes": notes,
        "eto_summary": {
            "method": "get_calculations",
            "location_id": int(effective_location_id),
            "from_date": from_date_str,
            "to_date": to_date_str,
            "formatting": "JSON-LD",
            "http_status": eto_status,
            "ok": eto_ok,
            "count": eto_count,
            "statistics": _summarize_eto_values(eto_resp),
            "option_types": options_summary,
            "soil_moisture": {
                "http_status": soil_status,
                "ok": 200 <= soil_status < 300,
                "available": soil_resp not in ({}, None),
            },
            "artifact_path": str(paths["eto_path"]),
            "preview": eto_preview,
            "weather_debug": weather_debug,
        },
    }


def _build_bootstrap_summary(
    *,
    base_url: str,
    email: str,
    parcel_count: int,
    created_default_parcel: bool,
    eto_summary: Dict[str, Any],
    notes: List[str],
) -> Dict[str, Any]:
    """Build final bootstrap success summary payload."""
    return {
        "enabled": True,
        "base_url": base_url,
        "email": email,
        "authenticated": True,
        "parcel_count": parcel_count,
        "created_default_parcel": created_default_parcel,
        "eto": eto_summary,
        "notes": notes,
    }


def _build_bootstrap_failure_summary(
    *,
    base_url: str,
    authenticated: bool,
    email: str,
    parcel_count: int,
    created_default_parcel: bool,
    notes: List[str],
    eto_http_status: Optional[int] = None,
) -> Dict[str, Any]:
    """Build standardized bootstrap failure summary payload."""
    return {
        "enabled": True,
        "base_url": base_url,
        "authenticated": authenticated,
        "email": email,
        "parcel_count": parcel_count,
        "created_default_parcel": created_default_parcel,
        "eto": {"ok": False, "http_status": eto_http_status, "method": "get_calculations"},
        "notes": notes,
    }


# ----------------------------
# Public entry used by pipeline
# ----------------------------
def ensure_irrigation_auth_parcel_and_eto(
    *,
    eto_location_id: Optional[int] = None,
    eto_days_back: Optional[int] = None,
    write_artifacts: bool = True,
    verbose: bool = True,
    output_dir: Path | None = None,
) -> Dict[str, Any]:
    """
    Config-driven by default.
    If eto_location_id / eto_days_back are provided explicitly, they override config.yaml.
    """
    bootstrap_cfg = _resolve_bootstrap_config(
        eto_location_id=eto_location_id,
        eto_days_back=eto_days_back,
    )
    base_url = bootstrap_cfg["base_url"]
    email = bootstrap_cfg["email"]
    password = bootstrap_cfg["password"]
    wkt = bootstrap_cfg["wkt"]
    effective_location_id = bootstrap_cfg["effective_location_id"]
    effective_days_back = bootstrap_cfg["effective_days_back"]

    _ensure_output_dir(output_dir=output_dir)

    notes: List[str] = []

    if verbose:
        print("\n[Irrigation] Ensuring Irrigation service + auth + parcels + ETo...")

    try:
        _ensure_service_up(base_url, seconds=75, verbose=verbose)
    except Exception as e:
        return _build_bootstrap_failure_summary(
            base_url=base_url,
            authenticated=False,
            email="",
            parcel_count=0,
            created_default_parcel=False,
            notes=[f"Irrigation service unavailable: {e}"],
        )

    auth_result = _authenticate_irrigation(
        base_url,
        email,
        password,
        write_artifacts=write_artifacts,
        verbose=verbose,
        output_dir=output_dir,
    )
    if not auth_result["ok"]:
        return auth_result["error_summary"]

    token = auth_result["token"]
    me = auth_result["me"]
    notes.extend(auth_result["notes"])

    parcel_result = _ensure_parcel_state(
        base_url=base_url,
        token=token,
        email=me.get("email", email),
        wkt=wkt,
        write_artifacts=write_artifacts,
        output_dir=output_dir,
    )
    if not parcel_result["ok"]:
        return parcel_result["error_summary"]

    parcel_count = parcel_result["parcel_count"]
    created_default = parcel_result["created_default_parcel"]
    notes.extend(parcel_result["notes"])
    effective_location_id = _select_effective_location_id(
        configured_location_id=effective_location_id,
        locations=parcel_result.get("locations", []),
        created_default_parcel=created_default,
        notes=notes,
    )
    eto_result = _fetch_eto_state(
        base_url=base_url,
        token=token,
        effective_location_id=effective_location_id,
        effective_days_back=effective_days_back,
        write_artifacts=write_artifacts,
        verbose=verbose,
        output_dir=output_dir,
    )
    notes.extend(eto_result["notes"])

    return _build_bootstrap_summary(
        base_url=base_url,
        email=me.get("email", email),
        parcel_count=parcel_count,
        created_default_parcel=created_default,
        eto_summary=eto_result["eto_summary"],
        notes=notes,
    )


def main() -> int:
    print("=== OpenAgri Irrigation Bootstrap (Config-driven) ===")
    summary = ensure_irrigation_auth_parcel_and_eto(write_artifacts=True, verbose=True)
    print("\n[Irrigation] Summary:")
    print(json.dumps(summary, indent=2))
    print("\n=== Bootstrap complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
