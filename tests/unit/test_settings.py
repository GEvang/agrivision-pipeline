from pathlib import Path

from agrivision.config import settings


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
  token: "yaml_token"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_load_config_ignores_yaml_secret_values(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    write_test_config(config_path)

    monkeypatch.setattr(settings, "_CONFIG_PATH", config_path)
    monkeypatch.delenv("WEATHER_USERNAME", raising=False)
    monkeypatch.delenv("WEATHER_PASSWORD", raising=False)
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
    monkeypatch.delenv("IRRIGATION_EMAIL", raising=False)
    monkeypatch.delenv("IRRIGATION_PASSWORD", raising=False)
    monkeypatch.delenv("IRRIGATION_TOKEN", raising=False)

    config = settings.load_config()

    assert config["weather"]["username"] == ""
    assert config["weather"]["password"] == ""
    assert config["weather"]["openweather_api_key"] == ""
    assert config["irrigation"]["auth"]["email"] == ""
    assert config["irrigation"]["auth"]["password"] == ""
    assert config["irrigation"]["token"] == ""


def test_load_config_env_overrides_yaml(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    write_test_config(config_path)

    monkeypatch.setattr(settings, "_CONFIG_PATH", config_path)

    monkeypatch.setenv("WEATHER_USERNAME", "env_user")
    monkeypatch.setenv("WEATHER_PASSWORD", "env_pass")
    monkeypatch.setenv("OPENWEATHER_API_KEY", "env_api_key")
    monkeypatch.setenv("IRRIGATION_EMAIL", "env_irrigation@example.com")
    monkeypatch.setenv("IRRIGATION_PASSWORD", "env_irrigation_pass")
    monkeypatch.setenv("IRRIGATION_TOKEN", "env_token")

    config = settings.load_config()

    assert config["weather"]["username"] == "env_user"
    assert config["weather"]["password"] == "env_pass"
    assert config["weather"]["openweather_api_key"] == "env_api_key"
    assert config["irrigation"]["auth"]["email"] == "env_irrigation@example.com"
    assert config["irrigation"]["auth"]["password"] == "env_irrigation_pass"
    assert config["irrigation"]["token"] == "env_token"


def test_load_config_returns_defaults_when_config_file_missing(monkeypatch, tmp_path):
    missing_config_path = tmp_path / "does_not_exist.yaml"
    monkeypatch.setattr(settings, "_CONFIG_PATH", missing_config_path)

    cfg = settings.load_config()

    assert isinstance(cfg, dict)
    assert "paths" in cfg
    assert "ndvi" in cfg
    assert "weather" in cfg
    assert "irrigation" in cfg


def test_get_project_root_uses_config_parent(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("weather: {}\n", encoding="utf-8")

    monkeypatch.setattr(settings, "_CONFIG_PATH", config_path)

    assert settings.get_project_root() == tmp_path.resolve()


def test_container_runtime_rewrites_loopback_service_urls(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
weather:
  base_url: "http://127.0.0.1:8010"
irrigation:
  base_url: "http://localhost:8004"
pdm:
  base_url: "http://example.test:8006"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(settings, "_CONFIG_PATH", config_path)
    monkeypatch.setenv("APP_CONTAINER_PROJECT_ROOT", "/workspace")

    cfg = settings.load_config()

    assert cfg["weather"]["base_url"] == "http://host.docker.internal:8010"
    assert cfg["irrigation"]["base_url"] == "http://host.docker.internal:8004"
    assert cfg["pdm"]["base_url"] == "http://example.test:8006"


def test_native_runtime_keeps_loopback_service_urls(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("weather:\n  base_url: \"http://127.0.0.1:8010\"\n", encoding="utf-8")

    monkeypatch.setattr(settings, "_CONFIG_PATH", config_path)
    monkeypatch.delenv("APP_CONTAINER_PROJECT_ROOT", raising=False)

    cfg = settings.load_config()

    assert cfg["weather"]["base_url"] == "http://127.0.0.1:8010"
