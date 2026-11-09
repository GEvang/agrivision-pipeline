"""Rules for IDs that become folder names on disk."""

from __future__ import annotations

import re

# Run and upload IDs become folder names, so they may only contain characters
# that can never form a path separator or "..".
SAFE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$"
_SAFE_ID = re.compile(SAFE_ID_PATTERN)


class InvalidStorageIdError(ValueError):
    """Raised when a run or upload ID could escape its storage folder."""


def validate_storage_id(value: str, *, label: str = "run ID") -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise InvalidStorageIdError(f"Invalid {label}: {value!r}")
    return value
