from __future__ import annotations

from dataclasses import fields, is_dataclass

from agrivision.config import settings
from agrivision.config.runtime import get_runtime_config


def test_runtime_config_reports_project_root():
    assert 'project_root' in get_runtime_config()


def _assert_matches_defaults(settings_type, defaults, path="") -> None:
    names = {item.name for item in fields(settings_type)}
    assert names == set(defaults), f"{path or 'config'}: dataclass fields and DEFAULT_CONFIG keys differ"
    hints = settings.get_type_hints(settings_type)
    for item in fields(settings_type):
        if is_dataclass(hints[item.name]):
            _assert_matches_defaults(hints[item.name], defaults[item.name], f"{path}{item.name}.")


def test_typed_settings_and_default_config_cannot_drift():
    _assert_matches_defaults(settings.AppSettings, settings.DEFAULT_CONFIG)


def test_settings_parse_boolean_strings(monkeypatch):
    config = settings._deep_merge(
        settings.DEFAULT_CONFIG,
        {
            "pdm": {"verify_ssl": "false", "enabled_by_default": "no", "allow_per_run_override": "0"},
            "app": {"min_free_disk_gb": -5, "max_active_odm_runs": 0},
            "location": {"reverse_geocode": "off"},
        },
    )
    monkeypatch.setattr(settings, "load_config", lambda: config)

    typed = settings.get_settings()

    assert typed.pdm.verify_ssl is False
    assert typed.pdm.enabled_by_default is False
    assert typed.pdm.allow_per_run_override is False
    assert typed.location.reverse_geocode is False
    assert typed.app.min_free_disk_gb == 0
    assert typed.app.max_active_odm_runs == 1
