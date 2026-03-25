from pathlib import Path


def test_pyproject_declares_console_script() -> None:
    content = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "[project.scripts]" in content
    assert 'agrivision = "agrivision.app.cli:main"' in content
