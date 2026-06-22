from __future__ import annotations

from types import SimpleNamespace

from agrivision.app import dependencies as deps
from agrivision.app.routes import settings as settings_routes


def test_deployment_status_reports_self_hosted_readiness(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_routes,
        'load_config',
        lambda: {
            'app': {
                'deployment_mode': 'self_hosted',
                'public_url': 'https://agrivision.example.com',
                'min_free_disk_gb': 50,
                'max_active_odm_runs': 1,
                'external_access_protection_confirmed': True,
            }
        },
    )
    monkeypatch.setattr(settings_routes, '_free_disk_gb', lambda: 120.0)
    monkeypatch.setattr(settings_routes, '_git_commit', lambda: 'abc1234')
    monkeypatch.setattr(settings_routes, '_public_health_check', lambda public_url: {'name': 'Tunnel reachability', 'state': 'ok', 'detail': 'HTTP 200 at /health'})
    monkeypatch.setattr(settings_routes, 'docker_health', lambda: {'name': 'Docker', 'state': 'ok', 'detail': '27.0.0', 'target': 'docker'})
    monkeypatch.setattr(deps, 'run_service', SimpleNamespace(list_runs=lambda: []))

    status = settings_routes.deployment_status()

    assert status['state'] == 'ok'
    assert status['deployment_mode'] == 'self_hosted'
    assert status['public_url'] == 'https://agrivision.example.com'
    assert status['free_disk_gb'] == 120.0
    assert status['disk_state'] == 'ok'
    assert status['active_odm_count'] == 0
    assert status['git_commit'] == 'abc1234'
    assert [item['state'] for item in status['cloudflare_checks']] == ['ok', 'ok', 'ok', 'ok']
    assert status['cloudflare_setup']['hostname'] == 'agrivision.example.com'
    assert 'cloudflared tunnel route dns agrivision agrivision.example.com' in status['cloudflare_setup']['commands']


def test_deployment_status_warns_when_odm_capacity_is_full(monkeypatch) -> None:
    active_run = SimpleNamespace(
        run_id='run-active',
        status='running',
        selected_steps=SimpleNamespace(run_odm=True),
    )
    monkeypatch.setattr(
        settings_routes,
        'load_config',
        lambda: {'app': {'min_free_disk_gb': 50, 'max_active_odm_runs': 1}},
    )
    monkeypatch.setattr(settings_routes, '_free_disk_gb', lambda: 60.0)
    monkeypatch.setattr(settings_routes, '_git_commit', lambda: 'abc1234')
    monkeypatch.setattr(settings_routes, 'docker_health', lambda: {'name': 'Docker', 'state': 'ok', 'detail': '27.0.0', 'target': 'docker'})
    monkeypatch.setattr(deps, 'run_service', SimpleNamespace(list_runs=lambda: [active_run]))

    status = settings_routes.deployment_status()

    assert status['state'] == 'warn'
    assert status['disk_state'] == 'warn'
    assert status['active_odm_runs'] == ['run-active']
    assert [item['state'] for item in status['cloudflare_checks']] == ['warn', 'warn', 'warn', 'down']
    assert status['cloudflare_setup']['local_service'] == 'http://localhost:8008'


def test_deployment_status_warns_when_public_url_is_not_reachable(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_routes,
        'load_config',
        lambda: {
            'app': {
                'deployment_mode': 'self_hosted',
                'public_url': 'https://agrivision.example.com',
                'min_free_disk_gb': 50,
                'max_active_odm_runs': 1,
                'external_access_protection_confirmed': True,
            }
        },
    )
    monkeypatch.setattr(settings_routes, '_free_disk_gb', lambda: 120.0)
    monkeypatch.setattr(settings_routes, '_git_commit', lambda: 'abc1234')
    monkeypatch.setattr(settings_routes, '_public_health_check', lambda public_url: {'name': 'Tunnel reachability', 'state': 'down', 'detail': 'Not reachable'})
    monkeypatch.setattr(settings_routes, 'docker_health', lambda: {'name': 'Docker', 'state': 'ok', 'detail': '27.0.0', 'target': 'docker'})
    monkeypatch.setattr(deps, 'run_service', SimpleNamespace(list_runs=lambda: []))

    status = settings_routes.deployment_status()

    assert status['state'] == 'warn'
    assert status['cloudflare_checks'][2]['state'] == 'down'


def test_deployment_status_warns_until_access_protection_is_confirmed(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_routes,
        'load_config',
        lambda: {
            'app': {
                'deployment_mode': 'self_hosted',
                'public_url': 'https://agrivision.example.com',
                'min_free_disk_gb': 50,
                'max_active_odm_runs': 1,
                'external_access_protection_confirmed': False,
            }
        },
    )
    monkeypatch.setattr(settings_routes, '_free_disk_gb', lambda: 120.0)
    monkeypatch.setattr(settings_routes, '_git_commit', lambda: 'abc1234')
    monkeypatch.setattr(settings_routes, '_public_health_check', lambda public_url: {'name': 'Tunnel reachability', 'state': 'ok', 'detail': 'HTTP 200 at /health'})
    monkeypatch.setattr(settings_routes, 'docker_health', lambda: {'name': 'Docker', 'state': 'ok', 'detail': '27.0.0', 'target': 'docker'})
    monkeypatch.setattr(deps, 'run_service', SimpleNamespace(list_runs=lambda: []))

    status = settings_routes.deployment_status()

    assert status['state'] == 'warn'
    assert status['cloudflare_checks'][3]['state'] == 'down'
