"""Stable JSON used for request hashes, result hashes, and PDF checksums."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def sanitize(value: Any) -> Any:
    """Drop NaN and Infinity, and collapse whole-number floats so a jsonb round-trip hashes the same."""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        if value.is_integer():
            return int(value)
        return value
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    cleaned = sanitize(value)
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def request_document(kind: str, request: dict) -> dict:
    return {"kind": kind, "request": sanitize(request)}


def request_hash(kind: str, request: dict) -> str:
    return sha256_text(canonical_json(request_document(kind, request)))


def result_hash(result: dict) -> str:
    return sha256_text(canonical_json(result))


def input_fingerprint(links: list[dict]) -> list[list[str]]:
    """Sorted [role, dataset id, sha256] rows. This is the cache key's dataset half."""
    rows = [[item["role"], item["dataset_id"], item["sha256"]] for item in links]
    return sorted(rows, key=lambda row: (row[0], row[1], row[2]))
