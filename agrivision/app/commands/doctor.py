from __future__ import annotations

from agrivision.config.runtime import get_runtime_config
from agrivision.runtime.environment import get_deployment_profile


def doctor() -> dict[str, str]:
    runtime = get_runtime_config()
    return {
        'deployment_profile': get_deployment_profile(),
        'project_root': runtime['project_root'],
        'weather_base_url': runtime['weather_base_url'],
        'irrigation_base_url': runtime['irrigation_base_url'],
        'pdm_base_url': runtime.get('pdm_base_url', ''),
    }
