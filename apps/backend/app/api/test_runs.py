import uuid
import logging
import asyncio
from typing import Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.graph.pipeline import run_pipeline
from app import db

logger = logging.getLogger("test-runs-router")
router = APIRouter(prefix="/api/test-runs", tags=["test-runs"])

# Registry of in-flight pipeline tasks so runs can be cancelled.
RUN_TASKS: Dict[str, asyncio.Task] = {}

TERMINAL_STATUSES = {"completed", "failed", "cancelled", "completed_with_failures"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _execute_pipeline_and_update(project_id: str, run_id: str, website_url: str, repo_url: str):
    """Wraps run_pipeline, persisting real-time status updates to the DB."""
    try:
        final_state = await run_pipeline(
            project_id, run_id, website_url, repo_url,
            on_status_change=lambda status: db.update_run(run_id, {"status": status})
        )

        # Extract generated Playwright suite code
        generated_code = ""
        generated_files = final_state.get("generated_tests") or []
        if generated_files:
            generated_code = generated_files[0].get("code", "")

        # Write execution results as test cases
        for i, result in enumerate(final_state.get("execution_results") or []):
            db.insert_case({
                "id": f"tc-{run_id[:8]}-{i}",
                "testRunId": run_id,
                "name": result.get("test_name", f"Test Case {i+1}"),
                "status": result.get("status", "passed"),
                "duration": result.get("duration_ms", 0),
                "error": result.get("error"),
                "logs": result.get("logs", ""),
                "code": generated_code,
                "screenshotUrl": None,
                "createdAt": _now_iso(),
            })

        db.update_run(run_id, {
            "status": final_state.get("status", "completed"),
            "completedAt": _now_iso(),
            "prUrl": final_state.get("pr_url"),
        })
        logger.info(f"Pipeline completed for run {run_id}: status={final_state.get('status')}")

    except asyncio.CancelledError:
        logger.info(f"Run {run_id} cancelled by user")
        db.update_run(run_id, {"status": "cancelled", "completedAt": _now_iso()})
    except Exception as e:
        logger.error(f"Pipeline failed for run {run_id}: {e}")
        db.update_run(run_id, {"status": "failed", "completedAt": _now_iso()})


@router.get("/{project_id}")
async def get_project_runs(project_id: str):
    return {"success": True, "data": db.list_runs(project_id)}


@router.get("/run/{run_id}")
async def get_run_details(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"success": True, "data": {"run": run, "testCases": db.list_cases(run_id)}}


@router.post("/{project_id}/start")
async def start_run(project_id: str, data: dict = None):
    project = db.get_project(project_id)

    default_website = project["websiteUrl"] if project else "http://localhost:3000"
    default_repo = project["repoUrl"] if project else "https://github.com/suriyaprakash500/Testpilot-AI"

    run_id = str(uuid.uuid4())
    website_url = (data or {}).get("websiteUrl") or default_website
    repo_url = (data or {}).get("repoUrl") or default_repo

    db.insert_run({
        "id": run_id,
        "projectId": project_id,
        "status": "analyzing",
        "trigger": "manual",
        "startedAt": _now_iso(),
        "completedAt": None,
        "prUrl": None,
        "createdAt": _now_iso(),
    })

    task = asyncio.create_task(_execute_pipeline_and_update(project_id, run_id, website_url, repo_url))
    RUN_TASKS[run_id] = task
    task.add_done_callback(lambda _t, rid=run_id: RUN_TASKS.pop(rid, None))

    return {"success": True, "data": {"runId": run_id, "status": "analyzing"}}


@router.post("/run/{run_id}/cancel")
async def cancel_run(run_id: str):
    """Cancels an in-flight pipeline run. Stale runs (no live task) are marked cancelled directly."""
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run["status"] in TERMINAL_STATUSES:
        return {"success": True, "data": {"status": run["status"], "message": "Run already finished"}}

    task = RUN_TASKS.get(run_id)
    if task and not task.done():
        task.cancel()
        db.update_run(run_id, {"status": "cancelling"})
        return {"success": True, "data": {"status": "cancelling"}}

    db.update_run(run_id, {"status": "cancelled", "completedAt": _now_iso()})
    return {"success": True, "data": {"status": "cancelled"}}


@router.delete("/run/{run_id}")
async def delete_run(run_id: str):
    if not db.delete_run(run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    return {"success": True, "data": {"deleted": True}}
