"""Exceptions safe to surface through MCP."""

from typing import Any


class UpstreamError(RuntimeError):
    """A structured error returned by or while contacting 1C.ai."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.data = data or {}
        suffix = f" (HTTP {status_code})" if status_code is not None else ""
        super().__init__(f"{message}{suffix}")
