# TestPilot AI — Backend Deployment on AWS EC2

This guide describes how to run the TestPilot AI **backend** (FastAPI + Playwright,
SQLite storage, AWS Bedrock LLM access) on a single AWS EC2 instance using Docker.

It is written so that another developer who did not build the application can
follow it end-to-end.

---

## 1. Architecture

```
Private GitHub repo
        │  (deploy key / token / GitHub App)
        ▼
       EC2 ── Docker ──► FastAPI (:3001)
        │                   │
        │                   ├── SQLite  (/opt/testpilot/data/testpilot.db)
        │                   ├── Artifacts (/opt/testpilot/artifacts)
        │                   └── Repos     (/opt/testpilot/repos)
        ▼
   AWS Bedrock  (via IAM instance role — no hard-coded credentials)
```

The instance is managed through **AWS Systems Manager → Session Manager**
(a terminal in the browser). SSH access is **not** required.

---

## 2. Prerequisites

### 2.1 EC2 instance
- Any current Amazon Linux 2023 or Ubuntu 22.04+ AMI.
- Enough CPU/RAM/disk for: Docker, Playwright/Chromium, repository cloning,
  generated artifacts and the SQLite database. Pick the instance type per
  company standards — **do not hard-code one here**.
- Recommended: attach an EBS volume (or ensure the root volume) with enough
  space for `artifacts/` and `repos/`.

### 2.2 Systems Manager (SSM)
- The instance must run the SSM Agent (pre-installed on Amazon Linux) and have
  an IAM role allowing `ssm:UpdateInstanceInformation` plus the standard
  `AmazonSSMManagedInstanceCore` managed policy.
- Access the shell via: **AWS Console → EC2 → Instance → Connect → Session Manager**.

### 2.3 IAM role for Bedrock
Attach an instance role (least privilege) that permits invoking the approved
model, e.g.:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": "arn:aws:bedrock:<region>::foundation-model/<model-id>"
    }
  ]
}
```

- `bedrock:InvokeModelWithResponseStream` is only needed if streaming is used.
- If **guardrails** are enabled, add **only** the required guardrail permissions
  (e.g. `bedrock:ApplyGuardrail`).
- Do **not** grant broad admin permissions.
- Do **not** put access keys in the app — boto3 uses the instance role via its
  default credential provider chain.

### 2.4 Bedrock model access
- The account/region must have **model access granted** in the Bedrock console.
- The company supplies `BEDROCK_MODEL_ID` and `AWS_REGION`. Treat these as
  configuration — **do not assume a model id**.

### 2.5 Network access
The instance must be able to reach:
- **AWS Bedrock** (regional endpoint),
- **GitHub** (to clone repositories),
- **The target application URL** being tested (if applicable).

Exact VPC / security-group / proxy configuration is environment-specific; do
**not** hard-code network assumptions here.

Only port **3001** (the API) needs to be reachable from wherever the frontend
runs. There is no need to expose any other port.

---

## 3. Install Docker (Amazon Linux 2023)

```bash
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"   # log out/in (or start a fresh SSM session) to take effect
docker --version
```

On Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y docker.io git
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

---

## 4. Get the code (private GitHub repo)

Use the company's **approved** GitHub access mechanism (deploy key, fine-grained
PAT, or GitHub App token). Never bake credentials into the image.

Example (HTTPS with a token — adapt to the approved method):

```bash
sudo mkdir -p /opt/testpilot/application
sudo chown "$USER":"$USER" /opt/testpilot/application
git clone https://<APPROVED-METHOD>@github.com/<org>/<repo>.git /opt/testpilot/application
cd /opt/testpilot/application
```

---

## 5. Configure the environment

Create the persistent storage directories and the env file:

```bash
sudo mkdir -p /opt/testpilot/data /opt/testpilot/artifacts /opt/testpilot/repos
sudo chown -R "$USER":"$USER" /opt/testpilot

cd /opt/testpilot/application
cp .env.example .env
```

Edit `/opt/testpilot/application/.env` for the **company environment**:

```env
ENVIRONMENT=production

# Use AWS Bedrock in EC2. No keys here — the IAM instance role is used.
LLM_PROVIDER=bedrock
AWS_REGION=<company-region>
BEDROCK_MODEL_ID=<company-provided-model-id>
# Optional guardrails
BEDROCK_GUARDRAIL_ID=
BEDROCK_GUARDRAIL_VERSION=

# Storage (the deploy script also sets these for the container)
DATABASE_PATH=/data/testpilot.db
ARTIFACTS_DIR=/artifacts
REPOS_DIR=/repos

JWT_SECRET=<strong-random-value>
FRONTEND_URL=<where the frontend is served from>
BACKEND_PORT=3001
```

> Local development instead uses `LLM_PROVIDER=openrouter` (with
> `OPENROUTER_API_KEY`) or `LLM_PROVIDER=groq` (with `GROQ_API_KEY`). The graph
> itself does not know which environment it is running in.

---

## 6. Persistent storage layout

```
/opt/testpilot/
  ├── data/                -> mounted at /data        (testpilot.db lives here)
  ├── artifacts/           -> mounted at /artifacts   (screenshots, reports)
  ├── repos/               -> mounted at /repos       (cloned target repositories)
  └── application/         (the checked-out repository)
```

These directories are bind-mounted into the container, so **the SQLite database
and generated artifacts survive container recreation**. Do not store the
database inside the container filesystem, and never commit it to Git.

---

## 7. Deploy

Use the provided script (build → replace container → health check):

```bash
cd /opt/testpilot/application
./deploy/deploy.sh
```

Override defaults when needed:

```bash
DATA_DIR=/opt/testpilot/data \
ARTIFACTS_DIR=/opt/testpilot/artifacts \
REPOS_DIR=/opt/testpilot/repos \
HOST_PORT=3001 \
./deploy/deploy.sh
```

Or use Docker Compose (named volumes):

```bash
docker compose up -d --build
```

---

## 8. Health check

```bash
curl -fsS http://localhost:3001/api/health
# {"status":"ok","app":"TestPilot AI Python Backend","environment":"production"}
```

---

## 9. Logs, restart, upgrades, rollback

```bash
# Logs (follow)
docker logs -f testpilot-backend

# Restart
docker restart testpilot-backend

# Upgrade: pull new code, then re-run the deploy script (data is preserved)
cd /opt/testpilot/application && git pull && ./deploy/deploy.sh

# Rollback: check out the previous revision and re-deploy
git checkout <previous-tag-or-commit> && ./deploy/deploy.sh
```

Because the database and artifacts are on host bind mounts, they are **untouched**
by container replacement.

---

## 10. Verify Bedrock access

Run the optional integration test inside the sandbox (requires `TESTPILOT_BEDROCK=1`
and the IAM role in place):

```bash
cd /opt/testpilot/application/apps/backend
TESTPILOT_BEDROCK=1 \
AWS_REGION=<company-region> \
BEDROCK_MODEL_ID=<company-provided-model-id> \
python -m pytest tests/integration/test_bedrock.py -q
```

This verifies the path: **EC2 → IAM credentials → boto3 → Bedrock → configured model**
with a minimal model invocation.

---

## 11. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Container exits immediately | Check `docker logs testpilot-backend`; usually a bad `.env` or missing dependency. |
| Health check never passes | App not listening on 3001, or DB/artifacts/repos dirs not writable by uid 10001. Confirm bind-mount ownership. |
| `docker: permission denied` | You are not in the `docker` group — start a fresh SSM session after `usermod`. |
| Bedrock `AccessDeniedException` | IAM role missing `bedrock:InvokeModel` for the model ARN, or model access not granted. |
| Bedrock `ValidationException` (model) | Wrong `BEDROCK_MODEL_ID`/`AWS_REGION`, or model not enabled in that region. |
| Playwright browser errors | Rebuild the image from `Dockerfile.backend` (it bundles Chromium); do not install browsers manually. |
| `git clone` fails during deploys | GitHub access method/token invalid or expired. |
| Data lost after upgrade | `data/` bind mount incorrect — verify `-v /opt/testpilot/data:/data`. |

---

## 12. What is intentionally NOT required

No S3, PostgreSQL, Redis, ECS, EKS, Kubernetes, Lambda, RDS, ElastiCache or Kafka.
The initial deployment is simply **EC2 + Docker + SQLite + Bedrock**.
