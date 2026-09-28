# TestPilot AI — Backend Architecture Hardening, AWS Bedrock Integration & EC2 Deployment Plan

**Type:** Architecture refactor + packaging + deployment readiness
**Scope:** Backend only. The Next.js frontend is **already implemented and out of scope**.
**Status:** Proposed

---

## 0. Guiding Principle

> The existing TestPilot AI QA logic **is the product**. This task is **not** to reinvent the product.

The core QA-agent code and the LangGraph workflow are **already implemented and working**. The task is to make the existing backend:

**cleaner + modular + provider-agnostic + Bedrock-ready + EC2-ready + Docker-ready + persistent + testable** — while **maintaining existing behavior**.

**The most important rule:**
> Improve the architecture *around* the existing application. **Do not** change the existing QA-agent business logic or LangGraph workflow unless it is *required* to complete the refactor.

**Prefer minimal safe refactoring over aggressive rewriting.** If a proposed change is not necessary for the objectives, do not implement it. If an existing implementation is already correct and does not conflict with the target architecture, preserve it.

---

## 1. Primary Objective

Refactor the existing Python backend so that it is:

- modular
- configurable
- provider-agnostic
- testable
- maintainable
- deployment-ready
- AWS Bedrock compatible
- EC2 compatible
- Docker compatible

…while **preserving existing functionality and behavior**.

---

## 2. Current Application

**TestPilot AI** is an autonomous QA engineering system.

**Existing backend stack:** Python · FastAPI · LangGraph StateGraph · LangChain · Pydantic v2 · Playwright · SQLite · GitHub integration.

**Frontend stack (out of scope):** Next.js · React · TypeScript · Tailwind CSS.

---

## 3. Existing QA Pipeline — DO NOT REDESIGN

The graph is already implemented. Its conceptual flow is:

```
auth_check_node
  ↓
repo_analysis_node
  ↓
page_inspection_node
  ↓
code_analysis_node
  ↓
app_understanding_node
  ↓
feature_segregation_node
  ↓
test_planning_node
  ↓
playwright_gen_node
  ↓
live_verify_node
  ↓
browser_execution_node
  ↓
test_evaluation_node
```

**Failure path:**
```
test_evaluation_node → failure_analysis_node → test_repair_node → browser_execution_node
```

**Inconclusive path:**
```
test_evaluation_node → inconclusive_retry_node → browser_execution_node
```

**Successful completion:** GitHub PR

### Do NOT
- redesign this topology
- replace LangGraph
- remove existing nodes
- change routing logic
- remove deterministic fallbacks
- rewrite the test-generation strategy
- replace Playwright
- introduce another orchestration framework

Only modify nodes where necessary to **replace their direct LLM calls with the new `LLMService`**.

---

## 4. Current Refactor Problems

### 4.1 LLM provider
`app/llm.py` contains provider branching:

```python
if provider == "openrouter":
    ...
else:
    ...
```

This does not scale cleanly to Bedrock and additional providers.

### 4.2 Duplicated LLM handling
Approximately **six** LLM call sites perform variations of:

```python
llm = get_llm(...)
response = await llm.ainvoke(prompt)
strip_markdown_fences(...)
json.loads(...)
fallback(...)
```

This parse/fallback logic is duplicated and must be centralized.

**Affected areas:**
- `app/graph/nodes.py`
- `app/graph/app_understanding_node.py`
- `app/graph/feature_segregation_node.py`
- `app/graph/failure_analysis_node.py`
- `app/graph/test_repair_node.py`

**Remain deterministic — do not change unnecessarily:**
- `test_evaluation_node`
- `inconclusive_retry_node`
- `live_verify_node`

---

## 5. Target Backend Architecture

```
apps/backend/app/
├── core/
│   ├── config.py
│   ├── singleton.py
│   └── logging.py
│
├── services/
│   └── llm/
│       ├── __init__.py
│       ├── base.py
│       ├── providers.py
│       ├── factory.py
│       └── service.py
│
├── repositories/
│   └── database.py
│
├── config.py        # backward-compatible shim
├── llm.py           # backward-compatible shim
├── db.py            # backward-compatible shim
│
├── api/             # unchanged structure
├── auth/            # unchanged structure
└── graph/           # unchanged structure
```

The existing **API** and **graph** package structure must remain intact.

---

## 6. Design Patterns

Use patterns **only where they genuinely reduce coupling**.

| Pattern | Applied to | Notes |
|---|---|---|
| **Singleton** | `Settings`, `Database`, `LLMService`, `CredentialStore`, `ArtifactStore`, `AuthSessionCache` | Shared implementation in `app/core/singleton.py`. Do **not** create unnecessary Singleton wrappers for objects that do not need shared lifecycle/state. |
| **Factory** | `LLMFactory` | Creates the configured provider. Callers must not know how Bedrock/OpenRouter/Groq clients are constructed. |
| **Strategy** | `LLMProvider` + `OpenRouterProvider`, `GroqProvider`, `BedrockProvider` | Providers must be interchangeable. |
| **Registry** | Provider registry | Adding a provider must not require a large `if/else` chain. Conceptual: `@register_provider("bedrock")` on `class BedrockProvider(...)`. |
| **Repository** | `Database` | Move SQLite persistence behind an abstraction; the rest of the app must not depend on the SQLite connection implementation. |
| **Facade** | `LLMService` | `await llm_service.invoke_text(prompt)` / `await llm_service.invoke_json(prompt, expect="object")`. |
| **Dependency Inversion** | LangGraph nodes | Nodes depend on the LLM service abstraction, not on concrete Bedrock/OpenRouter/Groq clients. Provider selection must be **configuration-driven**. |

---

## 7. Phase 1 — Configuration

**Create:**
- `app/core/config.py`
- `app/core/singleton.py`
- `app/core/logging.py`

**Keep:** `app/config.py` as a **backward-compatible shim** that re-exports the new settings interface.

---

## 8. Configuration Requirements (Pydantic Settings)

Configuration must support the following, grouped by domain.

### Application
`ENVIRONMENT` · `BACKEND_PORT` · `BACKEND_URL` · `FRONTEND_URL` · `JWT_SECRET` · `LOG_LEVEL`

### LLM
`LLM_PROVIDER` · `LLM_TEMPERATURE` · `LLM_MAX_TOKENS` · `LLM_TIMEOUT_S` · `LLM_MAX_RETRIES`

Supported providers: `bedrock` · `openrouter` · `groq`

### AWS / Bedrock
`AWS_REGION` · `BEDROCK_MODEL_ID` · `BEDROCK_GUARDRAIL_ID` · `BEDROCK_GUARDRAIL_VERSION`

### OpenRouter
Use the **existing** configuration values (no changes to behavior).

### Groq
Use the **existing** configuration values (no changes to behavior).

### Storage
`DATABASE_PATH` · `ARTIFACTS_DIR` · `REPOS_DIR`

All paths must be configurable. **Do not hard-code deployment-specific filesystem paths.**

---

## 9. Environment Files

Provide `.env.example` with **placeholders only**.

**Never commit real:** AWS credentials · OpenRouter API keys · Groq API keys · GitHub tokens · JWT secrets · application credentials.

The company sandbox must receive secrets through **approved environment/configuration mechanisms**.

---

## 10. Phase 2 — LLM Provider Architecture

**Create:**
- `app/services/llm/base.py`
- `app/services/llm/providers.py`
- `app/services/llm/factory.py`
- `app/services/llm/service.py`

---

## 11. LLM Provider Interface

Create an abstraction similar to:

```python
class LLMProvider(ABC):
    name: str

    @abstractmethod
    def build(self, temperature: float):
        ...
```

The exact implementation should follow the **existing project's LangChain version and APIs**. Do not unnecessarily constrain the implementation to an artificial interface if LangChain's current abstractions provide a cleaner solution.

---

## 12. OpenRouter Provider

Migrate the existing OpenRouter implementation into `OpenRouterProvider`.

**Preserve its current behavior.** Do not change prompts or model behavior unnecessarily.

---

## 13. Groq Provider

Migrate the existing Groq implementation into `GroqProvider`.

**Preserve its current behavior.**

---

## 14. AWS Bedrock Provider

Implement `BedrockProvider` using:

- `langchain-aws`
- `ChatBedrockConverse`
- `boto3` for AWS integration

**Configuration:** `AWS_REGION` · `BEDROCK_MODEL_ID`
**Optional:** `BEDROCK_GUARDRAIL_ID` · `BEDROCK_GUARDRAIL_VERSION`

**Do not hard-code the company's final Bedrock model ID** — it will be supplied by the company/AWS environment.

---

## 15. AWS Authentication

For EC2, the preferred authentication path is:

```
EC2 → IAM Instance Role → Bedrock
```

- **Do not hard-code access keys.**
- The application must use the normal **boto3 credential provider chain**.
- Local development may support environment-based AWS credentials if needed, but they must **never be committed**.

---

## 16. LLM Factory

Implement `LLMFactory`, which resolves the configured provider from the registry.

Conceptually:

```python
LLMFactory.get(provider=None, temperature=...)
```

Provider resolution chain:

```
configuration → provider registry → provider implementation → LangChain chat model
```

Requirements:
- Avoid provider-specific logic throughout the graph.
- **Cache** model/client instances appropriately rather than reconstructing them on every node invocation.
- Do not create unnecessary global state beyond the intended lifecycle management.

---

## 17. LLM Service

Create `LLMService` as the common **facade**, providing:

- `invoke_text(...)`
- `invoke_json(...)`

`invoke_json()` must centralize:
- LLM invocation
- response extraction
- Markdown code-fence removal
- JSON parsing
- validation
- error handling
- logging
- existing **graceful fallback** behavior

**The service must preserve the existing application's fallback behavior.** Do not remove fallback logic simply because the LLM abstraction changed.

---

## 18. Important Async Requirement

The existing code uses **asynchronous** LLM calls.

- Preserve async behavior where currently required.
- Do **not** convert the LangGraph pipeline into blocking synchronous calls.
- Use the appropriate LangChain **async** invocation API.
- Final implementation must remain compatible with **FastAPI** and the existing **LangGraph** execution model.

---

## 19. Phase 3 — Refactor Existing LLM Call Sites

Refactor the six existing LLM call areas, replacing direct LLM construction/invocation with `LLMService`.

| File | Function | Target call |
|---|---|---|
| `nodes.py` | `_llm_generate_test_plan` | `invoke_json(..., expect="object")` |
| `nodes.py` | `_llm_generate_playwright_steps` | `invoke_json(..., expect="object")` |
| `app_understanding_node.py` | `_llm_understand_app` | `invoke_json(..., expect="object")` |
| `feature_segregation_node.py` | `_llm_segregate_features` | `invoke_json(..., expect="object")` |
| `failure_analysis_node.py` | `_llm_analyze_failure` | `invoke_json(..., expect="object")` |
| `test_repair_node.py` | `_llm_repair_test` | `invoke_json(..., expect="array")` |

Choose `expect="object"` or `expect="array"` according to the **existing** expected response shape.

---

## 20. Preserve Existing Prompts

**This is critical.** Do not rewrite the existing prompts as part of this refactor.

Preserve:
- prompts
- expected JSON structures
- deterministic fallbacks
- test-generation semantics
- repair semantics
- evaluation semantics

…unless a change is **technically required** by the new service abstraction.

> The purpose of this phase is **architectural refactoring, not prompt engineering**.

---

## 21. Phase 4 — Database Repository

The current SQLite implementation uses module-level state/functions. Refactor it into:

`app/repositories/database.py` — with a `Database` abstraction that owns:
- SQLite connection
- locking
- schema initialization
- migrations
- CRUD operations

**Preserve all existing database behavior.**

---

## 22. Backward Compatibility

Keep `app/db.py` as a **compatibility shim**. Existing callers should continue working.

For example, `api/projects.py`, `api/test_runs.py`, and graph nodes should **not** require a large rewrite merely because the database implementation moved.

---

## 23. SQLite Deployment

- **SQLite remains the initial database.** Do **NOT** introduce PostgreSQL now.
- The architecture should make PostgreSQL *possible later*.
- The SQLite database must **persist across Docker container recreation** — use a persistent Docker volume or host-mounted directory.
- Do not store the production SQLite database only inside the disposable container filesystem.

---

## 24. Phase 5 — Existing Singleton Stores

Unify the lifecycle pattern for:
- `CredentialStore`
- `ArtifactStore`
- `AuthSessionCache`

Use the common **Singleton** infrastructure where appropriate.

**Do not change their business behavior.** The refactor should primarily improve:
- consistency
- testability
- lifecycle management

---

## 25. Phase 6 — Docker / Deployment

The existing Docker configuration needs correction. **Known issue (version drift):**

```
Dockerfile.backend → Playwright 1.42.0
requirements.txt   → Playwright 1.62.0
```

These **must be aligned** — use **one compatible Playwright version throughout**. Do not leave version drift.

---

## 26. Dockerfile Requirements

Update `Dockerfile.backend` to provide a **reproducible** backend image:

- compatible Python version
- compatible Playwright version (aligned with `requirements.txt`)
- Playwright browser dependencies
- application dependencies
- **non-root** runtime
- **healthcheck** (targets `/api/health`)
- port **3001** exposed
- configurable environment
- persistent storage paths
- appropriate working directory

Do not expose unnecessary ports.

---

## 27. Docker Compose

The existing compose file provisions **PostgreSQL and Redis**, even though the application **does not use them**. **Remove these unnecessary services.**

The initial deployment compose should represent the **actual** architecture:

```
docker-compose.yml
  backend
    ├── SQLite persistent volume
    ├── artifacts volume
    └── repos volume
```

Do not provision infrastructure that the application does not use.

---

## 28. EC2 Deployment Architecture

```
Private GitHub
      |
      v
     EC2
      |
      v
   Docker
      |
      +-------------------+
      |                   |
      v                   v
   FastAPI             SQLite
      |
      +------+
             |
             v
       AWS Bedrock
```

**EC2 access path:**
```
AWS Console → EC2 → Systems Manager → Session Manager → Terminal
```

> No SSH requirement should be assumed if **Session Manager** is the company's approved access mechanism.

---

## 29. Company AWS Sandbox — Required Components

Minimum requirements to run in the company AWS development/sandbox environment.

**1. EC2 instance** — enough CPU/RAM/storage for: Python backend, Docker, Playwright/Chromium, repository cloning, generated artifacts, SQLite, normal execution. Instance type chosen per company standards/workload. **Do not hard-code a specific instance type.**

**2. Systems Manager** — instance manageable via **SSM Session Manager**; requires the appropriate SSM configuration/IAM permissions per company setup.

**3. IAM Role** — attach a role with the **minimum required** permissions. For Bedrock this should include permission to invoke the approved model, typically `bedrock:InvokeModel`. If the selected API/model needs more, **document explicitly** — do not grant broad admin. If guardrails are enabled, include **only** the required guardrail permissions.

**4. Bedrock Model Access** — the account/region must have access to the selected model. The company provides `BEDROCK_MODEL_ID` and `AWS_REGION`. **Do not assume the model ID** — treat as configuration.

**5. Docker** — must be available on EC2: clone/pull private GitHub repo, build image, run container, persist SQLite.

**6. GitHub access** — EC2 needs an **approved** method for the private repo (GitHub token / deploy key / GitHub App / other). **Do not assume which mechanism.** Never hard-code GitHub credentials.

**7. Network access** — EC2 must reach AWS Bedrock, GitHub, and the target application (depending on architecture). Exact VPC/security-group/proxy config is environment-specific. **Do not hard-code network assumptions.**

---

## 30. What Does NOT Need To Be Provisioned Initially

Do **NOT** require: **S3 · PostgreSQL · Redis · ECS · EKS · Kubernetes · Lambda · RDS · ElastiCache · Kafka** — unless the company specifically requests them.

The initial application runs as: **EC2 + Docker + SQLite + Bedrock**.

---

## 31. Persistent EC2 Storage

The EC2 deployment needs persistent storage for: **SQLite database · artifacts · cloned repositories**.

Recommended structure (exact host path must remain **configurable**):

```
/opt/testpilot/
    ├── data/
    │     └── testpilot.db
    ├── artifacts/
    ├── repos/
    └── application/
```

**Do not put the database in Git.**

---

## 32. Deployment Script

Create `deploy/deploy.sh` (or equivalent) to make deployment repeatable. Conceptually:

```
pull latest code
      ↓
build Docker image
      ↓
stop previous backend container
      ↓
start new backend container
      ↓
preserve persistent volumes
      ↓
verify health endpoint
```

Do not implement a complex CI/CD system unless requested.

---

## 33. Deployment Documentation

Create `deploy/EC2.md` (or an equivalent README deployment section) documenting:

- EC2 prerequisites
- IAM role requirements
- SSM access
- Docker installation
- GitHub access
- environment configuration
- Bedrock model configuration
- persistent directories/volumes
- deployment commands
- health check
- troubleshooting
- logs
- container restart
- database persistence

> The documentation should be usable by **another developer who did not build the application**.

---

## 34. Sandbox Environment Verification

Provide a small Bedrock integration test: `tests/integration/test_bedrock.py` (or `test_bedrock.py`).

It should verify the path:
```
EC2 → IAM credentials → boto3 → Bedrock → configured model
```
using a **minimal** model invocation.

> Do **not** make the entire unit test suite dependent on Bedrock.

---

## 35. Local vs Company Environment

The application must support **two** configurations.

**Local development**
```
LLM_PROVIDER=openrouter
# or
LLM_PROVIDER=groq
```
Allows development without the company AWS sandbox.

**Company EC2 environment**
```
LLM_PROVIDER=bedrock
AWS_REGION=<company-region>
BEDROCK_MODEL_ID=<company-provided-model>
```
Authentication comes from the **EC2 IAM role**.

> The graph itself must **not** know which environment it is running in.

---

## 36. Testing — Existing Tests

Before declaring the refactor complete, run:

```
pytest tests/
```

- **All existing tests must remain green** (approximately seven existing test files).
- Do **not** modify tests simply to make failures disappear.
- If a test must change due to a legitimate architectural change, **explain why**.

---

## 37. New Tests

Add focused tests for:

- **Provider registry** — `openrouter`, `groq`, `bedrock` resolve correctly.
- **Factory** — `LLMFactory.get(...)` returns the correct provider/model configuration.
- **LLMService** — normal text response; JSON response; Markdown fence stripping; malformed JSON; expected object; expected array; fallback/error behavior. **Mock the provider.**
- **Settings** — environment variables correctly override defaults.
- **Database** — the repository abstraction preserves existing behavior.
- **Graph smoke test** — run the graph with a **dummy/stubbed** LLM provider; verify nodes use `LLMService` rather than constructing a provider directly.

---

## 38. Bedrock Tested Separately

- Do **not** require AWS credentials for normal `pytest`. Unit tests use mocks/stubs.
- Bedrock verification is an **explicit integration/smoke test**, e.g. `pytest tests/integration/test_bedrock.py`, run inside the AWS sandbox.

---

## 39. API Compatibility

The existing REST API contract must remain **unchanged**.

Do **not** modify: endpoint paths · request structures · response structures · status-code semantics — unless absolutely required.

**The frontend must continue to work without modification.**

---

## 40. Non-Goals

Do **NOT**:
- rewrite the frontend
- redesign the QA workflow
- change LangGraph topology
- replace Playwright
- remove deterministic logic
- introduce synthetic datasets
- introduce PostgreSQL now
- introduce S3 now
- introduce Redis
- introduce Kubernetes
- introduce ECS
- build unnecessary microservices
- rewrite working prompts
- change business behavior
- add unnecessary dependencies

---

## 41. Synthetic Data

Synthetic data is **not required** for this implementation. The current system should work from:
**Target GitHub repository + Target application URL + Actual runtime UI.**

Do not create a synthetic-data subsystem. Test fixtures may still be used where technically required by unit/integration tests — that is different from introducing a synthetic dataset or synthetic application.

---

## 42. Backward Compatibility

Keep compatibility shims: `app/config.py` · `app/llm.py` · `app/db.py` — so existing imports continue to work during the refactor.

> The goal is to migrate the internals **without** unnecessarily breaking the rest of the application.

---

## 43. Refactor Safety Rules

**Before modifying a file:**
1. Read the existing implementation.
2. Understand its callers.
3. Identify its tests.
4. Preserve behavior.
5. Make the **smallest appropriate change**.

**After modifying:**
- Run focused tests.
- Fix regressions.
- Run the complete test suite.
- Verify imports.
- Verify application startup.
- Verify `/api/health`.
- Verify provider resolution.
- Verify Docker build.

> Do not perform a large rewrite just because a cleaner architecture is possible.

---

## 44. Dependency Changes

**Expected new dependencies:** `langchain-aws` · `boto3`

Ensure versions are compatible with the project's existing **LangChain · LangGraph · Python · Playwright**. Do not blindly upgrade unrelated dependencies — **resolve version compatibility deliberately**.

---

## 45. Final Validation Checklist

The implementation is complete **only when all** of the following are true.

### Architecture
- [ ] `core/` exists
- [ ] Singleton foundation exists
- [ ] centralized configuration exists
- [ ] centralized logging exists
- [ ] LLM provider abstraction exists
- [ ] provider registry exists
- [ ] LLM factory exists
- [ ] LLM facade/service exists
- [ ] database repository exists
- [ ] compatibility shims work

### LLM
- [ ] OpenRouter works
- [ ] Groq works
- [ ] Bedrock provider exists
- [ ] provider selection is configuration-driven
- [ ] nodes do not construct concrete providers
- [ ] duplicated JSON parsing is removed
- [ ] existing prompts are preserved
- [ ] existing fallbacks are preserved

### AWS
- [ ] `boto3` configured
- [ ] `langchain-aws` configured
- [ ] Bedrock model ID configurable
- [ ] AWS region configurable
- [ ] IAM-based authentication supported
- [ ] no AWS secrets in source code

### Database
- [ ] SQLite remains the initial database
- [ ] database abstraction exists
- [ ] existing behavior preserved
- [ ] database path configurable
- [ ] database persists across Docker recreation

### Docker
- [ ] Playwright versions aligned
- [ ] image builds successfully
- [ ] backend runs as non-root
- [ ] healthcheck works
- [ ] port 3001 exposed
- [ ] persistent directories configured

### EC2
- [ ] deployment documentation exists
- [ ] deploy script exists
- [ ] SSM deployment path documented
- [ ] IAM requirements documented
- [ ] Bedrock requirements documented
- [ ] GitHub access requirements documented
- [ ] persistent storage documented

### Testing
- [ ] existing tests pass
- [ ] provider tests pass
- [ ] `LLMService` tests pass
- [ ] configuration tests pass
- [ ] database tests pass
- [ ] graph smoke test passes
- [ ] Bedrock integration test is available
- [ ] `/api/health` works
- [ ] backend starts successfully
- [ ] Docker build succeeds

---

## 46. Final Instruction

The existing TestPilot AI QA logic is the product. **This task is not to reinvent the product.**

The task is to make the existing backend:

**cleaner + modular + provider-agnostic + Bedrock-ready + EC2-ready + Docker-ready + persistent + testable**

…while maintaining existing behavior.

**Prefer minimal safe refactoring over aggressive rewriting.**

- If a proposed architectural change is **not necessary** for the objectives above, **do not implement it**.
- If an existing implementation is **already correct** and does not conflict with the target architecture, **preserve it**.
