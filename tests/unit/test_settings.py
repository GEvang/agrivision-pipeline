import warnings
from pathlib import Path

from agrivision.utils import settings


def write_test_config(path: Path) -> None:
    path.write_text(
        """
weather:
  username: "yaml_user"
  password: "yaml_pass"
  openweather_api_key: "yaml_api_key"

irrigation:
  auth:
    email: "yaml_irrigation@example.com"
    password: "yaml_irrigation_pass"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_load_config_uses_yaml_values_when_env_not_set(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    write_test_config(config_path)

    monkeypatch.setattr(settings, "_CONFIG_PATH", config_path)

    monkeypatch.delenv("WEATHER_USERNAME", raising=False)
    monkeypatch.delenv("WEATHER_PASSWORD", raising=False)
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
    monkeypatch.delenv("IRRIGATION_EMAIL", raising=False)
    monkeypatch.delenv("IRRIGATION_PASSWORD", raising=False)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        config = settings.load_config()

    assert config["weather"]["username"] == "yaml_user"
    assert config["weather"]["password"] == "yaml_pass"
    assert config["weather"]["openweather_api_key"] == "yaml_api_key"
    assert config["irrigation"]["auth"]["email"] == "yaml_irrigation@example.com"
    assert config["irrigation"]["auth"]["password"] == "yaml_irrigation_pass"


def test_load_config_env_overrides_yaml(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    write_test_config(config_path)

    monkeypatch.setattr(settings, "_CONFIG_PATH", config_path)

    monkeypatch.setenv("WEATHER_USERNAME", "env_user")
    monkeypatch.setenv("WEATHER_PASSWORD", "env_pass")
    monkeypatch.setenv("OPENWEATHER_API_KEY", "env_api_key")
    monkeypatch.setenv("IRRIGATION_EMAIL", "env_irrigation@example.com")
    monkeypatch.setenv("IRRIGATION_PASSWORD", "env_irrigation_pass")

    config = settings.load_config()

    assert config["weather"]["username"] == "env_user"
    assert config["weather"]["password"] == "env_pass"
    assert config["weather"]["openweather_api_key"] == "env_api_key"
    assert config["irrigation"]["auth"]["email"] == "env_irrigation@example.com"
    assert config["irrigation"]["auth"]["password"] == "env_irrigation_pass"

def test_load_config_returns_defaults_when_config_file_missing(monkeypatch, tmp_path):
    missing_config_path = tmp_path / "does_not_exist.yaml"
    monkeypatch.setattr(settings, "_CONFIG_PATH", missing_config_path)

    cfg = settings.load_config()

    assert isinstance(cfg, dict)
    assert "paths" in cfg
    assert "ndvi" in cfg
    assert "weather" in cfg
    assert "irrigation" in cfg
