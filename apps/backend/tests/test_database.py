"""Tests for the SQLite repository abstraction (`app.repositories.database`).

The ``Database`` class is a singleton, so each test resets the cached instance
and points it at a temporary database file. This exercises real SQLite behavior
(CRUD, cascade delete) and verifies migrations are idempotent.
"""
import pytest

from app.repositories.database import Database


@pytest.fixture
def db(tmp_path):
    Database.reset_instance()
    instance = Database(db_path=str(tmp_path / "test.db"))
    yield instance
    Database.reset_instance()


def _project(project_id="p1"):
    return {
        "id": project_id,
        "name": "Demo",
        "repoUrl": "https://github.com/example/repo",
        "websiteUrl": "https://example.com",
        "testEmail": "qa@example.com",
        "status": "active",
        "createdAt": "2024-01-01T00:00:00Z",
    }


def _run(run_id="r1", project_id="p1"):
    return {
        "id": run_id,
        "projectId": project_id,
        "status": "analyzing",
        "trigger": "manual",
        "startedAt": "2024-01-01T00:00:00Z",
        "completedAt": None,
        "prUrl": None,
        "createdAt": "2024-01-01T00:00:00Z",
    }


def _case(case_id="c1", run_id="r1"):
    return {
        "id": case_id,
        "testRunId": run_id,
        "name": "logs in",
        "status": "passed",
        "duration": 120.5,
        "error": None,
        "logs": "ok",
        "code": "def test_x(): pass",
        "screenshotUrl": None,
        "createdAt": "2024-01-01T00:00:00Z",
    }


# ---------------- projects ----------------


def test_project_crud(db):
    assert db.list_projects() == []

    db.insert_project(_project("p1"))
    db.insert_project(_project("p2"))

    fetched = db.get_project("p1")
    assert fetched is not None
    assert fetched["name"] == "Demo"
    assert fetched["websiteUrl"] == "https://example.com"

    assert len(db.list_projects()) == 2

    db.update_project("p1", {"name": "Renamed", "status": "archived"})
    updated = db.get_project("p1")
    assert updated["name"] == "Renamed"
    assert updated["status"] == "archived"

    assert db.get_project("missing") is None


def test_update_project_with_no_fields_is_noop(db):
    db.insert_project(_project("p1"))
    db.update_project("p1", {})
    assert db.get_project("p1")["name"] == "Demo"


# ---------------- runs ----------------


def test_run_crud_and_summary_columns(db):
    db.insert_project(_project("p1"))
    db.insert_run(_run("r1", "p1"))
    db.insert_run(_run("r2", "p1"))

    run = db.get_run("r1")
    assert run is not None
    assert run["projectId"] == "p1"
    # Migration columns should exist and default to NULL.
    assert "plannedTotal" in run
    assert "timeline" in run

    assert len(db.list_runs()) == 2
    assert len(db.list_runs(project_id="p1")) == 2

    db.update_run("r1", {"status": "completed", "plannedTotal": 5, "timeline": "[]"})
    updated = db.get_run("r1")
    assert updated["status"] == "completed"
    assert updated["plannedTotal"] == 5

    assert db.delete_run("r1") is True
    assert db.get_run("r1") is None
    assert db.delete_run("does-not-exist") is False


# ---------------- test cases ----------------


def test_case_crud(db):
    db.insert_project(_project("p1"))
    db.insert_run(_run("r1", "p1"))
    db.insert_case(_case("c1", "r1"))
    db.insert_case(_case("c2", "r1"))

    cases = db.list_cases("r1")
    assert len(cases) == 2
    assert {c["id"] for c in cases} == {"c1", "c2"}
    assert len(db.list_all_cases()) == 2


def test_insert_case_replaces_on_conflict(db):
    db.insert_project(_project("p1"))
    db.insert_run(_run("r1", "p1"))
    db.insert_case(_case("c1", "r1"))
    db.insert_case({**_case("c1", "r1"), "status": "failed"})

    cases = db.list_cases("r1")
    assert len(cases) == 1
    assert cases[0]["status"] == "failed"


def test_case_provenance_columns_roundtrip(db):
    db.insert_project(_project("p1"))
    db.insert_run(_run("r1", "p1"))
    db.insert_case({
        **_case("c1", "r1"),
        "status": "passed",
        "failedFirstPass": 1,
        "rootCause": "selector_wrong",
        "repairAttempts": 2,
        "firstPassError": "waiting for locator('#x')",
        "analysisNote": "The selector did not match the DOM.",
        "liveStatus": "verified",
    })

    case = db.list_cases("r1")[0]
    assert case["failedFirstPass"] == 1
    assert case["rootCause"] == "selector_wrong"
    assert case["repairAttempts"] == 2
    assert case["firstPassError"] == "waiting for locator('#x')"
    assert case["analysisNote"] == "The selector did not match the DOM."
    assert case["liveStatus"] == "verified"


def test_case_provenance_defaults_when_omitted(db):
    db.insert_project(_project("p1"))
    db.insert_run(_run("r1", "p1"))
    # A minimal dict without the provenance keys must not raise.
    db.insert_case(_case("c1", "r1"))

    case = db.list_cases("r1")[0]
    assert case["failedFirstPass"] == 0
    assert case["repairAttempts"] == 0
    assert case["rootCause"] is None
    assert case["analysisNote"] is None


def test_cases_table_migration_adds_provenance_columns(tmp_path):
    import sqlite3

    path = str(tmp_path / "legacy.db")
    # Simulate a pre-provenance database by creating a minimal test_cases table.
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE test_cases (id TEXT PRIMARY KEY, testRunId TEXT, name TEXT, status TEXT)"
    )
    conn.commit()
    conn.close()

    Database.reset_instance()
    instance = Database(db_path=path)
    conn = instance._get_conn()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(test_cases)").fetchall()}
    assert {
        "failedFirstPass", "rootCause", "repairAttempts",
        "firstPassError", "analysisNote", "liveStatus",
    } <= cols
    Database.reset_instance()


# ---------------- cascade delete ----------------


def test_cascade_delete_project_removes_runs_and_cases(db):
    db.insert_project(_project("p1"))
    db.insert_project(_project("p2"))
    db.insert_run(_run("r1", "p1"))
    db.insert_run(_run("r2", "p1"))
    db.insert_run(_run("r3", "p2"))
    db.insert_case(_case("c1", "r1"))
    db.insert_case(_case("c2", "r2"))
    db.insert_case(_case("c3", "r3"))

    removed_runs = db.cascade_delete_project("p1")
    assert removed_runs == 2

    assert db.get_project("p1") is None
    assert db.list_runs(project_id="p1") == []
    # Only p2's data survives.
    assert len(db.list_runs()) == 1
    assert {c["id"] for c in db.list_all_cases()} == {"c3"}


# ---------------- migrations ----------------


def test_migration_is_idempotent_across_reopen(tmp_path):
    path = str(tmp_path / "migrate.db")

    Database.reset_instance()
    first = Database(db_path=path)
    first.insert_project(_project("p1"))
    conn = first._get_conn()
    columns_before = {row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}

    # Re-opening the same file must not fail and must not duplicate columns.
    Database.reset_instance()
    second = Database(db_path=path)
    conn2 = second._get_conn()
    columns_after = {row[1] for row in conn2.execute("PRAGMA table_info(runs)").fetchall()}

    assert columns_before == columns_after
    assert {"plannedTotal", "timeline", "retryCount"} <= columns_after

    # Calling the migration again on an up-to-date schema is a safe no-op.
    second._migrate_runs_table(conn2)

    # Existing rows survive the reopen.
    assert second.get_project("p1") is not None

    Database.reset_instance()


def test_get_database_returns_singleton(tmp_path):
    from app.repositories.database import get_database

    Database.reset_instance()
    a = get_database()
    b = get_database()
    assert a is b
    Database.reset_instance()
