"""Keep the package layers pointing one way.

Each layer may import from itself and the layers listed before it, never from
a later one: settings and models at the bottom, the web app at the top.
"""

from __future__ import annotations

import ast
from pathlib import Path

LAYERS = ["config", "schemas", "runtime", "integrations", "pipeline", "services", "app"]
PACKAGE = Path(__file__).resolve().parents[2] / "agrivision"


def _imported_modules(path: Path) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return modules


def test_every_package_is_assigned_a_layer() -> None:
    packages = {path.name for path in PACKAGE.iterdir() if path.is_dir() and path.name != "__pycache__"}

    assert packages == set(LAYERS)


def test_layers_only_import_downwards() -> None:
    rank = {name: index for index, name in enumerate(LAYERS)}
    violations = []
    for path in PACKAGE.rglob("*.py"):
        layer = path.relative_to(PACKAGE).parts[0]
        if layer not in rank:
            continue
        for module in _imported_modules(path):
            parts = module.split(".")
            if parts[0] == "agrivision" and len(parts) > 1 and rank.get(parts[1], -1) > rank[layer]:
                violations.append(f"{path.relative_to(PACKAGE.parent)} ({layer}) imports {module}")

    assert violations == []
