from __future__ import annotations

import json

from agrivision.app import cli


def test_cli_doctor_mode_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(cli, 'load_local_env', lambda: None)
    monkeypatch.setattr(cli, 'parse_args', lambda: type('Args', (), {
        'doctor': True,
        'setup_services': False,
        'cleanup': False,
        'skip_odm': False,
        'skip_vegetation_index': False,
    })())

    cli.main()
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert 'deployment_profile' in payload
