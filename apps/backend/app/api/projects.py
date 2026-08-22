import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from app.auth.credential_store import credential_store
from app.db import (
    list_projects as db_list_projects,
    get_project as db_get_project,
    insert_project,
    update_project,
    cascade_delete_project,
    list_runs,
    list_cases,
    list_all_cases,
)

logger = logging.getLogger("projects-router")
router = APIRouter(prefix="/api/projects", tags=["projects"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("")
@router.get("/")
async def list_projects():
    return {"success": True, "data": db_list_projects()}

@router.post("")
@router.post("/")
async def create_project(data: dict):
    repo_url = data.get("repoUrl", "")
    website_url = data.get("websiteUrl", "")
    test_email = data.get("testEmail")
    test_password = data.get("testPassword")
    name = data.get("name") or repo_url.split("/")[-1].replace(".git", "") or "New Project"
    project_id = str(uuid.uuid4())

    new_project = {
        "id": project_id,
        "name": name,
        "repoUrl": repo_url,
        "websiteUrl": website_url,
        "testEmail": test_email,
        "status": "active",
        "createdAt": _now_iso(),
    }
    insert_project(new_project)

    if test_email and test_password:
        await credential_store.set_credential(project_id, test_email, test_password)

    logger.info(f"Created project {project_id} ({name})")
    return {"success": True, "data": new_project}

@router.get("/analytics")
async def get_analytics():
    """Computes workspace analytics from persisted runs and test cases."""
    runs = list_runs()
    cases = list_all_cases()
    projects = db_list_projects()

    total_cases = len(cases)
    passed_cases = sum(1 for c in cases if c.get("status") == "passed")
    average_pass_rate = round((passed_cases / total_cases) * 100, 1) if total_cases else 0.0
    failed_run_alerts = sum(
        1 for r in runs if r.get("status") in ("failed", "completed_with_failures")
    )

    # Per-project stats derived from real runs/cases
    projects_stats = []
    for p in projects:
        project_run_ids = {r["id"] for r in runs if r.get("projectId") == p["id"]}
        p_cases = [c for c in cases if c.get("testRunId") in project_run_ids]
        p_passed = sum(1 for c in p_cases if c.get("status") == "passed")
        p_rate = round((p_passed / len(p_cases)) * 100, 1) if p_cases else 0.0
        projects_stats.append({
            "id": p["id"],
            "name": p["name"],
            "websiteUrl": p["websiteUrl"],
            "totalRuns": len(project_run_ids),
            "passRate": p_rate,
            "status": p["status"]
        })

    # Recent runs (latest 5) mapped to their project names
    project_name_by_id = {p["id"]: p["name"] for p in projects}
    recent_runs = []
    for r in sorted(runs, key=lambda x: x.get("createdAt") or "", reverse=True)[:5]:
        run_cases = [c for c in cases if c.get("testRunId") == r["id"]]
        recent_runs.append({
            "id": r["id"],
            "projectName": project_name_by_id.get(r.get("projectId"), "Unknown"),
            "status": r.get("status", "unknown"),
            "passedCases": sum(1 for c in run_cases if c.get("status") == "passed"),
            "failedCases": sum(1 for c in run_cases if c.get("status") == "failed"),
            "createdAt": r.get("createdAt")
        })

    return {
        "success": True,
        "data": {
            "averagePassRate": average_pass_rate,
            "totalTimeSavedMs": sum(int(c.get("duration") or 0) for c in cases),
            "failedRunAlerts": failed_run_alerts,
            "totalRuns": len(runs),
            "totalCases": total_cases,
            "projects": projects_stats,
            "recentRuns": recent_runs
        }
    }

@router.get("/active-agents")
async def get_active_agents():
    return {
        "success": True,
        "data": {
            "repoAnalysis": False,
            "testPlanning": False,
            "playwrightGen": False,
            "browserExecution": False,
            "failureAnalysis": False,
            "githubIntegration": False
        }
    }

@router.get("/pipelines")
async def get_pipelines():
    """Summarizes the latest real pipeline runs by trigger type."""
    def _summarize(run: Dict[str, Any] | None) -> Dict[str, Any] | None:
        if not run:
            return None
        run_cases = list_cases(run["id"])
        return {
            "id": run["id"],
            "status": run.get("status", "unknown"),
            "createdAt": run.get("createdAt"),
            "completedAt": run.get("completedAt"),
            "casesCount": len(run_cases),
            "passedCount": sum(1 for c in run_cases if c.get("status") == "passed"),
            "failedCount": sum(1 for c in run_cases if c.get("status") == "failed")
        }

    triggered_runs = [r for r in list_runs() if r.get("trigger") == "manual"]
    latest = max(triggered_runs, key=lambda x: x.get("createdAt") or "", default=None)

    return {
        "success": True,
        "data": {
            "manual": _summarize(latest),
            "webhook": None,
            "schedule": None
        }
    }

@router.get("/active-session")
async def get_active_session():
    return {"success": True, "data": None}

@router.get("/repositories")
async def get_repositories():
    return {
        "success": True,
        "data": [
            {
                "projectId": p["id"],
                "repoUrl": p["repoUrl"],
                "repoName": p["repoUrl"].split("/")[-1],
                "projectName": p["name"],
                "framework": "nextjs",
                "language": "typescript",
                "analyzedAt": None
            }
            for p in db_list_projects()
        ]
    }

# NOTE: specific routes (/analytics, /pipelines, ...) MUST stay declared above /{project_id}

@router.get("/{project_id}")
async def get_project(project_id: str):
    project = db_get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"success": True, "data": project}

@router.patch("/{project_id}")
async def update_project(project_id: str, data: dict):
    project = db_get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    test_email = data.get("testEmail")
    test_password = data.get("testPassword")

    fields: Dict[str, Any] = {}
    for key in ("name", "repoUrl", "websiteUrl", "status"):
        if data.get(key):
            fields[key] = data[key]
    if test_email:
        fields["testEmail"] = test_email

    if fields:
        update_project(project_id, fields)

    if test_email or test_password:
        current_creds = await credential_store.get_credential(project_id) or {}
        email_to_save = test_email or current_creds.get("username", "")
        pass_to_save = test_password or current_creds.get("password", "")
        await credential_store.set_credential(project_id, email_to_save, pass_to_save)
        logger.info(f"Updated test credentials for project {project_id}")

    updated = db_get_project(project_id)
    return {"success": True, "data": updated}

@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Deletes a project along with all of its test runs and test cases (cascade)."""
    if not db_get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    deleted_runs = cascade_delete_project(project_id)
    logger.info(f"Deleted project {project_id} and {deleted_runs} associated run(s)")
    return {"success": True, "data": {"deleted": True}}
