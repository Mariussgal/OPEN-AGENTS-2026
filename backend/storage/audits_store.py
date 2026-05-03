"""
Audit persistence: local file (dev) or PostgreSQL (shared prod).

If DATABASE_URL is set (e.g. Render Postgres, Neon, Supabase), all
clients see the same history via GET /audits.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDITS_FILE = Path(".onchor/audits.json")


def _normalize_database_url(url: str) -> str:
    url = url.strip()
    # Render / Heroku utilisent parfois postgres:// ; psycopg attend postgresql://
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _database_url() -> str | None:
    u = (os.getenv("DATABASE_URL") or "").strip()
    return _normalize_database_url(u) if u else None


def _parse_audit_created_at(audit: dict[str, Any]) -> datetime:
    raw = audit.get("created_at")
    if isinstance(raw, str):
        try:
            s = raw.replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def load_audits_from_file() -> list[dict[str, Any]]:
    if AUDITS_FILE.exists():
        return json.loads(AUDITS_FILE.read_text())
    return []


def save_audit_to_file(audit: dict[str, Any]) -> None:
    AUDITS_FILE.parent.mkdir(parents=True, exist_ok=True)
    audits = load_audits_from_file()
    audits.insert(0, audit)
    AUDITS_FILE.write_text(json.dumps(audits, indent=2))


def _ensure_pg_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS onchor_audits (
            id TEXT PRIMARY KEY,
            body JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_onchor_audits_created_at
        ON onchor_audits (created_at DESC);
        """
    )


def load_audits_from_pg(url: str) -> list[dict[str, Any]]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _ensure_pg_table(cur)
            conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT body FROM onchor_audits ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
    return [row["body"] for row in rows]


def save_audit_to_pg(url: str, audit: dict[str, Any]) -> None:
    import psycopg
    from psycopg.types.json import Json

    aid = audit.get("id")
    if not aid:
        raise ValueError("audit record missing id")

    created = _parse_audit_created_at(audit)

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            _ensure_pg_table(cur)
            cur.execute(
                """
                INSERT INTO onchor_audits (id, body, created_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    body = EXCLUDED.body,
                    created_at = EXCLUDED.created_at;
                """,
                (str(aid), Json(audit), created),
            )
        conn.commit()


def load_audits() -> list[dict[str, Any]]:
    url = _database_url()
    if url:
        return load_audits_from_pg(url)
    return load_audits_from_file()


def save_audit(audit: dict[str, Any]) -> None:
    url = _database_url()
    if url:
        save_audit_to_pg(url, audit)
    else:
        save_audit_to_file(audit)
