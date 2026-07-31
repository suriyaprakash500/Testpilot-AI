from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

# --- System Enums & Types ---

AgentType = Literal[
    "repo-analysis",
    "test-planning",
    "playwright-gen",
    "browser-execution",
    "github-integration"
]

TestRunStatus = Literal[
    "pending",
    "analyzing",
    "planning",
    "generating",
    "executing",
    "reporting",
    "completed",
    "failed",
    "cancelled"
]

# --- Domain Models ---

class Project(BaseModel):
    id: str
    user_id: str
    name: str
    repo_url: str
    website_url: str
    test_email: Optional[str] = None
    test_password: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TestRun(BaseModel):
    id: str
    project_id: str
    status: TestRunStatus = "pending"
    trigger: str = "manual"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TestCase(BaseModel):
    id: str
    test_run_id: str
    name: str
    code: str
    status: str = "pending"
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    trace_path: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AuthSession(BaseModel):
    id: str
    project_id: str
    strategy: str = "form"
    storage_state_path: Optional[str] = None
    cookies: Optional[List[Dict[str, Any]]] = None
    headers: Optional[Dict[str, str]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
