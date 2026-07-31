import uuid
import logging
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.graph.pipeline import run_pipeline

logger = logging.getLogger("test-runs-router")
router = APIRouter(prefix="/api/test-runs", tags=["test-runs"])

runs_db: List[Dict[str, Any]] = [
    {
        "id": "run-101",
        "projectId": "proj-demo-1",
        "status": "completed",
        "trigger": "manual",
        "startedAt": "2026-07-29T20:00:00Z",
        "completedAt": "2026-07-29T20:02:15Z",
        "createdAt": "2026-07-29T20:00:00Z"
    }
]

test_cases_db: List[Dict[str, Any]] = [
    {
        "id": "tc-1",
        "testRunId": "run-101",
        "name": "Navigation & Dashboard Verification",
        "status": "passed",
        "duration": 1250,
        "error": None,
        "logs": "Navigated to http://localhost:3000\nAssertion passed: title contains TestPilot AI",
        "screenshotUrl": None,
        "createdAt": "2026-07-29T20:00:15Z"
    },
    {
        "id": "tc-2",
        "testRunId": "run-101",
        "name": "Form Submission & Validation Test",
        "status": "passed",
        "duration": 2100,
        "error": None,
        "logs": "Filled email input\nClicked submit button\nAssertion passed",
        "screenshotUrl": None,
        "createdAt": "2026-07-29T20:01:00Z"
    }
]


def _update_run_status(run_id: str, status: str):
    """Updates the run entry status in runs_db so the frontend can poll intermediate states."""
    run_entry = next((r for r in runs_db if r["id"] == run_id), None)
    if run_entry:
        run_entry["status"] = status


async def _execute_pipeline_and_update(project_id: str, run_id: str, website_url: str, repo_url: str):
    """Wraps run_pipeline with a status callback to update runs_db in real-time."""
    run_entry = next((r for r in runs_db if r["id"] == run_id), None)

    try:
        final_state = await run_pipeline(
            project_id, run_id, website_url, repo_url,
            on_status_change=lambda status: _update_run_status(run_id, status)
        )

        # Extract generated Playwright suite code
        generated_code = ""
        generated_files = final_state.get("generated_tests") or []
        if generated_files:
            generated_code = generated_files[0].get("code", "")

        # Write execution results as test cases
        for i, result in enumerate(final_state.get("execution_results") or []):
            test_cases_db.append({
                "id": f"tc-{run_id[:8]}-{i}",
                "testRunId": run_id,
                "name": result.get("test_name", f"Test Case {i+1}"),
                "status": result.get("status", "passed"),
                "duration": result.get("duration_ms", 0),
                "error": result.get("error"),
                "logs": result.get("logs", ""),
                "code": generated_code,
                "screenshotUrl": None,
                "createdAt": datetime.now(timezone.utc).isoformat()
            })


        # Final status update
        if run_entry:
            run_entry["status"] = final_state.get("status", "completed")
            run_entry["completedAt"] = datetime.now(timezone.utc).isoformat()
            run_entry["prUrl"] = final_state.get("pr_url")

        logger.info(f"Pipeline completed for run {run_id}: status={final_state.get('status')}")

    except Exception as e:
        logger.error(f"Pipeline failed for run {run_id}: {e}")
        if run_entry:
            run_entry["status"] = "failed"
            run_entry["completedAt"] = datetime.now(timezone.utc).isoformat()


@router.get("/{project_id}")
async def get_project_runs(project_id: str):
    project_runs = [r for r in runs_db if r["projectId"] == project_id]
    if not project_runs:
        project_runs = runs_db
    return {"success": True, "data": project_runs}

@router.get("/run/{run_id}")
async def get_run_details(run_id: str):
    run = next((r for r in runs_db if r["id"] == run_id), None)
    if not run:
        run = {
            "id": run_id,
            "projectId": "proj-demo-1",
            "status": "completed",
            "trigger": "manual",
            "startedAt": "2026-07-29T20:00:00Z",
            "completedAt": "2026-07-29T20:02:15Z",
            "createdAt": "2026-07-29T20:00:00Z"
        }
    cases = [c for c in test_cases_db if c["testRunId"] == run_id]
    if not cases:
        cases = test_cases_db

    return {"success": True, "data": {"run": run, "testCases": cases}}

@router.post("/{project_id}/start")
async def start_run(project_id: str, data: dict = None):
    from app.api.projects import projects_db
    project = next((p for p in projects_db if p["id"] == project_id), None)

    default_website = project["websiteUrl"] if project else "http://localhost:3000"
    default_repo = project["repoUrl"] if project else "https://github.com/suriyaprakash500/Testpilot-AI"

    run_id = str(uuid.uuid4())
    website_url = (data or {}).get("websiteUrl") or default_website
    repo_url = (data or {}).get("repoUrl") or default_repo

    new_run = {
        "id": run_id,
        "projectId": project_id,
        "status": "analyzing",
        "trigger": "manual",
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "completedAt": None,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    runs_db.insert(0, new_run)

    asyncio.create_task(_execute_pipeline_and_update(project_id, run_id, website_url, repo_url))
    return {"success": True, "data": {"runId": run_id, "status": "analyzing"}}


@router.delete("/run/{run_id}")
async def delete_run(run_id: str):
    global runs_db
    runs_db = [r for r in runs_db if r["id"] != run_id]
    return {"success": True, "data": {"deleted": True}}
