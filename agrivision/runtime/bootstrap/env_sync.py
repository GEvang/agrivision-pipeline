from __future__ import annotations

from pathlib import Path
from typing import Mapping

from agrivision.services.runtime import EnvSyncResult, update_env_file

__all__ = ["EnvSyncResult", "update_env_file", "sync_env_file"]


def sync_env_file(env_path: Path, values: Mapping[str, str]) -> EnvSyncResult:
    return update_env_file(env_path, values)
