"""A restricted public front door for the TERRAWINDOW scientific API.

The scientific service (backend/geoprocessing) is built to be called by trusted code: it can read any URL a
request names and trusts the bounds it is given. This gateway is what a tunnel should point at instead. It forwards
only the ten calls the interface makes, refuses everything else, validates and bounds each request, limits rate and
concurrency, times out slow work, hides filesystem paths, and turns upstream failures into one safe error shape.
It computes nothing and changes no result.

    uvicorn terrawindow_gateway.app:app --host 127.0.0.1 --port 8787
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

UPSTREAM = os.environ.get("GATEWAY_UPSTREAM", "http://127.0.0.1:8000").rstrip("/")
ORIGINS = {o.strip() for o in os.environ.get("GATEWAY_ALLOWED_ORIGINS", "https://terrawindow.vercel.app,http://localhost:5173,http://localhost:5232,http://127.0.0.1:5232").split(",") if o.strip()}
MAX_BODY = int(os.environ.get("GATEWAY_MAX_BODY_BYTES", 2_000_000))
RATE_PER_MIN = int(os.environ.get("GATEWAY_RATE_PER_MIN", 120))
HEAVY_PER_MIN = int(os.environ.get("GATEWAY_HEAVY_PER_MIN", 12))
MAX_HEAVY = int(os.environ.get("GATEWAY_MAX_HEAVY", 2))
BUSY_WAIT_S = 2.0

# Bounds on what one request may ask for (the service enforces its own as well; these are tighter and earlier).
MAX_GEOGRAPHIC_SPAN_DEG = 1.0
MAX_NATIVE_SPAN_M = 200_000.0
SCALE_RANGE_M = (1.0, 10_000.0)
MAX_SCALES = 8
PATCH_SIZE_RANGE_M = (100.0, 20_000.0)
FORBIDDEN_KEYS = {"uri", "uris", "path", "url", "urls", "file", "files", "kernel_path", "kernel_paths"}


@dataclass(frozen=True)
class Rule:
    timeout: float
    heavy: bool = False
    exclusive: bool = False  # only one at a time (Layer 4 ray-traces whole patches)


RULES: dict[tuple[str, str], Rule] = {
    ("GET", "/health"): Rule(5),
    ("GET", "/v1/datasets"): Rule(30),
    ("GET", "/v1/rehearsal/status"): Rule(10),
    ("GET", "/v1/suitability/metrics"): Rule(10),
    ("POST", "/v1/patches/profile"): Rule(120),
    ("POST", "/v1/patches/compare"): Rule(120, heavy=True),
    ("POST", "/v1/patches/overlay"): Rule(120, heavy=True),
    ("POST", "/v1/discovery/screen"): Rule(150, heavy=True),
    ("POST", "/v1/suitability/assess"): Rule(120, heavy=True),
    ("POST", "/v1/rehearsal/evaluate"): Rule(170, heavy=True, exclusive=True),
}
ALLOWED_PATHS = {p for _, p in RULES}


def error(status: int, code: str, message: str, *, retry_after: int | None = None) -> JSONResponse:
    headers = {"Retry-After": str(retry_after)} if retry_after else None
    return JSONResponse({"error": {"code": code, "message": message, "details": {}}}, status_code=status, headers=headers)


# ---- paths: the service reports where files live on this machine; the public gets stable tokens instead ----


def _roots() -> list[tuple[str, str]]:
    here = Path(__file__).resolve()
    backend = here.parents[3]
    repo = backend.parent
    data = Path(os.environ.get("TERRAWINDOW_DATA_DIR") or backend / "data").resolve()
    kernels = Path(os.environ.get("TWGEO_KERNEL_DIR") or repo / "solar_geometry_engine" / "kernels").resolve()
    pairs = [(str(data), "<data>"), (str(kernels), "<kernels>"), (str(repo), "<repo>"), (str(Path.home()), "<home>")]
    return sorted(pairs, key=lambda p: -len(p[0]))


ROOTS = _roots()
ANY_ABSOLUTE = re.compile(r"(?:(?<![A-Za-z])[A-Za-z]:[\\/]|\\\\|(?<![:/\w])/(?:Users|home|root|etc|var|tmp)/)[^\s\"']*")


def _hide(text: str) -> str:
    for prefix, token in ROOTS:
        for variant in {prefix, prefix.replace("\\", "/"), prefix.replace("/", "\\")}:
            text = text.replace(variant, token)
    return ANY_ABSOLUTE.sub("<local path>", text)


def _restore(text: str) -> str:
    for prefix, token in ROOTS:
        if text.startswith(token):
            return prefix + text[len(token):]
    return text


def _walk(value: Any, fn) -> Any:
    if isinstance(value, dict):
        return {k: _walk(v, fn) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(v, fn) for v in value]
    return fn(value) if isinstance(value, str) else value


# ---- request validation ----


class Invalid(Exception):
    pass


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise Invalid(f"{name} must be a finite number")
    return float(value)


def _check_dataset(value: Any, allowed: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != {"id"} or not isinstance(value["id"], str):
        raise Invalid("a dataset must be given as {\"id\": ...}; paths and URLs are not accepted")
    if value["id"] not in allowed:
        raise Invalid("unknown dataset id")


def _check_bbox(box: dict[str, Any]) -> None:
    west, south, east, north = (_number(box[k], f"bbox.{k}") for k in ("west", "south", "east", "north"))
    if box.get("crs", "geographic") == "geographic":
        if not (-360 <= west <= 360 and -90 <= south <= 90 and -360 <= east <= 360 and -90 <= north <= 90):
            raise Invalid("bbox is outside the coordinate range")
        if east - west > MAX_GEOGRAPHIC_SPAN_DEG or north - south > MAX_GEOGRAPHIC_SPAN_DEG:
            raise Invalid(f"bbox may span at most {MAX_GEOGRAPHIC_SPAN_DEG} degrees")
    elif east - west > MAX_NATIVE_SPAN_M or north - south > MAX_NATIVE_SPAN_M:
        raise Invalid(f"bbox may span at most {int(MAX_NATIVE_SPAN_M / 1000)} km")


def validate(value: Any, allowed: set[str], key: str = "") -> None:
    if key == "dataset":
        _check_dataset(value, allowed)
    elif isinstance(value, dict):
        if {"west", "south", "east", "north"} <= set(value):
            _check_bbox(value)
        for k, v in value.items():
            if k.lower() in FORBIDDEN_KEYS:
                raise Invalid(f"'{k}' is not accepted")
            validate(v, allowed, k)
    elif isinstance(value, list):
        if key in ("scales_m", "relief_windows_m") and len(value) > MAX_SCALES:
            raise Invalid(f"{key} may list at most {MAX_SCALES} values")
        for v in value:
            validate(v, allowed, key)
    elif key in ("scales_m", "scale_m", "relief_windows_m") and value is not None:
        if not SCALE_RANGE_M[0] <= _number(value, key) <= SCALE_RANGE_M[1]:
            raise Invalid(f"{key} must be between {SCALE_RANGE_M[0]:g} and {SCALE_RANGE_M[1]:g} m")
    elif key == "patch_size_m" and not PATCH_SIZE_RANGE_M[0] <= _number(value, key) <= PATCH_SIZE_RANGE_M[1]:
        raise Invalid(f"patch_size_m must be between {PATCH_SIZE_RANGE_M[0]:g} and {PATCH_SIZE_RANGE_M[1]:g} m")


# ---- limits ----


class Limiter:
    """Sliding one-minute window per client and bucket. In memory: a restart resets it, which is fine for a demo."""

    def __init__(self) -> None:
        self.hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def allow(self, client: str, bucket: str, limit: int) -> int | None:
        """None if allowed, else seconds until the oldest hit leaves the window."""
        now = time.monotonic()
        window = self.hits[(client, bucket)]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit:
            return max(1, int(60 - (now - window[0])) + 1)
        window.append(now)
        return None


def create_app(upstream: httpx.AsyncClient | None = None) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)  # nothing self-describing is exposed
    client = upstream or httpx.AsyncClient(base_url=UPSTREAM, follow_redirects=False)
    limiter = Limiter()
    heavy_slots = asyncio.Semaphore(MAX_HEAVY)
    exclusive_slot = asyncio.Semaphore(1)
    datasets_cache: dict[str, Any] = {"at": 0.0, "ids": set()}

    async def allowed_datasets() -> set[str]:
        if time.monotonic() - datasets_cache["at"] > 30:
            response = await client.get("/v1/datasets", timeout=15)
            response.raise_for_status()
            stored = response.json().get("stored_datasets", [])
            datasets_cache.update(at=time.monotonic(), ids={d["id"] for d in stored if d.get("id")})
        return datasets_cache["ids"]

    def cors(response: Response, origin: str | None) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        if origin and origin in ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def gateway(path: str, request: Request) -> Response:
        origin = request.headers.get("origin")
        route = "/" + path
        if request.method == "OPTIONS":
            if route in ALLOWED_PATHS and origin in ORIGINS:
                return cors(Response(status_code=204, headers={"Access-Control-Allow-Methods": "GET, POST", "Access-Control-Allow-Headers": "content-type", "Access-Control-Max-Age": "600"}), origin)
            return error(403, "forbidden", "Not allowed.")
        if origin and origin not in ORIGINS:
            return error(403, "forbidden", "This origin may not use the service.")
        rule = RULES.get((request.method, route))
        if rule is None:
            if route in ALLOWED_PATHS:
                return cors(error(405, "method_not_allowed", "That method is not available here."), origin)
            return cors(error(404, "not_found", "No such endpoint."), origin)

        peer = request.client.host if request.client else "unknown"
        who = request.headers.get("cf-connecting-ip", peer) if peer in ("127.0.0.1", "::1") else peer
        wait = limiter.allow(who, "all", RATE_PER_MIN) or (limiter.allow(who, "heavy", HEAVY_PER_MIN) if rule.heavy else None)
        if wait:
            return cors(error(429, "rate_limited", f"Too many requests. Try again in {wait} s.", retry_after=wait), origin)

        body = b""
        if request.method == "POST":
            if int(request.headers.get("content-length") or 0) > MAX_BODY:
                return cors(error(413, "too_large", "The request is too large."), origin)
            body = await request.body()
            if len(body) > MAX_BODY:
                return cors(error(413, "too_large", "The request is too large."), origin)
            try:
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise Invalid("the body must be a JSON object")
                validate(data, await allowed_datasets())
                body = json.dumps(_walk(data, _restore)).encode()
            except Invalid as exc:
                return cors(error(422, "invalid_request", str(exc)), origin)
            except (ValueError, UnicodeDecodeError):
                return cors(error(400, "invalid_request", "The body is not valid JSON."), origin)
            except httpx.HTTPError:
                return cors(error(503, "service_unavailable", "The scientific service is not reachable."), origin)

        slots = [exclusive_slot, heavy_slots] if rule.exclusive else [heavy_slots] if rule.heavy else []
        held: list[asyncio.Semaphore] = []
        try:
            for slot in slots:
                try:
                    await asyncio.wait_for(slot.acquire(), BUSY_WAIT_S)
                    held.append(slot)
                except asyncio.TimeoutError:
                    return cors(error(503, "busy", "The service is busy with another calculation. Try again shortly.", retry_after=10), origin)
            try:
                async with asyncio.timeout(rule.timeout):
                    upstream_response = await client.request(request.method, route, content=body or None, headers={"content-type": "application/json"} if body else None, timeout=rule.timeout)
            except (httpx.TimeoutException, TimeoutError):
                return cors(error(504, "timeout", "The calculation took too long and was stopped."), origin)
            except httpx.HTTPError:
                return cors(error(503, "service_unavailable", "The scientific service is not reachable."), origin)
        finally:
            for slot in held:
                slot.release()

        kind = upstream_response.headers.get("content-type", "")
        if upstream_response.status_code >= 500 or "json" not in kind:
            return cors(error(502, "upstream_error", "The scientific service could not complete the request."), origin)
        try:
            payload = _walk(upstream_response.json(), _hide)
        except ValueError:
            return cors(error(502, "upstream_error", "The scientific service returned something unreadable."), origin)
        return cors(JSONResponse(payload, status_code=upstream_response.status_code), origin)

    return app


app = create_app()
