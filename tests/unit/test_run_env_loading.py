import os

import run


def test_load_local_env_reads_dotenv(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "WEATHER_USERNAME=env_user\n"
        "IRRIGATION_EMAIL=env_irrigation@example.com\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(run, "__file__", str(tmp_path / "run.py"))
    monkeypatch.delenv("WEATHER_USERNAME", raising=False)
    monkeypatch.delenv("IRRIGATION_EMAIL", raising=False)

    run.load_local_env()

    assert os.environ["WEATHER_USERNAME"] == "env_user"
    assert os.environ["IRRIGATION_EMAIL"] == "env_irrigation@example.com"


def test_load_local_env_does_not_override_existing_env(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "WEATHER_USERNAME=file_user\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(run, "__file__", str(tmp_path / "run.py"))
    monkeypatch.setenv("WEATHER_USERNAME", "already_set_user")

    run.load_local_env()

    assert os.environ["WEATHER_USERNAME"] == "already_set_user"