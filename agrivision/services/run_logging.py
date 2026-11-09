"""Send each pipeline thread's output to its own run log.

``contextlib.redirect_stdout`` swaps ``sys.stdout`` for the whole process, so
output from the web server or any other thread lands in whichever run log is
open. Instead, ``sys.stdout`` and ``sys.stderr`` are replaced once with streams
that write to the calling thread's run log when it has one, and to the
original stream otherwise.
"""

from __future__ import annotations

import io
import sys
import threading
from contextlib import contextmanager
from typing import IO, Iterator

_local = threading.local()
_install_lock = threading.Lock()


class _ThreadRoutedStream(io.TextIOBase):
    def __init__(self, fallback: IO[str]) -> None:
        self._fallback = fallback

    def _target(self) -> IO[str]:
        return getattr(_local, "stream", None) or self._fallback

    def write(self, text: str) -> int:
        return self._target().write(text)

    def flush(self) -> None:
        self._target().flush()

    def fileno(self) -> int:
        # Lets subprocess.run(stdout=sys.stdout) write straight into the run log.
        return self._target().fileno()

    def isatty(self) -> bool:
        return self._target().isatty()

    @property
    def encoding(self) -> str:  # type: ignore[override]
        return getattr(self._target(), "encoding", None) or "utf-8"


def _install() -> None:
    with _install_lock:
        if not isinstance(sys.stdout, _ThreadRoutedStream):
            sys.stdout = _ThreadRoutedStream(sys.stdout)
        if not isinstance(sys.stderr, _ThreadRoutedStream):
            sys.stderr = _ThreadRoutedStream(sys.stderr)


@contextmanager
def thread_output_to(stream: IO[str]) -> Iterator[None]:
    """Route this thread's stdout and stderr to ``stream`` for the block."""
    _install()
    previous = getattr(_local, "stream", None)
    _local.stream = stream
    try:
        yield
    finally:
        _local.stream = previous
