from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Point config, runtime settings and the project root at a throwaway folder
# before any agrivision module is imported. The settings module resolves these
# paths at import time, so without this the suite would read the operator's
# real secrets and write into the real OpenAgri service folders.
_SANDBOX = Path(tempfile.mkdtemp(prefix="agrivision-tests-"))
os.environ["AGRIVISION_CONFIG_PATH"] = str(_SANDBOX / "config.yaml")
os.environ["AGRIVISION_RUNTIME_SETTINGS_PATH"] = str(_SANDBOX / "runtime" / "settings.json")
os.environ.pop("AGRIVISION_PROJECT_ROOT", None)
os.environ.pop("APP_CONTAINER_PROJECT_ROOT", None)

_BLOCKED_COMMANDS = {"docker", "docker-compose", "docker.exe", "git", "sudo"}


def pytest_unconfigure(config: pytest.Config) -> None:
    shutil.rmtree(_SANDBOX, ignore_errors=True)


def _command_name(args: object) -> str:
    if isinstance(args, (list, tuple)) and args:
        return Path(str(args[0])).name
    if isinstance(args, str) and args.strip():
        return Path(args.split()[0]).name
    return ""


# Block Docker, git and network access for the whole session, not per test:
# code such as saving credentials starts background threads that can outlive
# the test that started them. Tests that exercise these paths monkeypatch the
# call themselves; anything reaching the real thing fails fast instead of
# restarting the operator's containers.
_real_run = subprocess.run
_real_popen = subprocess.Popen


def _guarded_run(args, *pargs, **kwargs):
    if _command_name(args) in _BLOCKED_COMMANDS:
        raise FileNotFoundError(f"{_command_name(args)} is blocked in tests")
    return _real_run(args, *pargs, **kwargs)


class _GuardedPopen(_real_popen):  # type: ignore[misc, valid-type]
    def __init__(self, args, *pargs, **kwargs):
        if _command_name(args) in _BLOCKED_COMMANDS:
            raise FileNotFoundError(f"{_command_name(args)} is blocked in tests")
        super().__init__(args, *pargs, **kwargs)


def _blocked_request(self, method, url, *args, **kwargs):
    raise requests.ConnectionError(f"Network access is blocked in tests: {method} {url}")


subprocess.run = _guarded_run
subprocess.Popen = _GuardedPopen
requests.sessions.Session.request = _blocked_request


@pytest.fixture(autouse=True)
def _restore_environ():
    saved_environ = dict(os.environ)
    yield
    # Some code writes os.environ directly (e.g. saving credentials), which
    # monkeypatch cannot undo.
    os.environ.clear()
    os.environ.update(saved_environ)
