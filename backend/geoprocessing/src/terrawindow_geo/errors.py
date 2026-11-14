"""One error type for the whole engine, so the API can return a single error shape."""

from __future__ import annotations

from typing import Any


class GeoError(Exception):
    """A processing failure with a stable machine-readable code.

    Codes used by the engine:
      invalid_request, dataset_not_found, source_not_allowed, source_unavailable, source_unreadable,
      dataset_not_validated,
      no_data_coverage, scale_not_supported, patch_too_large, patch_too_small
    """

    def __init__(self, code: str, message: str, *, status: int = 400, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}
