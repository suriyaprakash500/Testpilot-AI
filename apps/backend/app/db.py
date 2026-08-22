"""SQLite-backed persistence for projects, test runs, and test cases.

Replaces the previous in-memory Python lists so that data survives
backend restarts and cannot be wiped by duplicate server instances.
"""
import sqlite3
import threading
from typing import Any, Dict, List, Optional

_DB_PATH = "testpilot.db"

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    repoUrl TEXT NOT NULL,
    websiteUrl TEXT NOT NULL,
    testEmail TEXT,
    status TEXT DEFAULT 'active',
    createdAt TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    projectId TEXT NOT NULL,
    status TEXT DEFAULT 'analyzing',
    trigger TEXT DEFAULT 'manual',
    startedAt TEXT,
    completedAt TEXT,
    prUrl TEXT,
    createdAt TEXT,
    plannedTotal INTEGER,
    passedFirstPass INTEGER,
    failedFirstPass INTEGER,
    passedFinal INTEGER,
    failedFinal INTEGER,
    inconclusiveFinal INTEGER,
    repairedCount INTEGER,
    appBugCount INTEGER,
    retryCount INTEGER,
    timeline TEXT
);
CREATE TABLE IF NOT EXISTS test_cases (
    id TEXT PRIMARY KEY,
    testRunId TEXT NOT NULL,
    name TEXT,
    status TEXT,
    duration REAL DEFAULT 0,
    error TEXT,
    logs TEXT,
    code TEXT,
    screenshotUrl TEXT,
    createdAt TEXT
);
"""

# Columns added after the initial schema. ALTER TABLE is idempotent-guarded
# so existing databases are migrated in place on first connect.
_RUN_MIGRATION_COLUMNS = [
    ("plannedTotal", "INTEGER"),
    ("passedFirstPass", "INTEGER"),
    ("failedFirstPass", "INTEGER"),
    ("passedFinal", "INTEGER"),
    ("failedFinal", "INTEGER"),
    ("inconclusiveFinal", "INTEGER"),
    ("repairedCount", "INTEGER"),
    ("appBugCount", "INTEGER"),
    ("retryCount", "INTEGER"),
    ("timeline", "TEXT"),
]


def _migrate_runs_table(conn: sqlite3.Connection) -> None:
    """Adds any missing run-summary columns to an existing runs table."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
    for name, coltype in _RUN_MIGRATION_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {name} {coltype}")


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_SCHEMA)
        _migrate_runs_table(_conn)
        _conn.commit()
    return _conn


def _to_dicts(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]


# ---------------- Projects ----------------

def insert_project(project: Dict[str, Any]) -> None:
    with _lock:
        _get_conn().execute(
            "INSERT INTO projects (id, name, repoUrl, websiteUrl, testEmail, status, createdAt) "
            "VALUES (:id, :name, :repoUrl, :websiteUrl, :testEmail, :status, :createdAt)",
            project,
        )
        _get_conn().commit()


def list_projects() -> List[Dict[str, Any]]:
    with _lock:
        rows = _get_conn().execute("SELECT * FROM projects ORDER BY createdAt DESC").fetchall()
    return _to_dicts(rows)


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        row = _get_conn().execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return dict(row) if row else None


def update_project(project_id: str, fields: Dict[str, Any]) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    fields = {**fields, "id": project_id}
    with _lock:
        _get_conn().execute(f"UPDATE projects SET {sets} WHERE id = :id", fields)
        _get_conn().commit()


def cascade_delete_project(project_id: str) -> int:
    """Deletes a project plus every run and test case belonging to it. Returns number of runs removed."""
    with _lock:
        conn = _get_conn()
        run_rows = conn.execute(
            "SELECT id FROM runs WHERE projectId = ?", (project_id,)
        ).fetchall()
        run_ids = [r["id"] for r in run_rows]

        if run_ids:
            placeholders = ",".join("?" for _ in run_ids)
            conn.execute(
                f"DELETE FROM test_cases WHERE testRunId IN ({placeholders})",
                run_ids,
            )
        conn.execute("DELETE FROM runs WHERE projectId = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
    return len(run_ids)


# ---------------- Runs ----------------

def insert_run(run: Dict[str, Any]) -> None:
    with _lock:
        _get_conn().execute(
            "INSERT INTO runs (id, projectId, status, trigger, startedAt, completedAt, prUrl, createdAt) "
            "VALUES (:id, :projectId, :status, :trigger, :startedAt, :completedAt, :prUrl, :createdAt)",
            run,
        )
        _get_conn().commit()


def list_runs(project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with _lock:
        if project_id:
            rows = _get_conn().execute(
                "SELECT * FROM runs WHERE projectId = ? ORDER BY createdAt DESC", (project_id,)
            ).fetchall()
        else:
            rows = _get_conn().execute("SELECT * FROM runs ORDER BY createdAt DESC").fetchall()
    return _to_dicts(rows)


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        row = _get_conn().execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def update_run(run_id: str, fields: Dict[str, Any]) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    fields = {**fields, "id": run_id}
    with _lock:
        _get_conn().execute(f"UPDATE runs SET {sets} WHERE id = :id", fields)
        _get_conn().commit()


def delete_run(run_id: str) -> bool:
    with _lock:
        conn = _get_conn()
        cur = conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        conn.execute("DELETE FROM test_cases WHERE testRunId = ?", (run_id,))
        conn.commit()
    return cur.rowcount > 0


# ---------------- Test Cases ----------------

def insert_case(case: Dict[str, Any]) -> None:
    with _lock:
        _get_conn().execute(
            "INSERT OR REPLACE INTO test_cases (id, testRunId, name, status, duration, error, logs, code, screenshotUrl, createdAt) "
            "VALUES (:id, :testRunId, :name, :status, :duration, :error, :logs, :code, :screenshotUrl, :createdAt)",
            case,
        )
        _get_conn().commit()


def list_cases(run_id: str) -> List[Dict[str, Any]]:
    with _lock:
        rows = _get_conn().execute(
            "SELECT * FROM test_cases WHERE testRunId = ?", (run_id,)
        ).fetchall()
    return _to_dicts(rows)


def list_all_cases() -> List[Dict[str, Any]]:
    with _lock:
        rows = _get_conn().execute("SELECT * FROM test_cases").fetchall()
    return _to_dicts(rows)
