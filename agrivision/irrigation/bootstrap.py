#!/usr/bin/env python3
"""
agrivision.irrigation.bootstrap

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

from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List
from datetime import date, timedelta
import json
import time
import urllib.parse
import urllib.request
import urllib.error
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

OUTPUT_DIR = PROJECT_ROOT / "output" / "irrigation"
TOKEN_PATH = OUTPUT_DIR / "auth_token.json"
PARCEL_PATH = OUTPUT_DIR / "parcel.json"
ETO_PATH = OUTPUT_DIR / "eto.json"

IRRIGATION_REPO_DIR = PROJECT_ROOT / "OpenAgri-IrrigationManagement"
IRRIGATION_COMPOSE_FILE = IRRIGATION_REPO_DIR / "compose.yaml"


# ----------------------------
# Config loading (minimal YAML)
# ----------------------------
def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _naive_yaml_get(config_text: str, keys: Tuple[str, ...]) -> Optional[str]:
    lines = config_text.splitlines()
    stack: list[Tuple[int, str]] = []

    for raw in lines:
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if ":" not in line:
            continue

        k, v = line.lstrip().split(":", 1)
        k = k.strip()
        v = v.strip()

        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, k))

        if tuple(item[1] for item in stack) == keys:
            if v.startswith(("'", '"')) and v.endswith(("'", '"')) and len(v) >= 2:
                v = v[1:-1]
            return v if v != "" else None

    return None


def _load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config.yaml at: {CONFIG_PATH}")

    cfg_text = _read_text(CONFIG_PATH)

    base_url = _naive_yaml_get(cfg_text, ("irrigation", "base_url"))
    email = _naive_yaml_get(cfg_text, ("irrigation", "auth", "email"))
    password = _naive_yaml_get(cfg_text, ("irrigation", "auth", "password"))
    wkt = _naive_yaml_get(cfg_text, ("irrigation", "default_parcel_wkt"))

    eto_location_id = _naive_yaml_get(cfg_text, ("irrigation", "eto", "location_id"))
    eto_days_back = _naive_yaml_get(cfg_text, ("irrigation", "eto", "days_back"))

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

    # Defaults if not provided in config
    loc_id = int(eto_location_id) if eto_location_id and eto_location_id.isdigit() else 1
    try:
        days_back = int(eto_days_back) if eto_days_back is not None else 7
    except ValueError:
        days_back = 7

    return {
        "base_url": base_url.rstrip("/"),
        "email": email,
        "password": password,
        "wkt": wkt,
        "eto_location_id": loc_id,
        "eto_days_back": days_back,
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
    if not IRRIGATION_REPO_DIR.exists():
        raise FileNotFoundError(f"Irrigation repo not found at: {IRRIGATION_REPO_DIR}")
    if not IRRIGATION_COMPOSE_FILE.exists():
        raise FileNotFoundError(f"compose.yaml not found at: {IRRIGATION_COMPOSE_FILE}")

    cmds = [
        ["docker", "compose", "-f", str(IRRIGATION_COMPOSE_FILE), "up", "-d"],
        ["sudo", "-n", "docker", "compose", "-f", str(IRRIGATION_COMPOSE_FILE), "up", "-d"],
    ]

    last_err = None
    for cmd in cmds:
        try:
            if verbose:
                print(f"[Irrigation] Running: {' '.join(cmd)} (cwd={IRRIGATION_REPO_DIR})")
            subprocess.run(
                cmd,
                cwd=str(IRRIGATION_REPO_DIR),
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
    cfg = _load_config()
    base_url = cfg["base_url"]
    email = cfg["email"]
    password = cfg["password"]
    wkt = cfg["wkt"]

    effective_location_id = int(eto_location_id) if eto_location_id is not None else int(cfg["eto_location_id"])
    effective_days_back = int(eto_days_back) if eto_days_back is not None else int(cfg["eto_days_back"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    notes: List[str] = []
    created_default = False

    if verbose:
        print("\n[Irrigation] Ensuring Irrigation service + auth + parcels + ETo...")

    try:
        _ensure_service_up(base_url, seconds=75, verbose=verbose)
    except Exception as e:
        return {
            "enabled": True,
            "base_url": base_url,
            "authenticated": False,
            "email": "",
            "parcel_count": 0,
            "created_default_parcel": False,
            "eto": {"ok": False, "http_status": None, "method": "get_calculations"},
            "notes": [f"Irrigation service unavailable: {e}"],
        }

    token: Optional[str] = None
    if TOKEN_PATH.exists():
        try:
            token_obj = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
            token = token_obj.get("access_token")
        except Exception:
            notes.append("Existing token file unreadable; will re-login.")
            token = None

    if token:
        ok, me = _token_valid(base_url, token)
        if not ok:
            notes.append("Existing token invalid/expired; re-login required.")
            token = None
        else:
            if verbose:
                print(f"[Irrigation] ✅ Existing token valid for: {me.get('email', email)}")

    if not token:
        status, _ = _register_user(base_url, email, password)
        if not (200 <= status < 300):
            notes.append(f"Register returned HTTP {status}: continuing (user may already exist).")

        status, login_resp = _login(base_url, email, password)
        if not (200 <= status < 300):
            return {
                "enabled": True,
                "base_url": base_url,
                "authenticated": False,
                "email": "",
                "parcel_count": 0,
                "created_default_parcel": False,
                "eto": {"ok": False, "http_status": None, "method": "get_calculations"},
                "notes": [f"Irrigation login failed (HTTP {status}): {login_resp}"],
            }

        token = (login_resp or {}).get("access_token")
        if not token:
            return {
                "enabled": True,
                "base_url": base_url,
                "authenticated": False,
                "email": "",
                "parcel_count": 0,
                "created_default_parcel": False,
                "eto": {"ok": False, "http_status": None, "method": "get_calculations"},
                "notes": [f"Irrigation login response missing access_token: {login_resp}"],
            }

        token_type = (login_resp or {}).get("token_type", "bearer")

        if write_artifacts:
            TOKEN_PATH.write_text(
                json.dumps({"base_url": base_url, "token_type": token_type, "access_token": token, "email": email}, indent=2),
                encoding="utf-8",
            )

        if verbose:
            print("[Irrigation] ✅ Logged in and token stored")

    ok, me = _token_valid(base_url, token)
    if not ok:
        return {
            "enabled": True,
            "base_url": base_url,
            "authenticated": False,
            "email": "",
            "parcel_count": 0,
            "created_default_parcel": False,
            "eto": {"ok": False, "http_status": None, "method": "get_calculations"},
            "notes": ["Token validation failed after login."],
        }

    status, locations_resp = _list_locations(base_url, token)
    if not (200 <= status < 300):
        return {
            "enabled": True,
            "base_url": base_url,
            "authenticated": True,
            "email": me.get("email", email),
            "parcel_count": 0,
            "created_default_parcel": False,
            "eto": {"ok": False, "http_status": None, "method": "get_calculations"},
            "notes": [f"Failed to list locations (HTTP {status}): {locations_resp}"],
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
            return {
                "enabled": True,
                "base_url": base_url,
                "authenticated": True,
                "email": me.get("email", email),
                "parcel_count": 0,
                "created_default_parcel": False,
                "eto": {"ok": False, "http_status": None, "method": "get_calculations"},
                "notes": [f"Failed to create default parcel (HTTP {status}): {parcel_resp}"],
            }
        created_default = True
        if write_artifacts:
            PARCEL_PATH.write_text(json.dumps(parcel_resp, indent=2), encoding="utf-8")

        status, locations_resp = _list_locations(base_url, token)
        if isinstance(locations_resp, dict) and isinstance(locations_resp.get("locations"), list):
            locations_list = locations_resp["locations"]
            parcel_count = len(locations_list)

    if write_artifacts and not PARCEL_PATH.exists():
        PARCEL_PATH.write_text(
            json.dumps({"message": "Parcel already existed; no creation performed."}, indent=2),
            encoding="utf-8",
        )

    to_d = date.today()
    from_d = to_d - timedelta(days=max(1, int(effective_days_back)))
    from_date_str = from_d.isoformat()
    to_date_str = to_d.isoformat()

    if verbose:
        print(f"[Irrigation] Fetching ETo via get-calculations for location_id={effective_location_id} ({from_date_str} → {to_date_str})...")

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
        ETO_PATH.write_text(
            json.dumps(
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
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    if not eto_ok:
        notes.append(f"ETo get-calculations failed (HTTP {eto_status}). See output/irrigation/eto.json for details.")

    try:
        eto_preview = json.dumps(eto_resp, indent=2)[:900] if isinstance(eto_resp, (dict, list)) else str(eto_resp)[:900]
    except Exception:
        eto_preview = ""

    return {
        "enabled": True,
        "base_url": base_url,
        "email": me.get("email", email),
        "authenticated": True,
        "parcel_count": parcel_count,
        "created_default_parcel": created_default,
        "eto": {
            "method": "get_calculations",
            "location_id": int(effective_location_id),
            "from_date": from_date_str,
            "to_date": to_date_str,
            "http_status": eto_status,
            "ok": eto_ok,
            "count": eto_count,
            "artifact_path": str(ETO_PATH),
            "preview": eto_preview,
        },
        "notes": notes,
    }


def main() -> int:
    print("=== OpenAgri Irrigation Bootstrap (Config-driven) ===")
    summary = ensure_irrigation_auth_parcel_and_eto(write_artifacts=True, verbose=True)
    print("\n[Irrigation] Summary:")
    print(json.dumps(summary, indent=2))
    print("\n=== Bootstrap complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
