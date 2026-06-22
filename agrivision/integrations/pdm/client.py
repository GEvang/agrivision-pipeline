from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from requests import Response, Session

from agrivision.config.settings import get_project_root, load_config
from agrivision.services.pdm.catalog import get_pdm_model
from agrivision.services.pdm.runtime import ensure_service_available

FIELD_TO_UNIT_ID = {
    'temperature_c': 1,
    'relative_humidity_pct': 5,
    'precipitation_mm': 7,
}

# Best-effort mapping inferred from the public API examples.
OPERATOR_TO_ID = {
    '>=': 1,
    '>': 1,
    '<=': 2,
    '<': 2,
    '==': 5,
}


@dataclass
class PdmServiceConfig:
    enabled_by_default: bool
    base_url: str
    timeout_seconds: int
    username: str
    password: str
    verify_ssl: bool
    token: str


class PdmApiError(RuntimeError):
    pass


class PdmAuthenticationError(PdmApiError):
    pass


class PdmClient:
    def __init__(self, config: PdmServiceConfig | None = None) -> None:
        self.config = config or get_pdm_service_config()
        self.session = Session()
        self.session.headers.update({'Accept': 'application/json'})
        self._token: str = self.config.token

    def register_user(self) -> dict[str, Any]:
        if not self.config.username or not self.config.password:
            raise PdmAuthenticationError('PDM credentials are not configured.')
        response = self._request(
            'POST',
            '/api/v1/user/register/',
            json={'email': self.config.username, 'password': self.config.password},
            expected_ok=False,
        )
        if response.ok:
            return response.json() if response.content else {'registered': True}
        # Treat already-exists style responses as non-fatal so bootstrap stays idempotent.
        text = response.text[:500].lower()
        if response.status_code in {400, 409} and any(token in text for token in ('already', 'exists', 'registered', 'taken')):
            return {'registered': False, 'already_exists': True, 'status_code': response.status_code, 'detail': response.text[:500]}
        raise PdmAuthenticationError(f'PDM registration failed with HTTP {response.status_code}: {response.text[:500]}')

    def _url(self, path: str) -> str:
        return f"{self.config.base_url.rstrip('/')}{path}"

    def _request(self, method: str, path: str, *, expected_ok: bool = True, **kwargs: Any) -> Response:
        timeout = kwargs.pop('timeout', self.config.timeout_seconds)
        verify = kwargs.pop('verify', self.config.verify_ssl)
        response = self.session.request(method, self._url(path), timeout=timeout, verify=verify, **kwargs)
        if expected_ok and not response.ok:
            raise PdmApiError(f'{method} {path} failed with HTTP {response.status_code}: {response.text[:500]}')
        return response

    def _authorize(self) -> None:
        if self._token:
            self.session.headers['Authorization'] = f'Bearer {self._token}'

    def _login_once(self) -> dict[str, Any]:
        response = self._request(
            'POST',
            '/api/v1/login/access-token/',
            data={'username': self.config.username, 'password': self.config.password},
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            expected_ok=False,
        )
        if not response.ok:
            raise PdmAuthenticationError(f'PDM login failed with HTTP {response.status_code}: {response.text[:500]}')
        payload = response.json() if response.content else {}
        token = payload.get('access_token') or payload.get('jwt_token') or payload.get('access') or ''
        if not token:
            raise PdmAuthenticationError('PDM login succeeded but no access token was returned.')
        self._token = token
        self._authorize()
        return {'authenticated': True, 'token_acquired': True, 'used_existing_token': False}

    def login(self) -> dict[str, Any]:
        if self._token:
            self._authorize()
            return {'authenticated': True, 'token_acquired': True, 'used_existing_token': True}
        if not self.config.username or not self.config.password:
            raise PdmAuthenticationError('PDM credentials are not configured.')
        try:
            return self._login_once()
        except PdmAuthenticationError as exc:
            self.register_user()
            try:
                result = self._login_once()
            except PdmAuthenticationError:
                raise exc
            result['registered_before_login'] = True
            return result

    def probe(self) -> dict[str, Any]:
        summary = {
            'base_url': self.config.base_url,
            'reachable': False,
            'http_status': None,
            'authenticated': False,
            'token_acquired': bool(self._token),
            'notes': [],
        }
        if not self.config.base_url:
            summary['notes'].append('PDM base URL not configured.')
            return summary
        for path in ('/openapi.json', '/docs', '/health'):
            try:
                response = self._request('GET', path, expected_ok=False)
                summary['http_status'] = response.status_code
                if response.status_code < 500:
                    summary['reachable'] = True
                    break
            except requests.RequestException as exc:
                summary['notes'].append(f'Service probe failed for {path}: {exc}')
        if not summary['reachable']:
            return summary
        try:
            login = self.login()
            summary['authenticated'] = bool(login.get('authenticated'))
            summary['token_acquired'] = bool(login.get('token_acquired'))
        except Exception as exc:  # noqa: BLE001
            summary['notes'].append(str(exc))
        return summary

    def supports_fuzzy_risk(self) -> bool:
        try:
            payload = self._request('GET', '/api/v1/openapi.json', expected_ok=False).json()
        except Exception:
            return False
        paths = payload.get('paths', {}) if isinstance(payload, dict) else {}
        return '/api/v1/fuzzy-risk/forecast/' in paths or '/api/v1/fuzzy-risk/historical/' in paths

    def list_crops(self) -> list[dict[str, Any]]:
        payload = self._request('GET', '/api/v1/crop/').json()
        return payload if isinstance(payload, list) else []

    def list_threat_models(self, *, crop_id: str | None = None) -> list[dict[str, Any]]:
        path = '/api/v1/threat-model/'
        if crop_id:
            path = f'{path}?crop_id={crop_id}'
        payload = self._request('GET', path).json()
        return payload if isinstance(payload, list) else []

    def list_pest_models(self) -> list[dict[str, Any]]:
        payload = self._request('GET', '/api/v1/pest-model/').json()
        pests = payload.get('pests', []) if isinstance(payload, dict) else []
        return pests if isinstance(pests, list) else []

    def list_parcels(self) -> list[dict[str, Any]]:
        payload = self._request('GET', '/api/v1/parcel/').json()
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        for key in ('elements', 'parcels', 'items', 'results', 'data'):
            parcels = payload.get(key, [])
            if isinstance(parcels, list):
                return parcels
        return []

    def create_pest_model(self, *, name: str, description: str, geo_areas_of_application: str, crop: str) -> dict[str, Any]:
        payload = {
            'name': name,
            'description': description,
            'geo_areas_of_application': geo_areas_of_application,
            'cultivations': [crop],
        }
        response = self._request('POST', '/api/v1/pest-model/', json=payload)
        return response.json() if response.content else {}

    def list_rules(self) -> list[dict[str, Any]]:
        payload = self._request('GET', '/api/v1/rule/').json()
        rules = payload.get('rules', []) if isinstance(payload, dict) else []
        return rules if isinstance(rules, list) else []

    def create_rule(self, *, pest_model_id: str, name: str, description: str, probability_value: str, conditions: list[dict[str, Any]]) -> dict[str, Any]:
        probability_map = {
            'low': 'low',
            'medium': 'moderate',
            'moderate': 'moderate',
            'high': 'high',
        }
        payload = {
            'name': name,
            'description': description,
            'probability_value': probability_map.get(probability_value.lower(), probability_value.lower()),
            'pest_model_id': pest_model_id,
            'conditions': conditions,
        }
        response = self._request('POST', '/api/v1/rule/', json=payload)
        return response.json() if response.content else {}

    def create_parcel_wkt(self, *, name: str, wkt_polygon: str) -> dict[str, Any]:
        payload = {'name': name, 'wkt_polygon': wkt_polygon}
        response = self._request('POST', '/api/v1/parcel/wkt-format/', json=payload)
        try:
            return response.json() if response.content else {}
        except ValueError:
            return {'message': response.text}

    def create_parcel_lat_lon(self, *, name: str, latitude: float, longitude: float, timeout: int | None = None) -> dict[str, Any]:
        payload = {'name': name, 'latitude': latitude, 'longitude': longitude}
        response = self._request('POST', '/api/v1/parcel/', json=payload, timeout=timeout or max(self.config.timeout_seconds, 90))
        try:
            return response.json() if response.content else {}
        except ValueError:
            return {'message': response.text}

    def upload_weather_dataset(self, *, parcel_id: int, records: list[dict[str, Any]]) -> dict[str, Any]:
        response = self._request('POST', f'/api/v1/data/{parcel_id}/', json=records)
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = {'message': response.text}
        if isinstance(payload, dict):
            payload.setdefault('uploaded', True)
            payload.setdefault('record_count', len(records))
            payload.setdefault('parcel_id', parcel_id)
            return payload
        return {'uploaded': True, 'record_count': len(records), 'parcel_id': parcel_id, 'response': payload}

    def calculate_risk_index(
        self,
        *,
        parcel_id: int,
        model_ids: list[str],
        from_date: str,
        to_date: str,
        high_only: bool = False,
    ) -> dict[str, Any]:
        suffix = 'high' if high_only else 'verbose'
        model_segment = ','.join(model_ids)
        path = (
            f"/api/v1/tool/calculate-risk-index/weather/{parcel_id}/model/{model_segment}/"
            f"{suffix}/{from_date}/from/{to_date}/to/"
        )
        response = self._request('GET', path)
        text = response.text if response.content else ''
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            try:
                payload = json.loads(text) if text else {}
            except Exception:
                payload = {'raw_text': text}
        if isinstance(payload, dict):
            payload.setdefault('_request_path', path)
            return payload
        if isinstance(payload, list):
            return {'entries': payload, '_request_path': path}
        return {'raw_text': text, '_request_path': path}

    def calculate_fuzzy_risk(
        self,
        *,
        parcel_id: int,
        threat_model_ids: list[str],
        from_date: str | None = None,
        to_date: str | None = None,
        days_ahead: int = 7,
        mode: str = 'historical',
    ) -> dict[str, Any]:
        if mode == 'forecast' or not from_date or not to_date:
            path = '/api/v1/fuzzy-risk/forecast/?format=json-ld'
            payload = {
                'parcel_id': parcel_id,
                'threat_model_ids': threat_model_ids,
                'days_ahead': days_ahead,
            }
        else:
            path = '/api/v1/fuzzy-risk/historical/?format=json-ld'
            payload = {
                'parcel_id': parcel_id,
                'threat_model_ids': threat_model_ids,
                'from_date': from_date,
                'to_date': to_date,
            }
        response = self._request('POST', path, json=payload, timeout=max(self.config.timeout_seconds, 90))
        parsed = response.json() if response.content else {}
        if isinstance(parsed, dict):
            parsed.setdefault('_request_path', path)
            parsed.setdefault('_request_payload', payload)
            return parsed
        return {'entries': parsed, '_request_path': path, '_request_payload': payload}



def get_pdm_service_config() -> PdmServiceConfig:
    config = load_config()
    pdm_cfg = config.get('pdm', {})
    auth = pdm_cfg.get('auth', {}) if isinstance(pdm_cfg.get('auth'), dict) else {}
    irrigation = config.get('irrigation', {}) if isinstance(config.get('irrigation'), dict) else {}
    irrigation_auth = irrigation.get('auth', {}) if isinstance(irrigation.get('auth'), dict) else {}
    username = str(auth.get('username', '') or irrigation_auth.get('email', '') or '')
    password = str(auth.get('password', '') or irrigation_auth.get('password', '') or '')
    return PdmServiceConfig(
        enabled_by_default=bool(pdm_cfg.get('enabled_by_default', True)),
        base_url=str(pdm_cfg.get('base_url', '')).rstrip('/'),
        timeout_seconds=int(pdm_cfg.get('timeout_seconds', 12) or 12),
        username=username,
        password=password,
        verify_ssl=bool(pdm_cfg.get('verify_ssl', True)),
        token=str(pdm_cfg.get('token', '') or ''),
    )


def probe_pdm_service() -> dict[str, Any]:
    return PdmClient().probe()


def ensure_pdm_service_available(timeout_seconds: int = 120) -> dict[str, Any]:
    state = ensure_service_available(timeout_seconds=timeout_seconds, verbose=True)
    return {
        'repo_dir': str(state.repo_dir),
        'compose_file': str(state.compose_file),
        'ready': state.ready,
        'was_reachable': state.was_reachable,
        'restarted': state.restarted,
        'started': state.started,
    }


def _safe_filename(prefix: str) -> str:
    now = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return f'{prefix}-{now}.json'


def _artifact_dir() -> Path:
    path = get_project_root() / 'output' / 'pdm'
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_pdm_artifact(prefix: str, payload: dict[str, Any]) -> str:
    path = _artifact_dir() / _safe_filename(prefix)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return str(path)


def parcel_name_for_model(model_key: str) -> str:
    return f'agrivision-{model_key}-parcel'


def model_name_for_catalog_entry(model: dict[str, Any]) -> str:
    return f"AgriVision {model['label']}"


def rule_name(model_key: str, label: str, index: int) -> str:
    return f'{model_key}-{label.lower()}-{index}'


def _remote_conditions(local_conditions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for condition in local_conditions:
        field = str(condition.get('field') or '')
        op = str(condition.get('op') or '')
        value = condition.get('value')
        unit_id = FIELD_TO_UNIT_ID.get(field)
        if unit_id is None:
            continue
        if op == 'between' and isinstance(value, list) and len(value) == 2:
            converted.append({'unit_id': unit_id, 'operator_id': OPERATOR_TO_ID['>='], 'value': float(value[0])})
            converted.append({'unit_id': unit_id, 'operator_id': OPERATOR_TO_ID['<='], 'value': float(value[1])})
            continue
        operator_id = OPERATOR_TO_ID.get(op)
        if operator_id is None:
            continue
        converted.append({'unit_id': unit_id, 'operator_id': operator_id, 'value': float(value)})
    return converted


def ensure_remote_model(client: PdmClient, model_key: str, *, geo_wkt: str) -> dict[str, Any]:
    model = get_pdm_model(model_key)
    remote_name = model_name_for_catalog_entry(model)
    existing_models = client.list_pest_models()
    remote = next((item for item in existing_models if str(item.get('name')) == remote_name), None)
    created = False
    if remote is None:
        remote = client.create_pest_model(
            name=remote_name,
            description=str(model.get('description') or model['label']),
            geo_areas_of_application=geo_wkt,
            crop=str(model['crop']),
        )
        created = True
    remote_id = str(remote.get('id') or '')
    if not remote_id:
        raise PdmApiError(f'PDM model {remote_name} did not return an id.')

    existing_rules = client.list_rules()
    rule_names = {str(item.get('name')) for item in existing_rules}
    created_rules: list[dict[str, Any]] = []
    for index, rule in enumerate(model.get('risk_rules', []), start=1):
        remote_rule_name = rule_name(model_key, str(rule.get('label', 'risk')), index)
        if remote_rule_name in rule_names:
            continue
        conditions = _remote_conditions(list(rule.get('conditions', [])))
        if not conditions:
            continue
        created_rules.append(
            client.create_rule(
                pest_model_id=remote_id,
                name=remote_rule_name,
                description=str(rule.get('recommendation') or model.get('description') or remote_name),
                probability_value=str(rule.get('label', 'moderate')),
                conditions=conditions,
            )
        )
    return {
        'remote_model': remote,
        'created_model': created,
        'created_rules_count': len(created_rules),
        'created_rules': created_rules,
        'remote_name': remote_name,
        'remote_id': remote_id,
    }


def ensure_remote_parcel(client: PdmClient, *, model_key: str, geo_wkt: str) -> dict[str, Any]:
    name = parcel_name_for_model(model_key)
    payload = client.create_parcel_wkt(name=name, wkt_polygon=geo_wkt)
    message = payload.get('message') if isinstance(payload, dict) else None
    parcel_id = ''
    parcel_record: dict[str, Any] | None = None
    if isinstance(payload, dict):
        candidate = payload.get('id') or payload.get('parcel_id')
        if candidate not in (None, ''):
            parcel_id = str(candidate)
            parcel_record = payload
    if not parcel_id:
        try:
            matches: list[dict[str, Any]] = []
            for parcel in client.list_parcels():
                if str(parcel.get('name') or '') == name:
                    matches.append(parcel)
            if matches:
                parcel_record = max(matches, key=lambda item: int(item.get('id') or item.get('parcel_id') or 0))
                candidate = parcel_record.get('id') or parcel_record.get('parcel_id')
                if candidate not in (None, ''):
                    parcel_id = str(candidate)
        except Exception:
            pass
    if not parcel_id:
        raise PdmApiError(f'PDM parcel id could not be resolved after parcel creation. Response: {payload!r}')
    return {
        'parcel': parcel_record or payload,
        'parcel_id': parcel_id,
        'message': message or 'Parcel request submitted to PDM service.',
    }


def build_weather_dataset_records(weather_summary: dict[str, Any] | None, parcel_reference: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not weather_summary:
        return rows

    current = weather_summary.get('current_weather') or {}
    timestamp = current.get('timestamp')
    if isinstance(timestamp, str):
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    def _record(day: str, tm: str, temp: Any, humidity: Any, rain: Any) -> dict[str, Any]:
        return {
            'date': day,
            'time': tm,
            'atmospheric_temperature': temp if temp not in (None, '') else 0,
            'atmospheric_relative_humidity': humidity if humidity not in (None, '') else 0,
            'precipitation': rain if rain not in (None, '') else 0,
        }

    rows.append(_record(dt.date().isoformat(), dt.time().replace(microsecond=0).isoformat(), current.get('temperature'), current.get('humidity'), 0))

    historical = weather_summary.get('historical_daily') or {}
    data = historical.get('data') if isinstance(historical, dict) else {}
    daily = data.get('daily') if isinstance(data, dict) else {}
    dates = list(daily.get('date') or daily.get('time') or []) if isinstance(daily, dict) else []
    temps = list(daily.get('temperature_2m_mean') or daily.get('temperature_mean') or []) if isinstance(daily, dict) else []
    rains = list(daily.get('precipitation_sum') or daily.get('precipitation') or []) if isinstance(daily, dict) else []
    for idx, day in enumerate(dates):
        rows.append(_record(str(day), '12:00:00', temps[idx] if idx < len(temps) else 0, current.get('humidity'), rains[idx] if idx < len(rains) else 0))

    if len(rows) == 1:
        later = dt + timedelta(hours=1)
        rows.append(_record(later.date().isoformat(), later.time().replace(microsecond=0).isoformat(), current.get('temperature'), current.get('humidity'), 0))

    return rows


def build_weather_dataset_csv(weather_summary: dict[str, Any] | None, parcel_reference: str | None = None) -> str:
    records = build_weather_dataset_records(weather_summary, parcel_reference)
    lines = ['date;time;parcel_location;atmospheric_temperature;atmospheric_relative_humidity;precipitation']
    for item in records:
        lines.append(';'.join([
            str(item.get('date', '')),
            str(item.get('time', '')),
            str(parcel_reference or ''),
            str(item.get('atmospheric_temperature', '')),
            str(item.get('atmospheric_relative_humidity', '')),
            str(item.get('precipitation', '')),
        ]))
    return '\n'.join(lines) + ('\n' if lines else '')
