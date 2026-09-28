"""SQLite-backed persistence repository.

This module owns the SQLite connection, locking, schema initialization,
idempotent migrations and the CRUD operations for projects, runs and test
cases. The rest of the application depends on this abstraction instead of a
module-level ``sqlite3`` handle, which keeps the storage engine swappable
(e.g. PostgreSQL later) without touching call sites.

``app/db.py`` remains as a backward-compatible shim that delegates here.
"""
import logging
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.singleton import Singleton

logger = logging.getLogger("database")

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
    liveVerifiedCount INTEGER,
    liveCorrectedCount INTEGER,
    liveUnverifiedCount INTEGER,
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
    createdAt TEXT,
    -- Per-case failure/repair provenance (populated by the feedback loop)
    failedFirstPass INTEGER DEFAULT 0,
    rootCause TEXT,
    repairAttempts INTEGER DEFAULT 0,
    firstPassError TEXT,
    analysisNote TEXT,
    liveStatus TEXT
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
    ("liveVerifiedCount", "INTEGER"),
    ("liveCorrectedCount", "INTEGER"),
    ("liveUnverifiedCount", "INTEGER"),
    ("timeline", "TEXT"),
]

# Per-case provenance columns added alongside the run summary. These let the UI
# show WHICH cases failed on the first pass and WHY (root cause + analysis note)
# instead of only storing the final, post-repair status.
_CASE_MIGRATION_COLUMNS = [
    ("failedFirstPass", "INTEGER DEFAULT 0"),
    ("rootCause", "TEXT"),
    ("repairAttempts", "INTEGER DEFAULT 0"),
    ("firstPassError", "TEXT"),
    ("analysisNote", "TEXT"),
    ("liveStatus", "TEXT"),
]


class Database(Singleton):
    """Owns the SQLite connection and all persistence operations."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        # Reached only on first construction (Singleton caches the instance).
        self.db_path = db_path or settings.database_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None

    # ---------------- Connection / schema ----------------

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(_SCHEMA)
            self._migrate_runs_table(self._conn)
            self._migrate_cases_table(self._conn)
            self._conn.commit()
            logger.info("Initialized SQLite database at %s", self.db_path)
        return self._conn

    def _migrate_runs_table(self, conn: sqlite3.Connection) -> None:
        """Adds any missing run-summary columns to an existing runs table."""
        existing = {row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
        for name, coltype in _RUN_MIGRATION_COLUMNS:
            if name not in existing:
                conn.execute(f"ALTER TABLE runs ADD COLUMN {name} {coltype}")

    def _migrate_cases_table(self, conn: sqlite3.Connection) -> None:
        """Adds missing per-case provenance columns to an existing test_cases table."""
        existing = {row[1] for row in conn.execute("PRAGMA table_info(test_cases)").fetchall()}
        for name, coltype in _CASE_MIGRATION_COLUMNS:
            if name not in existing:
                conn.execute(f"ALTER TABLE test_cases ADD COLUMN {name} {coltype}")

    @staticmethod
    def _to_dicts(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
        return [dict(r) for r in rows]

    # ---------------- Projects ----------------

    def insert_project(self, project: Dict[str, Any]) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO projects (id, name, repoUrl, websiteUrl, testEmail, status, createdAt) "
                "VALUES (:id, :name, :repoUrl, :websiteUrl, :testEmail, :status, :createdAt)",
                project,
            )
            conn.commit()

    def list_projects(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM projects ORDER BY createdAt DESC"
            ).fetchall()
        return self._to_dicts(rows)

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_project(self, project_id: str, fields: Dict[str, Any]) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        params = {**fields, "id": project_id}
        with self._lock:
            conn = self._get_conn()
            conn.execute(f"UPDATE projects SET {sets} WHERE id = :id", params)
            conn.commit()

    def cascade_delete_project(self, project_id: str) -> int:
        """Deletes a project plus every run and test case belonging to it.

        Returns the number of runs removed.
        """
        with self._lock:
            conn = self._get_conn()
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

    def insert_run(self, run: Dict[str, Any]) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO runs (id, projectId, status, trigger, startedAt, completedAt, prUrl, createdAt) "
                "VALUES (:id, :projectId, :status, :trigger, :startedAt, :completedAt, :prUrl, :createdAt)",
                run,
            )
            conn.commit()

    def list_runs(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if project_id:
                rows = self._get_conn().execute(
                    "SELECT * FROM runs WHERE projectId = ? ORDER BY createdAt DESC",
                    (project_id,),
                ).fetchall()
            else:
                rows = self._get_conn().execute(
                    "SELECT * FROM runs ORDER BY createdAt DESC"
                ).fetchall()
        return self._to_dicts(rows)

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_run(self, run_id: str, fields: Dict[str, Any]) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        params = {**fields, "id": run_id}
        with self._lock:
            conn = self._get_conn()
            conn.execute(f"UPDATE runs SET {sets} WHERE id = :id", params)
            conn.commit()

    def delete_run(self, run_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            conn.execute("DELETE FROM test_cases WHERE testRunId = ?", (run_id,))
            conn.commit()
        return cur.rowcount > 0

    # ---------------- Test Cases ----------------

    # Full column set for test_cases. Missing keys are defaulted so callers can
    # pass a minimal dict without tripping over named-parameter binding.
    _CASE_COLUMNS = (
        "id", "testRunId", "name", "status", "duration", "error", "logs",
        "code", "screenshotUrl", "createdAt",
        "failedFirstPass", "rootCause", "repairAttempts", "firstPassError",
        "analysisNote", "liveStatus",
    )
    _CASE_DEFAULTS: Dict[str, Any] = {"duration": 0.0, "failedFirstPass": 0, "repairAttempts": 0}

    def insert_case(self, case: Dict[str, Any]) -> None:
        record = {col: case.get(col, self._CASE_DEFAULTS.get(col)) for col in self._CASE_COLUMNS}
        cols = ", ".join(self._CASE_COLUMNS)
        placeholders = ", ".join(f":{c}" for c in self._CASE_COLUMNS)
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                f"INSERT OR REPLACE INTO test_cases ({cols}) VALUES ({placeholders})",
                record,
            )
            conn.commit()

    def list_cases(self, run_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM test_cases WHERE testRunId = ?", (run_id,)
            ).fetchall()
        return self._to_dicts(rows)

    def list_all_cases(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute("SELECT * FROM test_cases").fetchall()
        return self._to_dicts(rows)


def get_database() -> Database:
    """Return the process-wide :class:`Database` singleton."""
    return Database()
