from __future__ import annotations
import os
import sqlite3
from pathlib import Path

# Default location: ~/.taskmaster/tasks.db, overridable via env var for tests.
DEFAULT_DB_PATH = Path.home() / ".taskmaster" / "tasks.db"
ENV_OVERRIDE = "TASKMASTER_DB"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    due         TEXT,                       -- ISO 8601, nullable
    priority    TEXT    NOT NULL DEFAULT 'medium',
    status      TEXT    NOT NULL DEFAULT 'pending',
    recurrence  TEXT    NOT NULL DEFAULT 'none',
    tags        TEXT    NOT NULL DEFAULT '',  -- comma-separated
    notes       TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status   ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due       ON tasks(due);
CREATE INDEX IF NOT EXISTS idx_tasks_priority  ON tasks(priority);
"""


def resolve_db_path() -> Path:
    override = os.environ.get(ENV_OVERRIDE)
    return Path(override) if override else DEFAULT_DB_PATH


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open (and initialise if needed) a SQLite connection."""
    path = db_path or resolve_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn
