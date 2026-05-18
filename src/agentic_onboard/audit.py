"""SQLite-backed audit log and DLQ.

The audit log writes the *next* step of the pipeline before that step runs,
so a crash mid-record always leaves the database in a state that's safe to
replay. The DLQ is a separate table that holds records the orchestrator could
not push to the CRM (after retries) plus enough context (last error, attempt
count, original payload) to retry them later.

We use plain ``sqlite3`` from the stdlib — no ORM. Three reasons:

1. The schema is tiny (two tables, a handful of indexes); an ORM is overhead.
2. SQLite's WAL mode + autocommit gives us crash-safety without ceremony.
3. Recruiters reading this can see every SQL statement at a glance.

The store opens one connection per process and serializes writes with a
``threading.Lock``. SQLite already serialises writers across connections, but
the explicit lock makes the intent obvious and lets us batch under one BEGIN
when a hot loop wants to.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .schemas import RecordStatus

# --- Schema -----------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    total       INTEGER DEFAULT 0,
    succeeded   INTEGER DEFAULT 0,
    duplicates  INTEGER DEFAULT 0,
    human_review INTEGER DEFAULT 0,
    parse_failed INTEGER DEFAULT 0,
    dlq         INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    customer_id TEXT,
    step        TEXT NOT NULL,         -- 'ingested' | 'parsed' | 'mapped' | 'pushed' | 'failed'
    status      TEXT NOT NULL,         -- RecordStatus value or 'in_progress'
    detail      TEXT,                  -- JSON string
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_audit_log_run ON audit_log(run_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_source ON audit_log(source_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_step ON audit_log(step);

CREATE TABLE IF NOT EXISTS dlq (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    customer_id   TEXT,
    payload       TEXT NOT NULL,        -- JSON of CRMUpsertRequest
    last_error    TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    last_tried_at TEXT NOT NULL,
    next_retry_at TEXT,
    UNIQUE(run_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_dlq_run ON dlq(run_id);
CREATE INDEX IF NOT EXISTS idx_dlq_next ON dlq(next_retry_at);
"""


# --- Store -----------------------------------------------------------------


class AuditStore:
    """Thin wrapper around a single SQLite database for audit + DLQ tables.

    The DB path comes from ``settings.database_url`` (``sqlite:///<path>``).
    Tables are created on first use, so a fresh checkout works with zero
    bootstrap. Use :func:`open_default` to construct one from settings.
    """

    def __init__(self, db_path: Path | str):
        self._path = Path(str(db_path))
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            self._path,
            isolation_level=None,  # autocommit
            check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    # --- lifecycle ---

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
            finally:
                cur.close()

    # --- runs ---

    def start_run(self) -> str:
        """Create a fresh run row and return the run_id."""
        run_id = uuid.uuid4().hex
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO runs (run_id, started_at) VALUES (?, ?)",
                (run_id, _now_iso()),
            )
        return run_id

    def finalize_run(self, run_id: str, *, counters: dict[str, int]) -> None:
        """Write final counters when the orchestrator's loop exits."""
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE runs SET
                    finished_at = ?,
                    total = ?, succeeded = ?, duplicates = ?,
                    human_review = ?, parse_failed = ?, dlq = ?
                WHERE run_id = ?
                """,
                (
                    _now_iso(),
                    counters.get("total", 0),
                    counters.get("succeeded", 0),
                    counters.get("duplicates", 0),
                    counters.get("human_review", 0),
                    counters.get("parse_failed", 0),
                    counters.get("dlq", 0),
                    run_id,
                ),
            )

    # --- audit log ---

    def log(
        self,
        *,
        run_id: str,
        source_id: str,
        step: str,
        status: str | RecordStatus,
        customer_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Append one row to the audit log. Always called *before* the step runs."""
        if isinstance(status, RecordStatus):
            status = status.value
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_log
                    (run_id, source_id, customer_id, step, status, detail, occurred_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    source_id,
                    customer_id,
                    step,
                    status,
                    json.dumps(detail) if detail else None,
                    _now_iso(),
                ),
            )

    def list_audit(self, run_id: str) -> list[sqlite3.Row]:
        with self._cursor() as cur:
            return cur.execute(
                "SELECT * FROM audit_log WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()

    # --- DLQ ---

    def dlq_put(
        self,
        *,
        run_id: str,
        source_id: str,
        payload: dict[str, Any],
        last_error: str,
        customer_id: str | None = None,
        attempt_count: int = 1,
    ) -> None:
        """Insert (or upsert) a record into the DLQ.

        The (run_id, source_id) UNIQUE makes this idempotent — replaying the
        same run will overwrite the existing entry instead of duplicating it.
        """
        now = _now_iso()
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO dlq
                    (run_id, source_id, customer_id, payload, last_error,
                     attempt_count, created_at, last_tried_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, source_id) DO UPDATE SET
                    last_error = excluded.last_error,
                    attempt_count = dlq.attempt_count + 1,
                    last_tried_at = excluded.last_tried_at
                """,
                (
                    run_id,
                    source_id,
                    customer_id,
                    json.dumps(payload),
                    last_error,
                    attempt_count,
                    now,
                    now,
                ),
            )

    def dlq_pop(self, dlq_id: int) -> None:
        """Remove a row by id (used after a successful replay)."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM dlq WHERE id = ?", (dlq_id,))

    def dlq_list(self, *, run_id: str | None = None) -> list[sqlite3.Row]:
        with self._cursor() as cur:
            if run_id is None:
                return cur.execute("SELECT * FROM dlq ORDER BY created_at DESC").fetchall()
            return cur.execute(
                "SELECT * FROM dlq WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()


# --- Helpers ---------------------------------------------------------------


def _now_iso() -> str:
    """ISO 8601 UTC timestamp suitable for SQLite storage and lex sorting."""
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def open_default(database_url: str) -> AuditStore:
    """Open an :class:`AuditStore` from a ``sqlite:///<path>`` URL.

    Anything other than the SQLite scheme raises — this project's audit DB is
    intentionally local. Swapping to Postgres is a one-class change.
    """
    if not database_url.startswith("sqlite:///"):
        raise ValueError(f"only sqlite:/// URLs are supported here, got: {database_url}")
    path = database_url.removeprefix("sqlite:///")
    return AuditStore(path)
