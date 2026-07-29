import uuid
import httpx
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.config import settings

logger = logging.getLogger("auth-router")
router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.get("/github")
async def github_login():
    client_id = settings.github_client_id
    redirect_uri = f"{settings.backend_url}/api/auth/github/callback"
    
    if not client_id:
        # If GitHub Client ID is not configured, redirect directly to dashboard as dev user
        dev_token = "dev-mock-jwt-token"
        return RedirectResponse(url=f"{settings.frontend_url}/auth/callback?token={dev_token}")

    github_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=repo%20user:email%20read:org"
        f"&state={uuid.uuid4()}"
    )
    return RedirectResponse(url=github_url)

@router.get("/github/callback")
async def github_callback(code: str = None):
    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code")

    client_id = settings.github_client_id
    client_secret = settings.github_client_secret

    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
            },
        )
        token_data = token_res.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise HTTPException(status_code=400, detail=token_data.get("error", "Failed to exchange OAuth code"))

        # Create JWT token and redirect back to frontend
        mock_token = f"jwt-github-{uuid.uuid4()}"
        return RedirectResponse(url=f"{settings.frontend_url}/auth/callback?token={mock_token}")

@router.get("/me")
async def get_current_user():
    return {
        "success": True,
        "data": {
            "id": "usr-1",
            "name": "TestPilot Developer",
            "email": "dev@testpilot.ai",
            "avatarUrl": "https://avatars.githubusercontent.com/u/1000000?v=4"
        }
    }
