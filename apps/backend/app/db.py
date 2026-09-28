"""Backward-compatible shim over the SQLite repository.

The real implementation now lives in :mod:`app.repositories.database`. These
module-level functions delegate to the shared :class:`Database` singleton so
that existing imports (``from app.db import list_projects`` / ``from app import
db``) keep working unchanged.
"""
from typing import Any, Dict, List, Optional

from app.repositories.database import Database, get_database

_DB_PATH = None  # retained for reference; the path is now configuration-driven


def insert_project(project: Dict[str, Any]) -> None:
    get_database().insert_project(project)


def list_projects() -> List[Dict[str, Any]]:
    return get_database().list_projects()


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    return get_database().get_project(project_id)


def update_project(project_id: str, fields: Dict[str, Any]) -> None:
    get_database().update_project(project_id, fields)


def cascade_delete_project(project_id: str) -> int:
    """Deletes a project plus every run and test case belonging to it."""
    return get_database().cascade_delete_project(project_id)


def insert_run(run: Dict[str, Any]) -> None:
    get_database().insert_run(run)


def list_runs(project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return get_database().list_runs(project_id)


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    return get_database().get_run(run_id)


def update_run(run_id: str, fields: Dict[str, Any]) -> None:
    get_database().update_run(run_id, fields)


def delete_run(run_id: str) -> bool:
    return get_database().delete_run(run_id)


def insert_case(case: Dict[str, Any]) -> None:
    get_database().insert_case(case)


def list_cases(run_id: str) -> List[Dict[str, Any]]:
    return get_database().list_cases(run_id)


def list_all_cases() -> List[Dict[str, Any]]:
    return get_database().list_all_cases()


__all__ = [
    "Database",
    "get_database",
    "insert_project",
    "list_projects",
    "get_project",
    "update_project",
    "cascade_delete_project",
    "insert_run",
    "list_runs",
    "get_run",
    "update_run",
    "delete_run",
    "insert_case",
    "list_cases",
    "list_all_cases",
]
