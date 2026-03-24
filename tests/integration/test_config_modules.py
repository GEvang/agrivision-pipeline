from __future__ import annotations

from agrivision.config.pipeline import get_pipeline_config
from agrivision.config.runtime import get_runtime_config
from agrivision.config.services import get_service_config


def test_split_config_modules_return_expected_keys():
    assert 'paths' in get_pipeline_config()
    assert 'project_root' in get_runtime_config()
    assert 'weather' in get_service_config()
