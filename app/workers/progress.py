from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

ProgressCallback = Callable[[float], None]

_callback: ContextVar[ProgressCallback | None] = ContextVar(
    "progress_callback", default=None
)


@contextmanager
def reporting_progress(callback: ProgressCallback) -> Iterator[None]:
    token = _callback.set(callback)
    try:
        yield
    finally:
        _callback.reset(token)


def report_progress(fraction: float) -> None:
    callback = _callback.get()
    if callback is not None:
        callback(min(max(fraction, 0.0), 1.0))
