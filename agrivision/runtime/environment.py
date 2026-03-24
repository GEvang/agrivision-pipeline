from __future__ import annotations

import os
from pathlib import Path

ENV_DEPLOYMENT_PROFILE = "AGRIVISION_DEPLOYMENT_PROFILE"


def get_deployment_profile(default: str = "standalone") -> str:
    return os.getenv(ENV_DEPLOYMENT_PROFILE, default).strip() or default


def repo_root_from(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()
