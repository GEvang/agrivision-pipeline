"""Store paths relative to the project, and find them again.

Records, metadata and artifact summaries are written as paths relative to the
project root (``output/runs/<id>/report.html``, always with ``/``), so they
keep working when the folder moves, on another PC, and inside the dashboard
container where the project lives at ``/app``.

Older records hold absolute paths; :func:`resolve_project_path` still finds
those by rebasing them on this project's data folders.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from agrivision.config.settings import get_project_root

DATA_FOLDERS = ("output", "runtime", "data")


def to_project_path(path: str | Path, root: Path | None = None) -> str:
    """Return ``path`` relative to the project root, or unchanged if outside it."""
    base = (root or get_project_root()).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        return PurePosixPath(*Path(path).parts).as_posix()
    try:
        return candidate.resolve().relative_to(base).as_posix()
    except ValueError:
        return str(path)


def _rebased(value: str, base: Path) -> Path | None:
    parts = value.replace("\\", "/").split("/")
    # Earliest match first: a run workspace contains its own output/ folder.
    for index, part in enumerate(parts):
        if part in DATA_FOLDERS:
            candidate = base.joinpath(*parts[index:])
            if candidate.exists():
                return candidate
    return None


def resolve_project_path(value: str | Path, root: Path | None = None) -> Path:
    """Return where a stored path lives in this project.

    Relative paths are joined to the project root. Absolute paths are used as
    they are when they exist, and otherwise rebased on the project's data
    folders (records written on another machine or in the container).
    """
    base = root or get_project_root()
    text = str(value)
    is_windows_absolute = len(text) > 2 and text[1] == ":" and text[2] in "\\/"
    if not Path(text).is_absolute() and not is_windows_absolute:
        return base / text
    path = Path(text)
    if path.exists():
        return path
    return _rebased(text, base) or path
