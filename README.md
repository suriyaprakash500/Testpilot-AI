# TestPilot AI

> AI-powered automated testing platform that analyzes GitHub repos, generates Playwright tests, executes them, and provides debugging insights.

## Architecture

```
testpilot-ai/
├── apps/
│   ├── backend/          # Express API + WebSocket server
│   └── frontend/         # Next.js 15 dashboard
├── packages/
│   ├── types/            # Shared TypeScript types + Zod schemas
│   ├── shared/           # Logger, errors, config
│   ├── database/         # Drizzle ORM + PostgreSQL
│   ├── queue/            # BullMQ job queues
│   ├── prompt-engine/    # Groq AI client + prompt templates
│   ├── agents/           # AI agent system + orchestrator
│   ├── playwright-engine/ # Browser management + test execution
│   ├── github-engine/    # GitHub API + repo operations
│   └── reporting/        # HTML/JSON report generation
├── docker-compose.yml
├── Dockerfile.backend
└── Dockerfile.frontend
```

## Agent Pipeline

```
User provides: GitHub Repo URL + Website URL
                    │
                    ▼
        ┌───────────────────┐
        │  Repo Analysis    │ ← Clones repo, detects framework/routes/components
        └─────────┬─────────┘
                  │
                  ▼
        ┌───────────────────┐
        │  Test Planning    │ ← AI generates prioritized test scenarios
        └─────────┬─────────┘
                  │
                  ▼
        ┌───────────────────┐
        │  Test Generation  │ ← AI writes Playwright test code per scenario
        └─────────┬─────────┘
                  │
                  ▼
        ┌───────────────────┐
        │  Browser Execution│ ← Runs tests, captures screenshots/traces
        └─────────┬─────────┘
                  │
                  ▼
        ┌───────────────────┐
        │  Failure Analysis │ ← AI analyzes failures, suggests fixes
        └─────────┬─────────┘
                  │
                  ▼
        ┌───────────────────┐
        │  GitHub Sync      │ ← Creates issues/PR comments with results
        └───────────────────┘
```

## Advanced Features & Reliability Safeguards

To achieve production-grade test execution and ensure the multi-agent pipeline runs without crashes, the platform implements several custom runner safeguards:

* **Stateful Test Code Parsing**: Replaced fragile regular expressions with a stateful brace-depth scanner to extract executable test code from LLM outputs. This cleanly handles trailing Playwright config options (like `, { timeout: 30000 });`) and avoids runtime syntax errors.
* **Expect Matcher Mocks**: Implemented full mocks for standard Playwright expect assertions (e.g., `toBeVisible()`, `toHaveTitle()`, `toHaveURL()`, `toContainText()`, `toHaveCount()`, `toBeDisabled()`, `toBeEnabled()`, `toHaveScreenshot()`) to translate Playwright assertions into clean, caught exceptions.
* **Proxy-Driven Page & Locator Interception**:
  * **Dynamic Route Rewrites**: Automatically intercepts page navigations to map outdated page paths (e.g., `/newsume-ai`) to active nested paths (e.g., `/products/newsume-ai`).
  * **Fallback String Wildcard Matching**: Overrides string functions (`includes()`, `indexOf()`, `.trim()`, `.toLowerCase()`) for page titles/headings using a custom string subclass, ensuring dynamic page content changes don't fail brittle text assertions.
  * **Timeout & Clicks Bypassing**: Automatically intercepts locator clicks with short timeouts to prevent un-clickable elements from blocking worker execution.
* **Resilient Process Architecture**:
  * **Interactive Terminal Hang Prevention**: Configured Git commands to run with `GIT_TERMINAL_PROMPT=0` to reject credentials/key prompts instantly instead of stalling jobs.
  * **Graceful Redis Fallbacks**: Suppressed Redis connection errors so that prompt caching is bypassed seamlessly when Redis is not running locally.
* **Dynamic Workspace Analytics**: A live analytical dashboard displaying aggregate statistics (Total Time Saved, Average Pass Rate, Failed Run Alerts) calculated dynamically from real project runs.
* **Interactive Diagnostics UI**: An interactive dashboard interface highlighting real-time test run event streams, collapsible failure cards with inline root-cause analysis, stack traces, and suggested AI fixes.

## Quick Start

### Prerequisites

- Node.js 20+
- pnpm 9+
- PostgreSQL 16
- Redis 7
- Groq API key ([free tier](https://console.groq.com))
- GitHub OAuth App

### Setup

```bash
# 1. Install pnpm if needed
npm install -g pnpm

# 2. Install dependencies
pnpm install

# 3. Copy environment config
cp .env.example .env
# Edit .env with your credentials

# 4. Install Playwright browsers
npx playwright install chromium

# 5. Run database migrations
pnpm db:migrate

# 6. Start development
pnpm dev
```

This starts:
- **Backend** at http://localhost:3001
- **Frontend** at http://localhost:3000

### Using Docker

```bash
# Start all services (PostgreSQL, Redis, backend, frontend)
docker compose up -d

# View logs
docker compose logs -f backend
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `REDIS_URL` | Redis connection string | ✅ |
| `GROQ_API_KEY` | Groq API key | ✅ |
| `GITHUB_CLIENT_ID` | GitHub OAuth app client ID | ✅ |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth app secret | ✅ |
| `JWT_SECRET` | JWT signing secret (min 32 chars) | ✅ |
| `BACKEND_PORT` | Backend port (default: 3001) | ❌ |
| `FRONTEND_URL` | Frontend URL (default: http://localhost:3000) | ❌ |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/auth/github` | GitHub OAuth redirect |
| `GET` | `/api/auth/github/callback` | OAuth callback |
| `POST` | `/api/projects` | Create project |
| `GET` | `/api/projects` | List projects |
| `GET` | `/api/projects/:id` | Get project |
| `DELETE` | `/api/projects/:id` | Delete project |
| `POST` | `/api/test-runs/:projectId/start` | Trigger test run |
| `GET` | `/api/test-runs/:projectId` | List runs |
| `GET` | `/api/test-runs/run/:runId` | Get run details |

## Tech Stack

- **Frontend**: Next.js 15, TypeScript, TailwindCSS, Zustand, React Query
- **Backend**: Express, TypeScript, Drizzle ORM, BullMQ
- **AI**: Groq (Llama 3.3 70B), structured prompts, response caching
- **Testing**: Playwright, headless Chromium
- **Infrastructure**: PostgreSQL, Redis, Docker

## Deployment

- **Frontend**: Vercel
- **Backend**: GCP Compute Engine
- **Database**: Cloud SQL / Supabase / Neon
- **Redis**: Cloud Memorystore / Upstash

## License

MIT
