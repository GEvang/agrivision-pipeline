from __future__ import annotations

from pathlib import Path

from agrivision.services.runtime import find_compose_file


def resolve_compose_file(repo_dir: Path) -> Path:
    return find_compose_file(repo_dir)
