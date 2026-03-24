from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry(call: Callable[[], T], attempts: int = 3, delay_seconds: float = 1.0) -> T:
    last_exc: Exception | None = None
    for _ in range(attempts):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(delay_seconds)
    assert last_exc is not None
    raise last_exc
