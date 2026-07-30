import uuid
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
import asyncio
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
        "screenshotUrl": "/api/artifacts/dashboard-preview.png",
        "createdAt": "2026-07-29T20:00:15Z"
    },
    {
        "id": "tc-2",
        "testRunId": "run-101",
        "name": "Self-Healing Selector Test",
        "status": "passed",
        "duration": 2100,
        "error": None,
        "logs": "Locator drift detected on button#submit\nAI Auto-Healer applied role selector: [data-testid='submit-btn']\nAssertion passed",
        "screenshotUrl": "/api/artifacts/healed-locator.png",
        "createdAt": "2026-07-29T20:01:00Z"
    }
]

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
        "startedAt": "2026-07-29T22:00:00Z",
        "completedAt": None,
        "createdAt": "2026-07-29T22:00:00Z"
    }
    runs_db.insert(0, new_run)

    # Execute LangGraph StateGraph pipeline asynchronously
    asyncio.create_task(run_pipeline(project_id, run_id, website_url, repo_url))
    return {"success": True, "data": {"runId": run_id, "status": "analyzing"}}



@router.delete("/run/{run_id}")
async def delete_run(run_id: str):
    global runs_db
    runs_db = [r for r in runs_db if r["id"] != run_id]
    return {"success": True, "data": {"deleted": True}}
