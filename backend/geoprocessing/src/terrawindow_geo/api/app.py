"""FastAPI application. Run with: uvicorn terrawindow_geo.api.app:app --reload --port 8000"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .. import __version__
from ..config import get_settings
from ..errors import GeoError
from .routes import router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="TERRAWINDOW Geospatial Processing Engine",
        version=__version__,
        description=(
            "Layer 3 extracts terrain profiles with provenance and limitations. Layer 5 assesses "
            "those profiles and caller-supplied Layer 4 rehearsal evidence against explicit mission "
            "criteria; it does not recalculate Layer 4 science."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.exception_handler(GeoError)
    async def geo_error(_: Request, exc: GeoError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        issues = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        body = {"error": {"code": "invalid_request", "message": "The request body is not valid.", "details": {"issues": issues}}}
        return JSONResponse(status_code=422, content=body)

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception) -> JSONResponse:
        body = {"error": {"code": "internal_error", "message": "Unexpected processing error.", "details": {"type": type(exc).__name__}}}
        return JSONResponse(status_code=500, content=body)

    app.include_router(router)
    return app


app = create_app()
