from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

# --- System Enums & Types ---

AgentType = Literal[
    "repo-analysis",
    "test-planning",
    "playwright-gen",
    "browser-execution",
    "failure-analysis",
    "github-integration"
]

TestRunStatus = Literal[
    "pending",
    "analyzing",
    "planning",
    "generating",
    "executing",
    "analyzing_failures",
    "reporting",
    "completed",
    "failed",
    "cancelled"
]

# --- Database & Domain Models ---

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

# --- Enterprise Auth Contracts ---

class AuthSession(BaseModel):
    id: str
    project_id: str
    strategy: str = "form"
    storage_state_path: Optional[str] = None
    cookies: Optional[List[Dict[str, Any]]] = None
    headers: Optional[Dict[str, str]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime

# --- Architecture Contracts ---

class Observation(BaseModel):
    id: str = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    type: str
    source: str
    data: Any

class MemoryItem(BaseModel):
    id: str
    run_id: str
    key: str
    type: Literal["failure", "attempted_fix", "dom_snapshot", "generated_test"]
    content: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class RunState(BaseModel):
    run_id: str
    project_id: str
    status: TestRunStatus = "analyzing"
    active_agent: Optional[AgentType] = None
    completed_steps: List[str] = Field(default_factory=list)
    observations: List[Observation] = Field(default_factory=list)
    artifacts: Dict[str, str] = Field(default_factory=dict)
    iteration: int = 0
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ToolCallRequest(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]

class ToolCallResult(BaseModel):
    tool_call_id: str
    tool_name: str
    output: Any
    error: Optional[str] = None

class AgentDecision(BaseModel):
    reasoning: str
    action: Optional[ToolCallRequest] = None
    confidence: float = 1.0
    completed: bool = False
    output: Optional[Any] = None

class ToolDefinition(BaseModel):
    name: str
    description: str
    handler_key: str
    parameters: Dict[str, Any]

class AgentDefinitionConfig(BaseModel):
    name: str
    type: AgentType
    description: str
    system_prompt: str
    allowed_tools: List[str]
    supported_events: List[str]
    priority: int = 10

class DomainEvent(BaseModel):
    type: str
    run_id: str
    project_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
