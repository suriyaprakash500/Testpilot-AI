# TestPilot AI

> Autonomous, AI-native QA engineering platform powered by a **Python FastAPI + Pydantic v2 Agentic Backend** and a **React / Next.js 16 Dark-Mode IDE Dashboard**.

---

## Clean Monorepo Architecture

```
testpilot-ai/
├── apps/
│   ├── backend/              # Python 3.12 FastAPI + Pydantic v2 Backend
│   │   ├── app/
│   │   │   ├── main.py       # FastAPI REST & WebSocket Server
│   │   │   ├── config.py     # Environment settings (pydantic-settings)
│   │   │   ├── models.py     # Pydantic v2 Domain Models & Contracts
│   │   │   ├── core/         # Architecture (EventBus, Telemetry, ArtifactStore, MemoryStore, Planner, RetryPolicy)
│   │   │   ├── auth/         # Decoupled Auth Subsystem (AuthManager, CredentialStore, SessionCache, Fail-Fast)
│   │   │   ├── agents/       # Single ReAct Engine & Capability AgentRegistry
│   │   │   └── tools/        # Decoupled Tool Metadata Registry & Playwright Async Executor
│   │   └── requirements.txt
│   └── frontend/             # Next.js 16 + Tailwind CSS Dark Obsidian Dashboard
├── docs/
│   ├── architecture.md       # Full System Architecture
│   └── interview.md          # Enterprise System Design & Interview Preparation Guide
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── render.yaml
└── README.md
```

---

## Enterprise Agentic Pipeline

```
              React / Next.js 16 Frontend
                           │
                           ▼ (REST / WebSockets)
                 Event-Driven Supervisor
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
         EventBus       Planner     AgentRegistry
             │
     ┌───────┴───────┐
     ▼               ▼
ReActExecutor   Groq LLM Engine
     │
     ▼
Tool Executor ──► Playwright Async Engine / Git
     │
     ▼
Shared RunState ──► MemoryStore / ArtifactStore / Telemetry
```

---

## Core System Highlights

* **Python FastAPI + Pydantic v2 Backend**: High-performance asynchronous API server with strict Pydantic data validation and native WebSockets.
* **Playwright Python Async Integration**: Runs test suites using `playwright.async_api` for non-blocking browser execution.
* **Single Reusable ReAct Engine**: Eliminates ReAct loop duplication. A single engine executes agent configurations with Pydantic schemas.
* **Decoupled Enterprise Authentication**: `AuthManager` handles login detection (heuristic-first), credential loading, session caching, and **Fail-Fast Post-Auth Verification** to prevent 50 duplicate failed screenshots on bad credentials.
* **Capability-Based AgentRegistry**: Dynamically routes domain events (`SUITE_EXECUTION_FAILED`, `REPO_ANALYZED`) without if-else ladders.
* **Decoupled Tool Registry & Executor**: Separates tool metadata (`ToolRegistry`) from physical service invocation (`ToolExecutor`).
* **Dedicated Observability & Storage**: Dedicated `ArtifactStore` for binary traces, `MemoryStore` for failure snapshots, and `TelemetryStore` for latency/token APM logging.

---

## Quick Start

### 1. Python Backend Setup

```bash
cd apps/backend

# Create & activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright Chromium browser
playwright install chromium

# Start FastAPI dev server on port 3001
uvicorn app.main:app --reload --port 3001
```

### 2. Frontend Setup

```bash
cd apps/frontend

# Install & start Next.js dev server on port 3000
pnpm install
pnpm dev
```
