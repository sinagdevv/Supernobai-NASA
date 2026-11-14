"""Database connection and schema apply. The URL stays in the environment."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from psycopg import Connection

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema.sql"


class DatabaseError(Exception):
    pass


def database_url() -> str:
    url = os.environ.get("TERRAWINDOW_DATABASE_URL", "").strip()
    if not url:
        raise DatabaseError("TERRAWINDOW_DATABASE_URL is not set.")
    return url


def connect() -> Connection:
    try:
        conn = psycopg.connect(database_url())
    except psycopg.Error as exc:
        raise DatabaseError("The database could not be reached.") from exc
    conn.execute("SELECT set_config('search_path', 'terrawindow, public, extensions', false)")
    return conn


def statements(script: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for line in script.splitlines():
        if line.strip().startswith("--"):
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt:
                parts.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def apply_schema(conn: Connection) -> int:
    script = SCHEMA_PATH.read_text(encoding="utf-8")
    applied = 0
    for stmt in statements(script):
        conn.execute(stmt)
        applied += 1
    conn.commit()
    return applied
