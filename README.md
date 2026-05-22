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
