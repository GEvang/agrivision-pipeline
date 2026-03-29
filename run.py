from __future__ import annotations

import os
from pathlib import Path

from agrivision.app.cli import main as _cli_main


def load_local_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    # Preserve historical contract expected by the tests and users invoking run.py.
    load_local_env()
    _cli_main()


if __name__ == '__main__':
    main()
