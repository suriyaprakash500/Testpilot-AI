import uuid
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from app.auth.credential_store import credential_store

logger = logging.getLogger("projects-router")
router = APIRouter(prefix="/api/projects", tags=["projects"])

# Mock/in-memory projects store for local dev
projects_db: List[Dict[str, Any]] = [
    {
        "id": "proj-demo-1",
        "name": "Stellaris",
        "repoUrl": "https://github.com/suriyaprakash500/Stellaris",
        "websiteUrl": "http://localhost:3000",
        "testEmail": "testuser@example.com",
        "status": "active",
        "createdAt": "2026-07-29T12:00:00Z"
    }
]

@router.get("")
@router.get("/")
async def list_projects():
    return {"success": True, "data": projects_db}

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
        "createdAt": "2026-07-29T12:00:00Z"
    }
    projects_db.append(new_project)

    if test_email and test_password:
        await credential_store.set_credential(project_id, test_email, test_password)

    return {"success": True, "data": new_project}

@router.get("/analytics")
async def get_analytics():
    return {
        "success": True,
        "data": {
            "averagePassRate": 94.2,
            "totalTimeSavedMs": 138240000,
            "failedRunAlerts": 1,
            "totalRuns": 18,
            "totalCases": 142,
            "projects": [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "websiteUrl": p["websiteUrl"],
                    "totalRuns": 12,
                    "passRate": 96.5,
                    "status": p["status"]
                }
                for p in projects_db
            ],
            "recentRuns": [
                {
                    "id": "run-101",
                    "projectName": "Stellaris",
                    "status": "completed",
                    "passedCases": 8,
                    "failedCases": 0,
                    "createdAt": "2026-07-29T20:00:00Z"
                }
            ]
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
    return {
        "success": True,
        "data": {
            "manual": {
                "id": "run-101",
                "status": "completed",
                "createdAt": "2026-07-29T20:00:00Z",
                "completedAt": "2026-07-29T20:02:15Z",
                "casesCount": 8,
                "passedCount": 8,
                "failedCount": 0
            },
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
                "analyzedAt": "2026-07-29T20:00:00Z"
            }
            for p in projects_db
        ]
    }

@router.get("/{project_id}")
async def get_project(project_id: str):
    project = next((p for p in projects_db if p["id"] == project_id), None)
    if not project:
        # Dynamically create and register project in memory if missing
        project = {
            "id": project_id,
            "name": "Stellaris",
            "repoUrl": "https://github.com/suriyaprakash500/Stellaris",
            "websiteUrl": "http://localhost:3000",
            "testEmail": None,
            "status": "active",
            "createdAt": "2026-07-29T12:00:00Z"
        }
        projects_db.append(project)
    return {"success": True, "data": project}

@router.patch("/{project_id}")
async def update_project(project_id: str, data: dict):
    project = next((p for p in projects_db if p["id"] == project_id), None)
    if not project:
        project = {
            "id": project_id,
            "name": "Stellaris",
            "repoUrl": "https://github.com/suriyaprakash500/Stellaris",
            "websiteUrl": "http://localhost:3000",
            "testEmail": None,
            "status": "active",
            "createdAt": "2026-07-29T12:00:00Z"
        }
        projects_db.append(project)

    test_email = data.get("testEmail")
    test_password = data.get("testPassword")

    if test_email:
        project["testEmail"] = test_email

    if test_email or test_password:
        current_creds = await credential_store.get_credential(project_id) or {}
        email_to_save = test_email or current_creds.get("username", "")
        pass_to_save = test_password or current_creds.get("password", "")
        await credential_store.set_credential(project_id, email_to_save, pass_to_save)
        logger.info(f"Updated test credentials for project {project_id}")

    return {"success": True, "data": project}

@router.delete("/{project_id}")
async def delete_project(project_id: str):
    global projects_db
    projects_db = [p for p in projects_db if p["id"] != project_id]
    return {"success": True, "data": {"deleted": True}}
