from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agrivision.config.paths import to_project_path


def write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return to_project_path(path)
