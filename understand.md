# Verity (TestPilot AI) — How the Whole Project Works

> A plain-English, function-by-function walkthrough of the entire codebase.
> Read top to bottom once; then use the section headings as a map.

---

## 0. The one-paragraph summary

Verity (branded "TestPilot" in code) is an **AI QA agent**. You give it:

- a **GitHub repo URL** (so it can read your front-end code), and
- a **live website URL** (so it can look at the running app).

It then **clones the repo**, **scans the real pages in a headless browser**, asks an
**LLM to design a QA test plan**, **generates executable Playwright tests**, **verifies
those tests against the live DOM before running them**, **runs them**, **classifies every
failure** (is it a broken test, or a broken app?), **auto-repairs broken tests**, and
finally **opens a GitHub pull request** with the generated test suite.

The whole thing is driven by a **LangGraph state machine** (a graph of "nodes") that
loops until tests pass or repair attempts are exhausted.

---

## 1. The big picture

```
                          ┌──────────────────────────────┐
   Browser (Next.js)      │  Frontend  apps/frontend     │
   localhost:3000  ─────► │  - dashboard, projects, runs  │
                          └───────────────┬──────────────┘
                                          │ HTTP  fetch("/api/...")
                                          ▼
                          ┌──────────────────────────────┐
                          │  Backend  apps/backend        │
                          │  FastAPI + LangGraph          │
                          │  localhost:3001               │
                          └───────┬───────────────┬──────┘
                                  │               │
                    SQLite (testpilot.db)     Playwright + LLM
                    projects / runs /         (real browser, OpenRouter/
                    test_cases                Groq/Bedrock model)
```

**Two servers, one idea.** The Next.js frontend is a thin UI. All the intelligence lives
in the FastAPI backend. The backend does not stream to the browser; instead it **writes
progress to SQLite**, and the frontend **polls** the run status every couple of seconds.

---

## 2. Repository map

```
Deepseek_Test/
├── apps/
│   ├── backend/                 ← all the logic (Python)
│   │   ├── app/
│   │   │   ├── main.py              entry point (FastAPI app)
│   │   │   ├── config.py            shim → core/config.py
│   │   │   ├── db.py                shim → repositories/database.py
│   │   │   ├── models.py            Pydantic domain models
│   │   │   ├── core/                config, logging, singleton, artifact store
│   │   │   ├── api/                 HTTP routers: auth, projects, test_runs
│   │   │   ├── auth/                login/session handling
│   │   │   ├── graph/               ← the pipeline (LangGraph)
│   │   │   │   ├── state.py            the shared "memory" of a run
│   │   │   │   ├── pipeline.py         wires nodes together, runs them
│   │   │   │   ├── nodes.py            most nodes + helpers
│   │   │   │   ├── *_node.py           the bigger nodes, one file each
│   │   │   │   ├── edges.py            routing decisions
│   │   │   │   ├── tools.py            repo scan / DOM tool / PR tool
│   │   │   │   └── playwright_runner.py Windows browser-execution helper
│   │   │   ├── repositories/database.py  SQLite CRUD
│   │   │   └── services/llm/          LLM provider abstraction
│   │   ├── tests/                 pytest suite
│   │   └── testpilot.db           the SQLite database
│   └── frontend/                 ← Next.js UI (TypeScript)
├── deploy/, Dockerfile.*, docker-compose.yml   deployment
└── README.md, context.md, implementation.md, understand.md   docs
```

---

## 3. Running the app

`_start.ps1` starts both servers:

```powershell
# backend (FastAPI) on :3001
python -m uvicorn app.main:app --host 127.0.0.1 --port 3001
# frontend (Next.js) on :3000
npm run dev
```

**Important:** the backend is started **without `--reload`**, so **after you edit Python
code you must restart it** for changes to take effect.

---

## 4. Request lifecycle — "start a run", step by step

This is the single most useful flow to understand.

1. **Frontend** → `POST /api/test-runs/{projectId}/start` with `{websiteUrl, repoUrl}`
   (see `apps/frontend/lib/api.ts` → `startRun`).
2. **`app/api/test_runs.py` → `start_run(...)`**
   - looks up the project (`db.get_project`),
   - creates a new `run_id` (UUID),
   - inserts a `runs` row with `status="analyzing"`,
   - launches the pipeline **in the background**:
     `asyncio.create_task(_execute_pipeline_and_update(...))`,
   - registers the task in `RUN_TASKS[run_id]` (so it can be cancelled),
   - returns `{runId}` immediately.
3. **`_execute_pipeline_and_update(...)`** awaits `run_pipeline(...)`. While it runs, the
   `on_status_change` callback fires after **every node**, writing the new status straight
   into the DB (`db.update_run(run_id, {"status": status})`).
4. **Frontend** polls `GET /api/test-runs/run/{runId}` every ~2 s
   → `get_run_details` returns `{run, testCases}` from SQLite. The user watches the run
   advance: `analyzing → page_inspection → app_understanding → test_planning → …`.
5. When the pipeline finishes, `_execute_pipeline_and_update` writes all test cases
   (`db.insert_case`), the run summary + timeline (`db.update_run`), and the PR URL.
6. A run can be stopped with `POST /api/test-runs/run/{runId}/cancel` (cancels the asyncio
   task) or removed with `DELETE /api/test-runs/run/{runId}`.

---

## 5. Backend entry point & configuration

### `app/main.py`
The FastAPI application object. It:
- calls `configure_logging()` (from `core/logging.py`),
- creates `FastAPI(title=...)`,
- mounts the three routers,
- adds wide-open CORS (so the :3000 frontend can call :3001),
- exposes `GET /api/health`.

### `app/core/config.py` → `class Settings`
A Pydantic `BaseSettings` object named `settings`. It reads `.env` files and environment
variables (case-insensitive). Groups:
- **Application:** `environment`, `backend_port`, `frontend_url`, `jwt_secret`, `log_level`.
- **LLM:** `llm_provider` ("openrouter" | "groq" | "bedrock"), `llm_temperature`, model ids,
  API keys, timeouts.
- **AWS/Bedrock**, **GitHub OAuth** client id/secret.
- **Storage:** `database_path`, `artifacts_dir`, `repos_dir`.

`app/config.py` is a **backwards-compatible shim** that just re-exports `settings`, so old
imports (`from app.config import settings`) keep working.

### `app/core/singleton.py` → `Singleton`
A tiny thread-safe base class. Any subclass that inherits it is constructed **exactly
once** per process (the instance is cached on the class). Used by the database, the LLM
service, the auth manager, credential store, session cache, artifact store, etc. — so they
all share state.

---

## 6. API layer (`app/api/`)

Every endpoint returns `{"success": true, "data": ...}`.

### `api/auth.py` (GitHub OAuth)
- `github_login()` → redirects to GitHub; if no client id configured, fakes a dev token
  and bounces to the frontend.
- `github_callback(code)` → exchanges the OAuth code for an access token, redirects to the
  frontend with a token.
- `get_current_user()` → returns a hard-coded dev user.

### `api/projects.py` (projects + analytics)
- `list_projects()`, `create_project(data)`, `get_project(id)`, `update_project(id, data)`,
  `delete_project(id)` (cascade-deletes runs + cases).
- `get_analytics()` → aggregates pass-rates over all runs/cases for the dashboard.
- `get_pipelines()`, `get_repositories()`, `get_active_agents()`, `get_active_session()` →
  small helper endpoints the UI calls.
- Note: the specific routes must be declared **above** `/{project_id}` or FastAPI would
  treat "analytics" as a project id.

### `api/test_runs.py` (the important one)
- `start_run(project_id, data)` → described in §4.
- `get_project_runs(project_id)` → `db.list_runs`.
- `get_run_details(run_id)` → `{run, testCases}`.
- `cancel_run(run_id)` → cancels `RUN_TASKS[run_id]`; marks stale runs cancelled.
- `delete_run(run_id)`.
- Private helpers: `_now_iso()`, `_execute_pipeline_and_update(...)`,
  `TERMINAL_STATUSES`, `RUN_TASKS`.

---

## 7. Persistence — `app/repositories/database.py`

SQLite, wrapped in a `Database(Singleton)` class. `app/db.py` is a shim exposing plain
functions (`insert_run`, `get_run`, …) that delegate to the singleton.

### Three tables
| Table | Holds |
|---|---|
| `projects` | id, name, repoUrl, websiteUrl, testEmail, status |
| `runs` | one row per pipeline run + summary counters + `timeline` JSON |
| `test_cases` | one row per test in a run + failure/repair provenance |

### Key methods
- `_get_conn()` — lazily opens the connection, runs `_SCHEMA`, then the two **idempotent
  migrations** (`_migrate_runs_table`, `_migrate_cases_table`) that `ALTER TABLE … ADD
  COLUMN` for any missing column. This is why the DB "upgrades itself" on first connect.
- Projects: `insert_project`, `list_projects`, `get_project`, `update_project`,
  `cascade_delete_project`.
- Runs: `insert_run`, `list_runs`, `get_run`, `update_run`, `delete_run`.
- Cases: `insert_case` (uses `_CASE_COLUMNS` defaults so callers may pass a partial dict),
  `list_cases`, `list_all_cases`.
- All writes go through a `threading.Lock` because FastAPI runs async but SQLite is
  single-connection.

---

## 8. The LangGraph pipeline (`app/graph/`)

This is the heart. A **graph** = nodes (work) + edges (routing). LangGraph executes nodes,
feeding each node the shared state and merging each node's **partial** return value back in.

### 8.1 Shared memory — `graph/state.py` → `class TestPilotState`

A `TypedDict`. Every node reads what it needs and returns only the keys it changes.

- **Inputs:** `run_id`, `project_id`, `repo_url`, `website_url`, `status`, `error`.
- **Linear outputs:** `auth_session`, `repo_analysis`, `page_inspections`,
  `app_understanding`, `features`, `test_plan_doc`, `test_plan`, `generated_tests`,
  `execution_results`, `pr_url`.
- **Loop fields:**
  - `evaluation_results` — per-test verdict (`{test_id: {verdict, category, reason}}`).
  - `failure_analyses` — per-test root cause.
  - `repair_attempts` — per-test repair counter.
  - `inconclusive_retries` — per-test retry counter.
  - `repaired_tests` — per-test replacement steps.
  - `suspected_app_bugs` — accumulating list.
  - `tests_to_execute` — which test ids to run next (`None` = all, `[]` = none).
- **Live-verify:** `live_verifications` — per-test pre-execution verification report.
- **Repair-integrity:** `test_intents` (immutable snapshot of each test's original meaning),
  `repair_statuses` (`ACCEPTED`/`REJECTED`).
- `messages` — a running log of human-readable notes.

**Reducers (subtle but critical).** Some keys have an `Annotated[..., reducer]` marker:
- `messages` uses `operator.add` (append).
- `evaluation_results`, `failure_analyses`, `repair_attempts`, `repaired_tests`,
  `inconclusive_retries`, `live_verifications`, `test_intents`, `repair_statuses` use
  `merge_dicts` (defined in the file).

Without `merge_dicts`, LangGraph's default **last-write-wins** would wipe per-test data
when the repair loop updates just one test. `merge_dicts` merges dicts instead.

### 8.2 Wiring — `graph/pipeline.py`

- `build_pipeline()` creates a `StateGraph(TestPilotState)`, `add_node(...)` for every node,
  and wires edges. Entry point is `auth_check`. Compiled with a `MemorySaver` checkpointer
  (keyed by `thread_id = run_id`).
  The compiled object is `pipeline_app = build_pipeline()`.
- `NODE_STATUS_MAP` translates each node name into the status string the UI shows
  (e.g. `test_evaluation → "evaluating"`).
- `run_pipeline(project_id, run_id, website_url, repo_url, on_status_change)`:
  1. builds `initial_state`,
  2. `async for event in pipeline_app.astream(...)`: for each finished node it logs the
     status, appends to a `timeline`, captures the **first-pass** execution snapshot
     (`first_pass_stats`/`first_pass_results` — needed because repaired tests end up
     passing, so the original failure must be captured here), calls `on_status_change` to
     persist the status, and sleeps 1.5 s to let the event loop serve polling requests,
  3. reads the final checkpointed state,
  4. computes `run_summary` (plannedTotal, passedFirstPass, passedFinal, notExecutedFinal,
     liveVerified/Corrected/Unverified counts, repairedCount, appBugCount, retryCount…),
  5. computes `case_details` (per-test failure story: failedFirstPass, root cause, repair
     attempts, live status),
  6. returns the final state with `run_summary`, `case_details`, `timeline` attached.

### 8.3 The nodes, one by one

> Notation: **reads** = state keys consumed, **writes** = keys returned.

#### 1. `auth_check_node` (`nodes.py`)
- **Reads:** project_id, website_url.
- **Does:** `auth_manager.get_or_authenticate_session(...)` → a `{storage_state_path, ...}`
  session. If the site is unreachable it logs a warning and fabricates a dev session
  (auth is best-effort).
- **Writes:** `auth_session`, `status`, `messages`; on hard error: `error`, `status="failed"`.

#### 2. `repo_analysis_node` (`nodes.py`)
- **Reads:** repo_url.
- **Does:** calls the LangChain tool `analyze_repo_structure.invoke({repo_url})`.
- **Writes:** `repo_analysis` = `{framework, language, routes[], components_count, package_json}`.

#### 3. `page_inspection_node` (`page_inspection_node.py`)
- **Reads:** website_url, `repo_analysis.routes`.
- **Does:** opens one headless Chromium, visits each route, runs a big `page.evaluate(...)`
  JS block that harvests headings/buttons/inputs/forms/tables/cards/links/images/
  `data-testid` elements and body text. Then:
  - `_stabilize_page(page)` waits for `networkidle` (bounded) + a short settle so SPAs
    finish rendering,
  - `_is_not_found_page(title, body)` detects in-app 404 pages (which pretend to be 200),
  - `classify_page_type(route, meta)` labels each page (authentication_page, dashboard, …),
  - grabs an **accessibility tree** (`aria_snapshot`) for semantic context.
- **Writes:** `page_inspections` (list of dicts), `status`.

#### 4. `app_feature_analysis_node` (`app_feature_analysis_node.py`)
- **Reads:** `page_inspections`, `repo_analysis`.
- **Does:** `_build_evidence(...)` compresses the inspections into text;
  `_llm_analyze_app_features(evidence)` asks the LLM for **one** JSON with `app` + `features`
  (this merged two older nodes into one call). On failure it falls back to
  `_rule_based_understanding` + `_rule_based_segregation`.
- **Writes:** `app_understanding`, `features`, `status`.

#### 5. `test_planning_node` (`nodes.py`)
- **Reads:** `app_understanding`, `features`, `page_inspections`, `repo_analysis`.
- **Does:**
  - `_build_test_planning_evidence(...)` assembles the evidence, including three grounding
    helpers: `_observed_visible_text`, `_observed_accessible_names`, `_observed_image_alts`,
    and `_build_verified_routes(...)` (only routes with real evidence are usable).
  - `_llm_generate_test_plan(evidence)` asks the LLM for a hierarchical plan.
  - For every scenario it enforces **grounding**: drops scenarios on unverified routes and
    runs `_ground_scenario(...)` which (with `_mentions_ungrounded_identity`) removes
    assertions on the app's *inferred* name (e.g. "ERP CRM Software") that is **not visible
    text**.
  - Flattens the plan into a list of scenarios (steps empty for now).
- **Writes:** `test_plan_doc`, `test_plan` (flattened scenarios), `status`.

#### 6. `playwright_gen_node` (`nodes.py`)
- **Reads:** `test_plan`, `page_inspections`.
- **Does:** `_build_aom_and_inspections_context(...)` builds AOM + element context;
  `_llm_generate_playwright_steps(...)` asks the LLM for concrete step objects
  (`{"action": "navigate"|"click"|"fill"|"assert_visible", ...}`) and Python code; falls
  back to `_fallback_playwright_steps(...)` + local code generation. It also builds
  `test_intents[test_id] = _build_test_intent(scenario, website_url)` — the **immutable
  original intent** used later to police repairs.
- **Writes:** `test_plan` (with steps), `generated_tests` (one suite file with code),
  `test_intents`, `status`.

#### 7. `live_verify_node` (`live_verify_node.py`) — pre-execution ground-truth check
- **Reads:** `test_plan`, `page_inspections`.
- **Does:** fully deterministic (no LLM). For each scenario it builds a searchable index of
  live elements (`_build_live_element_index`), extracts every selector reference
  (`_selector_hints`), and fuzzy-matches each against the live page (`_score_hint`,
  `_best_match`, `FUZZY_MATCH_THRESHOLD`). Outcomes:
  - **VERIFIED** — every selector exists.
  - **CORRECTED** — a confident fuzzy match; the step is rewritten in place.
  - **UNVERIFIED** — a selector could not be confirmed → **fail-closed**.
  For unverified scenarios it records a `status="not_executed"` result and puts only the
  eligible ids in `tests_to_execute`. If *any* selector is unconfirmed the scenario is
  unverified even if some were corrected.
- **Writes:** `test_plan` (possibly corrected), `live_verifications`, `execution_results`
  (the not-executed rows, if any), `tests_to_execute` (`None` if all eligible, else the
  eligible id list), `status`.

#### 8. `browser_execution_node` (`nodes.py`)
- **Reads:** `test_plan`, `tests_to_execute`, `repaired_tests`, project credentials.
- **Does:**
  - If `tests_to_execute` is not `None`, it builds a **scoped plan** (only those ids).
  - **Fail-closed short-circuit:** if `tests_to_execute` is `[]` (nothing eligible), it
    **never launches a browser** and returns the not-executed results untouched.
  - Otherwise, for each scenario, `_run_all_scenarios` opens a Chromium context and runs
    each step through `_execute_step(page, step, logs)`. `_execute_step` knows four verbs:
    `navigate`, `fill`, `click`, `assert_visible`, and handles `data-testid`, parent
    scoping, `.first`/`.nth` to avoid Playwright strict-mode violations. HTTP 429 raises
    `RateLimitError`. Use **repaired steps** when the repair loop produced them.
  - After a scoped run it **merges** fresh results back over the previous results (by test
    id, preserving plan order) so passing tests aren't lost.
- **Writes:** `execution_results` (each with `status`, `duration_ms`, `error`, `logs`,
  `rate_limited`, `http_status`), `status`.

#### 9. `test_evaluation_node` (`test_evaluation_node.py`) — deterministic triage
- **Reads:** `execution_results`.
- **Does:** `_classify_test_result(result)` assigns each test a **verdict** with **no LLM**:
  - `PASS` (passed, no error),
  - `NOT_EXECUTED` (status `not_executed` → category `verification_failure`),
  - `INCONCLUSIVE` (zero duration / rate-limited via `_is_rate_limited` / environment error),
  - `FAIL` (`_SELECTOR_ERROR_PATTERNS` in the error field → `selector_failure`, else
    `assertion_failure`).
  Order matters: selector errors are checked before environment errors so interaction
  timeouts count as repairable defects.
- **Writes:** `evaluation_results` (`{test_id: {verdict, category, reason, evidence}}`),
  `status`.

#### 10. `failure_analysis_node` (`failure_analysis_node.py`)
- **Reads:** `evaluation_results`, `execution_results`, `test_plan`, `page_inspections`.
- **Does:** for each `FAIL`, `_build_failure_context(...)` gathers the error, logs, plan and
  page inspection (incl. AOM), then `_llm_analyze_failure(...)` classifies the **root
  cause**: `selector_wrong`, `timing_issue`, `test_assumption_wrong` (all repairable) or
  `application_bug` (not repairable). Fallback = `selector_wrong`.
- **Writes:** `failure_analyses` (`{test_id: {root_cause, explanation, repairable}}`),
  `suspected_app_bugs` (when an app bug is found), `status`.

#### 11. `test_repair_node` (`test_repair_node.py`)
- **Reads:** `failure_analyses`, `repair_attempts`, `generated_tests`, `execution_results`,
  `test_plan`, `page_inspections`, `test_intents`, `repair_statuses`.
- **Does:** for each repairable test (not exhausted, not previously rejected):
  `_build_repair_prompt(...)` (includes the intent + ground-truth elements),
  `_llm_repair_test(...)` proposes new steps, then **`_validate_repair_integrity(intent,
  steps, website_url)`** enforces that the repair kept every action type, the same target
  route(s), and did not drop assertions. Failure → `{"status": "REJECTED"}` (terminal, never
  re-run). Success → `{"status": "ACCEPTED"}` + repaired steps. `MAX_REPAIR_ATTEMPTS = 3`.
- **Writes:** `repaired_tests`, `repair_attempts`, `repair_statuses`, `tests_to_execute`
  (the repaired ids, or `None`), `status`.

#### 12. `inconclusive_retry_node` (`inconclusive_retry_node.py`)
- **Reads:** `evaluation_results`, `inconclusive_retries`.
- **Does:** increments a retry counter for each `INCONCLUSIVE` test (max
  `MAX_INCONCLUSIVE_RETRIES = 2`); rate-limited tests back off (`_compute_backoff`, honouring
  `Retry-After`). Schedules the retryable ids for re-execution.
- **Writes:** `inconclusive_retries`, `tests_to_execute`, `status`.

#### 13. `github_pr_node` (`nodes.py`)
- **Reads:** `evaluation_results`, `repair_attempts`, `suspected_app_bugs`, repo_url.
- **Does:** builds a Markdown PR body (results table, auto-repaired tests, suspected app
  bugs, pre-execution verification failures) and calls the tool
  `create_github_pull_request.invoke(...)`.
- **Writes:** `pr_url`, `status` (`"completed"` if all PASS else
  `"completed_with_failures"`), `messages`.

#### 14. `abort_node` (`nodes.py`)
- Terminal failure handler; writes `status="failed"` and a message.

### 8.4 Routing — `graph/edges.py`

Conditional edges decide where to go next; they read the state and return a node name.

- `route_after_auth` — error → `abort`, else → `repo_analysis`.
- `route_after_evaluation` — all PASS → `github_pr`; any FAIL → `failure_analysis`; only
  INCONCLUSIVE → `inconclusive_retry`; nothing actionable → `github_pr`.
  (`NOT_EXECUTED` is none of these, so a fail-closed run with only not-executed tests goes
  straight to `github_pr`.)
- `route_after_failure_analysis` — repairable tests with attempts left (and not
  `REJECTED`) → `test_repair`; otherwise → `github_pr`.
- `route_after_inconclusive_retry` — retries left → `browser_execution`; else → `github_pr`.

Constants: `MAX_REPAIR_ATTEMPTS = 3`, `MAX_INCONCLUSIVE_RETRIES = 2` (mirrored in the nodes).

### 8.5 The loop, in words

```
auth_check → repo_analysis → page_inspection → app_feature_analysis
           → test_planning → playwright_gen → live_verify → browser_execution
                                                                    │
                                            ┌───────────────────────┘
                                            ▼
                                      test_evaluation
                       ┌──────────────┬──────────────┬───────────────┐
              all PASS │     FAIL     │ INCONCLUSIVE │  not_executed │
                       ▼              ▼              ▼               ▼
                  github_pr   failure_analysis  inconclusive_retry  github_pr
                                     │                  │
                                     ▼                  │
                               test_repair ─────────────┘
                                     │
                                     ▼
                             browser_execution  (scoped re-run; loop)
```

Deterministic counters guarantee termination; `GRAPH_RECURSION_LIMIT = 150` is only a
catastrophic circuit breaker.

---

## 9. Supporting services

### LLM stack — `app/services/llm/`
- `base.py` — `LLMProvider` abstract class + a **registry** (`register_provider`,
  `get_provider_class`, `available_providers`).
- `providers.py` — concrete providers: `OpenRouterProvider`, `GroqProvider`,
  `BedrockProvider`. Each builds a LangChain chat model lazily (third-party SDKs imported
  inside `build`).
- `factory.py` — `LLMFactory.get(provider, temperature)` resolves and **caches** a model per
  `(provider, temperature)`.
- `service.py` — `LLMService` facade (singleton `llm_service`) with `invoke_text` and
  `invoke_json(prompt, expect="object"|"array")`. It strips markdown fences, parses JSON,
  validates the shape, and returns `None` on any failure so callers keep their deterministic
  fallbacks. Helpers: `extract_text`, `strip_markdown_fences`.
- Nodes call `from app.services.llm.service import llm_service`.

### Playwright helpers
- `graph/playwright_runner.py` — on Windows, uvicorn's event loop can't create
  subprocesses, so `run_playwright(coro_fn)` runs the coroutine in a **dedicated thread
  with a `ProactorEventLoop`**. `target_slot(url)` is a per-host async lock that serializes
  browser work against one host.
- `graph/tools.py` — LangChain tools: `analyze_repo_structure` (git clone + scan routes/
  framework), `inspect_dom_elements`, `run_playwright_suite` (stub), and
  `create_github_pull_request`.

### Auth — `app/auth/`
- `auth_manager.py` — `AuthManager` (singleton `auth_manager`):
  `get_or_authenticate_session` checks the session cache, gets credentials, performs a login
  with Playwright, saves `storage_state`, and runs `verify_session_post_auth` (fail-fast
  probe).
- `credential_store.py` — in-memory per-project username/password (with a default fallback).
- `session_cache.py` — in-memory cache of `AuthSession` with expiry.
- `login_detector.py` — heuristic/LLM login-form detector (used by auth).

### Cross-cutting
- `core/logging.py` — `configure_logging()` (idempotent) and `get_logger()`.
- `core/artifact_store.py` — `ArtifactStore` writes files under `artifacts_dir`.
- `models.py` — Pydantic models (`Project`, `TestRun`, `TestCase`, `AuthSession`).

---

## 10. Frontend (`apps/frontend`)

Next.js App Router. Key pieces:
- `lib/api.ts` — the single place that calls the backend (`startRun`, `getRun`,
  `listProjects`, …).
- `app/page.tsx` — landing/login.
- `app/dashboard/**` — the main UI: overview, `analytics`, `runs`, `settings`, and
  per-project/per-run pages `app/dashboard/[projectId]/runs/[runId]/page.tsx` (which polls a
  run and renders the live status, test cases, and PR link).

The frontend does **no** business logic — it only calls the API and renders what SQLite has.

---

## 11. Data model quick reference

**`runs`** (selected columns): `id, projectId, status, trigger, startedAt, completedAt,
prUrl, plannedTotal, passedFirstPass, failedFirstPass, passedFinal, failedFinal,
inconclusiveFinal, repairedCount, appBugCount, retryCount, liveVerifiedCount,
liveCorrectedCount, liveUnverifiedCount, timeline`.

**`test_cases`** (selected columns): `id, testRunId, name, status, duration, error, logs,
code, failedFirstPass, rootCause, repairAttempts, firstPassError, analysisNote, liveStatus`.

Run `status` values you'll see: `analyzing, page_inspection, app_understanding,
test_planning, playwright_gen, live_verify, execution, evaluating, analyzing_failures,
repairing, retrying, creating_pr, completed, completed_with_failures, failed, cancelled`.

Test `status` values: `passed, failed, not_executed` (+ transient `pending`).

---

## 12. Glossary & "where do I change X?"

| I want to… | Go to |
|---|---|
| Add/change an HTTP endpoint | `app/api/*.py` |
| Change how a run starts/streams status | `api/test_runs.py`, `graph/pipeline.py` |
| Add a pipeline step | `graph/nodes.py` + `graph/pipeline.py` + `graph/edges.py` |
| Change failure triage rules | `graph/test_evaluation_node.py` |
| Change repair behavior / integrity rules | `graph/test_repair_node.py`, `graph/edges.py` |
| Change pre-execution verification | `graph/live_verify_node.py` |
| Change what the LLM is asked | the `_llm_*` functions in each node file |
| Change DB schema/columns | `repositories/database.py` |
| Add an LLM provider | `services/llm/providers.py` (decorate with `@register_provider`) |
| Change app settings | `core/config.py` + `.env` |

**Terminology:** *node* = one pipeline step; *state* = shared run memory; *edge* = routing
rule; *verdict* = PASS/FAIL/INCONCLUSIVE/NOT_EXECUTED; *root cause* = why a FAIL happened;
*intent* = what a test is fundamentally checking (repairs may not change it); *fail-closed*
= if a test can't be verified against the live DOM, it is **not run** and is reported as
`not_executed` (never a fake pass).

---

## 13. The mindset behind the design

Three ideas show up everywhere and explain most of the code:

1. **Ground everything in real evidence.** Tests may only reference routes, text, and
   elements actually observed on the live site (`_build_verified_routes`, `_ground_scenario`,
   `live_verify_node`). The LLM is never trusted to invent selectors.
2. **Distinguish "our test is wrong" from "your app is broken."** Deterministic evaluation
   first, LLM root-cause second; test defects get repaired, app bugs get reported in the PR
   as *suspected application bugs*.
3. **Never fake a pass.** Repairs must preserve intent (`_validate_repair_integrity`), and
   anything that can't be verified is `not_executed`, not "passed".
