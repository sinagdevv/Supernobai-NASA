"""Command line for schema, ingest, dossiers, and verification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .db import DatabaseError, apply_schema, connect
from .registry import get_run, insert_report, record_run, upsert_datasets
from .report import render_report
from .shapes import ReportError, detect_kind
from .verify import verify_run


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _print(payload: dict) -> None:
    json.dump(payload, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TERRAWINDOW Layer 6 research records")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Apply the PostGIS schema")
    sub.add_parser("ingest-store", help="Copy the Layer 2 manifest and provenance into the dataset registry")

    ingest = sub.add_parser("ingest-result", help="Record a profile, comparison, or screen JSON document")
    ingest.add_argument("path")
    ingest.add_argument("--request", help="Original analysis request JSON. Derived from the result when omitted.")
    ingest.add_argument("--kind", choices=("profile", "compare", "screen"))
    ingest.add_argument("--engine", help="Engine version. Read from the result when omitted.")

    report = sub.add_parser("report", help="Write a new dossier for a completed run")
    report.add_argument("run_id")
    report.add_argument("--pdf", help="Also write the PDF to this path")

    verify = sub.add_parser("verify", help="Check result, dataset, and PDF integrity")
    verify.add_argument("run_id")

    serve = sub.add_parser("serve", help="Serve the HTTP API on localhost")
    serve.add_argument("--port", type=int, default=8001)

    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            import uvicorn

            uvicorn.run("terrawindow_report.api:app", host="127.0.0.1", port=args.port)
            return 0
        with connect() as conn:
            if args.command == "init":
                _print({"statements": apply_schema(conn)})
            elif args.command == "ingest-store":
                _print({"datasets": upsert_datasets(conn)})
            elif args.command == "ingest-result":
                result = _load(args.path)
                request = _load(args.request) if args.request else None
                _print(
                    record_run(
                        conn,
                        kind=args.kind or detect_kind(result),
                        result=result,
                        request=request,
                        engine_version=args.engine,
                    )
                )
            elif args.command == "report":
                run = get_run(conn, args.run_id)
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
                if args.pdf:
                    Path(args.pdf).write_bytes(rendered["pdf"])
                _print(
                    {
                        "report_id": report_id,
                        "run_id": run["run_id"],
                        "template_version": rendered["template_version"],
                        "pdf_sha256": rendered["pdf_sha256"],
                        "pdf": args.pdf,
                    }
                )
            elif args.command == "verify":
                outcome = verify_run(conn, args.run_id)
                _print(outcome)
                return 0 if outcome["ok"] else 1
    except (ReportError, DatabaseError) as exc:
        message = exc.message if isinstance(exc, ReportError) else str(exc)
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
