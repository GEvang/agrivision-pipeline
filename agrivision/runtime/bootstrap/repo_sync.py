from __future__ import annotations

from pathlib import Path

from agrivision.services.runtime import project_service_dir


def resolve_service_repo(service_dir_name: str) -> Path:
    return project_service_dir(service_dir_name)
