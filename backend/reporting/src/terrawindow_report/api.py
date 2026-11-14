"""HTTP service. Bind it to localhost: the database URL is the credential, and this process does not authenticate callers."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from . import __version__
from .db import DatabaseError, apply_schema, connect
from .registry import get_report, get_run, insert_report, record_run, upsert_datasets
from .report import render_report
from .shapes import ReportError, ReportIn, RunIn
from .verify import verify_run


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app() -> FastAPI:
    app = FastAPI(
        title="TERRAWINDOW Research Reporting",
        version=__version__,
        description="Layer 6. Stores dataset provenance, analysis runs, candidate geometries, and research dossiers.",
    )

    @app.exception_handler(ReportError)
    async def report_error(_: Request, exc: ReportError) -> JSONResponse:
        body: dict = {"error": {"code": exc.code, "message": exc.message}}
        if exc.run_id:
            body["error"]["run_id"] = exc.run_id
        return JSONResponse(status_code=exc.status, content=body)

    @app.exception_handler(DatabaseError)
    async def database_error(_: Request, exc: DatabaseError) -> JSONResponse:
        return _error("database_unavailable", str(exc), 503)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "terrawindow-report", "version": __version__}

    @app.post("/v1/datasets/ingest")
    def ingest_datasets() -> dict:
        with connect() as conn:
            count = upsert_datasets(conn)
        return {"datasets": count}

    @app.post("/v1/runs")
    def create_run(body: RunIn) -> dict:
        with connect() as conn:
            return record_run(
                conn,
                kind=body.kind,
                request=body.request,
                result=body.result,
                engine_version=body.engine_version,
                datasets=[item.model_dump() for item in body.datasets] if body.datasets is not None else None,
            )

    @app.post("/v1/reports")
    def create_report(body: ReportIn) -> dict:
        with connect() as conn:
            run = get_run(conn, body.run_id)
            rendered = render_report(run)
            report_id = insert_report(
                conn,
                run_id=run["run_id"],
                title=rendered["title"],
                template_version=rendered["template_version"],
                generated_at=rendered["generated_at"],
                markdown=rendered["markdown"],
                pdf=rendered["pdf"],
                pdf_sha256=rendered["pdf_sha256"],
            )
        return {
            "report_id": report_id,
            "run_id": run["run_id"],
            "template_version": rendered["template_version"],
            "generated_at": rendered["generated_at"].isoformat(),
            "pdf_sha256": rendered["pdf_sha256"],
        }

    @app.get("/v1/reports/{report_id}")
    def read_report(report_id: str) -> dict:
        with connect() as conn:
            report = get_report(conn, report_id)
        return {
            "report_id": report["report_id"],
            "run_id": report["run_id"],
            "title": report["title"],
            "template_version": report["template_version"],
            "generated_at": report["generated_at"].isoformat(),
            "pdf_sha256": report["pdf_sha256"],
            "markdown": report["markdown"],
        }

    @app.get("/v1/reports/{report_id}.pdf")
    def read_pdf(report_id: str) -> Response:
        with connect() as conn:
            report = get_report(conn, report_id)
        return Response(content=report["pdf"], media_type="application/pdf")

    @app.post("/v1/runs/{run_id}/verify")
    def verify(run_id: str) -> dict:
        with connect() as conn:
            return verify_run(conn, run_id)

    @app.post("/v1/schema")
    def schema() -> dict:
        with connect() as conn:
            applied = apply_schema(conn)
        return {"statements": applied}

    return app


app = create_app()
