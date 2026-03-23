#!/usr/bin/env python3
"""
agrivision.services.irrigation.bootstrap

Bootstraps OpenAgri Irrigation Management Service auth + parcels + ETo (official workflow).

Self-healing:
- If the Irrigation service is down (e.g., after reboot), attempt to bring it up via
  docker compose in OpenAgri-IrrigationManagement, then wait until reachable.

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
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agrivision.config.settings import get_project_root, get_settings


def _get_bootstrap_paths() -> dict[str, Path]:
    settings = get_settings()
    project_root = get_project_root()
    output_root = str(getattr(settings.paths, "output_root", "output") or "output")
    service_dir = str(getattr(settings.irrigation, "service_dir", "OpenAgri-IrrigationManagement") or "OpenAgri-IrrigationManagement")

    output_dir = project_root / output_root / "irrigation"
    token_path = output_dir / "auth_token.json"
    parcel_path = output_dir / "parcel.json"
    eto_path = output_dir / "eto.json"
    irrigation_repo_dir = project_root / service_dir
    irrigation_compose_file = irrigation_repo_dir / "compose.yaml"
    return {
        "project_root": project_root,
        "output_dir": output_dir,
        "token_path": token_path,
        "parcel_path": parcel_path,
        "eto_path": eto_path,
        "irrigation_repo_dir": irrigation_repo_dir,
        "irrigation_compose_file": irrigation_compose_file,
    }


def _ensure_output_dir() -> None:
    paths = _get_bootstrap_paths()
    paths["output_dir"].mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_token_artifact(base_url: str, token_type: str, access_token: str, email: str) -> None:
    paths = _get_bootstrap_paths()
    _write_json(
        paths["token_path"],
        {
            "base_url": base_url,
            "token_type": token_type,
            "access_token": access_token,
            "email": email,
        },
    )


def _write_parcel_artifact(payload: Dict[str, Any]) -> None:
    paths = _get_bootstrap_paths()
    _write_json(paths["parcel_path"], payload)


def _write_eto_artifact(payload: Dict[str, Any]) -> None:
    paths = _get_bootstrap_paths()
    _write_json(paths["eto_path"], payload)


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
def _is_service_up(base_url: str) -> bool:
    try:
        status, _ = _http_json("GET", f"{base_url}/api/v1/openapi.json", timeout=6)
        return 200 <= status < 300
    except Exception:
        return False


def _run_compose_up(verbose: bool = True) -> None:
    """
    Try to bring up the irrigation stack using docker compose.

    Attempts:
      1) docker compose (no sudo)
      2) sudo -n docker compose (only works if passwordless sudo is configured)
    """
    paths = _get_bootstrap_paths()
    irrigation_repo_dir = paths["irrigation_repo_dir"]
    irrigation_compose_file = paths["irrigation_compose_file"]

    if not irrigation_repo_dir.exists():
        raise FileNotFoundError(f"Irrigation repo not found at: {irrigation_repo_dir}")
    if not irrigation_compose_file.exists():
        raise FileNotFoundError(f"compose.yaml not found at: {irrigation_compose_file}")

    cmds = [
        ["docker", "compose", "-f", str(irrigation_compose_file), "up", "-d"],
        ["sudo", "-n", "docker", "compose", "-f", str(irrigation_compose_file), "up", "-d"],
    ]

    last_err = None
    for cmd in cmds:
        try:
            if verbose:
                print(f"[Irrigation] Running: {' '.join(cmd)} (cwd={irrigation_repo_dir})")
            subprocess.run(
                cmd,
                cwd=str(irrigation_repo_dir),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return
        except Exception as e:
            last_err = str(e)

    raise RuntimeError(f"Failed to start irrigation via docker compose. Last error: {last_err}")


def _ensure_service_up(base_url: str, seconds: int = 75, verbose: bool = True) -> None:
    if _is_service_up(base_url):
        if verbose:
            print("[Irrigation] ✅ Service is already reachable")
        return

    if verbose:
        print("[Irrigation] ⚠️ Service not reachable. Attempting to start via Docker Compose...")

    _run_compose_up(verbose=verbose)

    deadline = time.time() + seconds
    while time.time() < deadline:
        if _is_service_up(base_url):
            if verbose:
                print("[Irrigation] ✅ Service is reachable after startup")
            return
        time.sleep(2)

    raise RuntimeError("Service did not become reachable after docker compose up")


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
    created_default = False
    paths = _get_bootstrap_paths()

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
            "error_summary": error_summary,
        }

    locations_list: List[dict] = []
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
            _write_parcel_artifact(parcel_resp)

        status, locations_resp = _list_locations(base_url, token)
        if isinstance(locations_resp, dict) and isinstance(locations_resp.get("locations"), list):
            locations_list = locations_resp["locations"]
            parcel_count = len(locations_list)

    if write_artifacts and not paths["parcel_path"].exists():
        _write_parcel_artifact({"message": "Parcel already existed; no creation performed."})

    return {
        "ok": True,
        "parcel_count": parcel_count,
        "created_default_parcel": created_default,
        "notes": notes,
        "error_summary": None,
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
    token: Optional[str] = None
    paths = _get_bootstrap_paths()

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
                print(f"[Irrigation] ✅ Existing token valid for: {me.get('email', email)}")
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
        _write_token_artifact(base_url, token_type, token, email)

    if verbose:
        print("[Irrigation] ✅ Logged in and token stored")

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
) -> Dict[str, Any]:
    """
    Fetch ETo via get-calculations and return summary components for orchestration.
    """
    notes: List[str] = []
    paths = _get_bootstrap_paths()

    to_d = date.today()
    from_d = to_d - timedelta(days=max(1, int(effective_days_back)))
    from_date_str = from_d.isoformat()
    to_date_str = to_d.isoformat()

    if verbose:
        print(
            f"[Irrigation] Fetching ETo via get-calculations for location_id={effective_location_id} "
            f"({from_date_str} → {to_date_str})..."
        )

    eto_status, eto_resp = fetch_eto_get_calculations(
        base_url=base_url,
        token=token,
        location_id=int(effective_location_id),
        from_date=from_date_str,
        to_date=to_date_str,
        formatting="JSON",
    )
    eto_ok = 200 <= eto_status < 300

    eto_count: Optional[int] = None
    if isinstance(eto_resp, list):
        eto_count = len(eto_resp)
    elif isinstance(eto_resp, dict):
        if isinstance(eto_resp.get("calculations"), list):
            eto_count = len(eto_resp["calculations"])
        elif isinstance(eto_resp.get("eto"), list):
            eto_count = len(eto_resp["eto"])
        elif isinstance(eto_resp.get("data"), list):
            eto_count = len(eto_resp["data"])
        elif isinstance(eto_resp.get("results"), list):
            eto_count = len(eto_resp["results"])

    if write_artifacts:
        _write_eto_artifact(
            {
                "requested": {
                    "method": "get_calculations",
                    "location_id": int(effective_location_id),
                    "from_date": from_date_str,
                    "to_date": to_date_str,
                    "formatting": "JSON",
                },
                "http_status": eto_status,
                "response": eto_resp,
            }
        )

    if not eto_ok:
        notes.append(f"ETo get-calculations failed (HTTP {eto_status}). See output/irrigation/eto.json for details.")

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
            "http_status": eto_status,
            "ok": eto_ok,
            "count": eto_count,
            "artifact_path": str(paths["eto_path"]),
            "preview": eto_preview,
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

    _ensure_output_dir()

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

    auth_result = _authenticate_irrigation(base_url, email, password, write_artifacts=write_artifacts, verbose=verbose)
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
    )
    if not parcel_result["ok"]:
        return parcel_result["error_summary"]

    parcel_count = parcel_result["parcel_count"]
    created_default = parcel_result["created_default_parcel"]
    notes.extend(parcel_result["notes"])
    eto_result = _fetch_eto_state(
        base_url=base_url,
        token=token,
        effective_location_id=effective_location_id,
        effective_days_back=effective_days_back,
        write_artifacts=write_artifacts,
        verbose=verbose,
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
