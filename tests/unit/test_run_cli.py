from __future__ import annotations

import subprocess

import pytest

import run
from agrivision.app import cli


def test_run_module_exposes_main():
    assert hasattr(run, "main")
    assert callable(run.main)


def test_run_module_exposes_load_local_env():
    assert hasattr(run, "load_local_env")
    assert callable(run.load_local_env)


def test_cli_dashboard_start_invokes_uvicorn(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool = False):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(cli, 'load_local_env', lambda: None)
    monkeypatch.setattr(cli, 'parse_args', lambda: cli.build_parser().parse_args(['--serve-dashboard', '--host', '0.0.0.0', '--port', '8011']))
    monkeypatch.setattr(cli.subprocess, 'run', fake_run)

    cli.main()

    assert calls == [[
        cli.sys.executable,
        '-m',
        'uvicorn',
        'agrivision.app.api:app',
        '--host',
        '0.0.0.0',
        '--port',
        '8011',
    ]]


def test_cli_dashboard_start_exits_non_zero_when_uvicorn_fails(monkeypatch) -> None:
    def fake_run(cmd: list[str], check: bool = False):
        return subprocess.CompletedProcess(cmd, 3)

    monkeypatch.setattr(cli, 'load_local_env', lambda: None)
    monkeypatch.setattr(cli, 'parse_args', lambda: cli.build_parser().parse_args(['--serve-dashboard']))
    monkeypatch.setattr(cli.subprocess, 'run', fake_run)

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 3
