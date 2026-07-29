import uuid
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException

logger = logging.getLogger("projects-router")
router = APIRouter(prefix="/api/projects", tags=["projects"])

# Mock/in-memory projects store for local dev
projects_db: List[Dict[str, Any]] = [
    {
        "id": "proj-demo-1",
        "name": "TestPilot AI Demo",
        "repoUrl": "https://github.com/suriyaprakash500/Testpilot-AI",
        "websiteUrl": "http://localhost:3000",
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
    name = data.get("name") or repo_url.split("/")[-1].replace(".git", "")
    project_id = str(uuid.uuid4())
    
    new_project = {
        "id": project_id,
        "name": name,
        "repoUrl": repo_url,
        "websiteUrl": website_url,
        "status": "active",
        "createdAt": "2026-07-29T12:00:00Z"
    }
    projects_db.append(new_project)
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
                    "projectName": "TestPilot AI Demo",
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
        # Fallback for dynamic UUID routes or demo projects
        project = {
            "id": project_id,
            "name": "TestPilot AI Demo",
            "repoUrl": "https://github.com/suriyaprakash500/Testpilot-AI",
            "websiteUrl": "http://localhost:3000",
            "status": "active",
            "createdAt": "2026-07-29T12:00:00Z"
        }
    return {"success": True, "data": project}
