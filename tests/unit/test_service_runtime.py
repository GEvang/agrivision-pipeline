from pathlib import Path

from agrivision.services.runtime import update_env_file


def test_update_env_file_reports_changed_keys(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("A=1\nB=2\n", encoding="utf-8")

    sync = update_env_file(env_path, {"A": "1", "B": "3", "C": "4"})

    assert sync.changed is True
    assert set(sync.changed_keys) == {"B", "C"}
    assert env_path.read_text(encoding="utf-8") == "A=1\nB=3\nC=4\n"


def test_update_env_file_noop_when_values_match(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("A=1\n", encoding="utf-8")

    sync = update_env_file(env_path, {"A": "1"})

    assert sync.changed is False
    assert sync.changed_keys == ()
