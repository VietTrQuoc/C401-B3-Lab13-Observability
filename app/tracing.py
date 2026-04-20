from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Callable, Iterator

try:
    from langfuse import get_client as _get_langfuse_client
    from langfuse import observe as _sdk_observe
except Exception:  # pragma: no cover
    _get_langfuse_client = None
    _sdk_observe = None


def tracing_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def _client() -> Any | None:
    if not tracing_enabled() or _get_langfuse_client is None:
        return None
    try:
        return _get_langfuse_client()
    except Exception:
        return None


def _identity_decorator(*args: Any, **kwargs: Any):
    if args and callable(args[0]) and len(args) == 1 and not kwargs:
        return args[0]

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    return decorator


def observe(*args: Any, **kwargs: Any):
    if not tracing_enabled() or _sdk_observe is None:
        return _identity_decorator(*args, **kwargs)

    try:
        return _sdk_observe(*args, **kwargs)
    except Exception:
        return _identity_decorator(*args, **kwargs)


@contextmanager
def start_span(name: str, **attrs: Any) -> Iterator[Any | None]:
    client = _client()
    if client is None:
        yield None
        return
    try:
        with client.start_as_current_observation(as_type="span", name=name, **attrs) as span:
            yield span
    except Exception:
        yield None


@contextmanager
def start_generation(name: str, **attrs: Any) -> Iterator[Any | None]:
    client = _client()
    if client is None:
        yield None
        return
    try:
        with client.start_as_current_observation(as_type="generation", name=name, **attrs) as gen:
            yield gen
    except Exception:
        yield None


def flush() -> None:
    client = _client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        return


def score_current_trace(*, name: str, value: float, comment: str | None = None) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.score_current_trace(name=name, value=value, comment=comment)
    except Exception:
        return


class _LangfuseContextProxy:
    def update_current_trace(self, **kwargs: Any) -> None:
        client = _client()
        if client is None:
            return None

        payload = {key: value for key, value in kwargs.items() if value is not None}
        try:
            client.update_current_trace(**payload)
        except Exception:
            return None

    def update_current_span(self, **kwargs: Any) -> None:
        client = _client()
        if client is None:
            return None
        payload = {key: value for key, value in kwargs.items() if value is not None}
        try:
            client.update_current_span(**payload)
        except Exception:
            return None

    def update_current_generation(self, **kwargs: Any) -> None:
        client = _client()
        if client is None:
            return None
        payload = {key: value for key, value in kwargs.items() if value is not None}
        try:
            client.update_current_generation(**payload)
        except Exception:
            return None

    def update_current_observation(self, **kwargs: Any) -> None:
        self.update_current_span(**kwargs)


langfuse_context = _LangfuseContextProxy()
