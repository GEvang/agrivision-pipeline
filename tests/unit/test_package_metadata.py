from pathlib import Path

import tomllib


def test_package_declares_console_script() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]
    assert scripts["agrivision"] == "agrivision.app.cli:main"
