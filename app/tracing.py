from __future__ import annotations

import os
from typing import Any, Callable

try:
    from langfuse import get_client as _get_langfuse_client
    from langfuse import observe as _sdk_observe
except Exception:  # pragma: no cover
    _get_langfuse_client = None
    _sdk_observe = None


def tracing_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


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


class _LangfuseContextProxy:
    def _client(self) -> Any | None:
        if not tracing_enabled() or _get_langfuse_client is None:
            return None
        try:
            return _get_langfuse_client()
        except Exception:
            return None

    def update_current_trace(self, **kwargs: Any) -> None:
        client = self._client()
        if client is None:
            return None

        payload = {key: value for key, value in kwargs.items() if value is not None}
        try:
            client.update_current_trace(**payload)
        except Exception:
            return None

    def update_current_observation(self, **kwargs: Any) -> None:
        client = self._client()
        if client is None:
            return None

        metadata = kwargs.get("metadata")
        usage_details = kwargs.get("usage_details")
        if usage_details is not None:
            if isinstance(metadata, dict):
                metadata = {**metadata, "usage_details": usage_details}
            elif metadata is None:
                metadata = {"usage_details": usage_details}
            else:
                metadata = {"value": metadata, "usage_details": usage_details}

        payload = {
            key: value
            for key, value in {
                "name": kwargs.get("name"),
                "input": kwargs.get("input"),
                "output": kwargs.get("output"),
                "metadata": metadata,
                "version": kwargs.get("version"),
                "level": kwargs.get("level"),
                "status_message": kwargs.get("status_message"),
            }.items()
            if value is not None
        }
        try:
            client.update_current_span(**payload)
        except Exception:
            return None


langfuse_context = _LangfuseContextProxy()
