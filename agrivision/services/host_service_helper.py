from __future__ import annotations

import re
import time
import uuid
from pathlib import Path

from agrivision.config.settings import get_project_root
from agrivision.services.runtime import ServiceBootstrapError

_HEARTBEAT_TTL_SECONDS = 15
_COMMAND_TIMEOUT_SECONDS = 240
# A first install clones the service repo, pulls its images and builds
# Irrigation from source, which can take well over 4 minutes on a slow link.
INSTALL_TIMEOUT_SECONDS = 900


def helper_root() -> Path:
    return get_project_root() / "runtime" / "service-helper"


def _commands_dir() -> Path:
    return helper_root() / "commands"


def _responses_dir() -> Path:
    return helper_root() / "responses"


def _status_file() -> Path:
    return helper_root() / "helper.env"


def _service_file(service_key: str) -> Path:
    return helper_root() / "services" / f"{service_key}.env"


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def helper_state() -> dict[str, object]:
    payload = _parse_env_file(_status_file())
    timestamp_raw = payload.get("TIMESTAMP_EPOCH", "")
    try:
        timestamp = int(timestamp_raw)
    except ValueError:
        timestamp = 0
    available = bool(timestamp) and (time.time() - timestamp) <= _HEARTBEAT_TTL_SECONDS
    return {
        "available": available,
        "reason": (
            ""
            if available
            else (
                "Dashboard service controls require the host helper. Start AgriVision from the OS launcher so the helper starts with it."
            )
        ),
        "mode": payload.get("MODE", ""),
    }


def _local_log_path(reported: str) -> Path | None:
    """Map the helper's host log path to this process's view of the helper folder.

    The helper reports host paths (``C:\\...`` on Windows), which do not exist
    inside the dashboard container, so fall back to the same file name under
    the bind-mounted helper logs folder.
    """
    if not reported:
        return None
    reported_path = Path(reported)
    if reported_path.exists():
        return reported_path
    return helper_root() / "logs" / re.split(r"[\\/]", reported)[-1]


def installed_service_state(service_key: str) -> dict[str, str]:
    return _parse_env_file(_service_file(service_key))


def submit_command(
    *,
    action: str,
    service_key: str | None = None,
    timeout_seconds: int = _COMMAND_TIMEOUT_SECONDS,
) -> None:
    state = helper_state()
    if not state["available"]:
        raise ServiceBootstrapError(str(state["reason"]))

    request_id = uuid.uuid4().hex
    _commands_dir().mkdir(parents=True, exist_ok=True)
    _responses_dir().mkdir(parents=True, exist_ok=True)

    command_file = _commands_dir() / f"{request_id}.env"
    response_file = _responses_dir() / f"{request_id}.env"
    command_lines = [
        f"REQUEST_ID={request_id}",
        f"ACTION={action}",
    ]
    if service_key:
        command_lines.append(f"SERVICE_KEY={service_key}")
    command_file.write_text("\n".join(command_lines) + "\n", encoding="utf-8")

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if response_file.exists():
            payload = _parse_env_file(response_file)
            ok = payload.get("OK", "").lower() in {"1", "true", "yes", "ok"}
            log_path = _local_log_path(payload.get("LOG_PATH", ""))
            message = payload.get("MESSAGE", "Host helper did not return a message.")
            if not ok:
                if log_path and log_path.exists():
                    tail = log_path.read_text(encoding="utf-8", errors="ignore")[-8000:]
                    raise ServiceBootstrapError(f"{message}\n\n{tail}")
                raise ServiceBootstrapError(message)
            return
        time.sleep(1)

    raise ServiceBootstrapError("Timed out waiting for the host helper to complete the service action.")
