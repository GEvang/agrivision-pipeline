#!/usr/bin/env python3
"""
Compatibility entry point for AgriVision.

This module keeps the historical `python run.py` entrypoint working while
moving the actual CLI implementation into `agrivision.app.cli`.
"""

import os
from pathlib import Path

from agrivision.app.cli import main, parse_args



def load_local_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


__all__ = ["load_local_env", "main", "parse_args"]


if __name__ == "__main__":
    main()
