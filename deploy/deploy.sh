#!/usr/bin/env bash
#
# TestPilot AI — repeatable backend deployment script (EC2 / any Docker host).
#
# Conceptually:
#   pull latest code -> build image -> stop/remove old container ->
#   start new container (with persistent volumes) -> verify health endpoint
#
# Usage:
#   ./deploy/deploy.sh
#
# Configuration (override via environment or edit below):
#   APP_DIR       Absolute path to the checked-out repository (default: ., the repo root)
#   IMAGE_NAME    Docker image tag                (default: testpilot-backend:latest)
#   CONTAINER     Container name                  (default: testpilot-backend)
#   HOST_PORT     Host port mapped to 3001        (default: 3001)
#   DATA_DIR      Persistent host dir for SQLite  (default: /opt/testpilot/data)
#   ARTIFACTS_DIR Persistent host dir for artifacts (default: /opt/testpilot/artifacts)
#   REPOS_DIR     Persistent host dir for repos   (default: /opt/testpilot/repos)
#   ENV_FILE      Env file passed to the container (default: <repo>/.env)
#
# The script never hard-codes secrets: they are read from ENV_FILE / the host
# environment (e.g. an EC2 IAM instance role supplies AWS Bedrock credentials).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

IMAGE_NAME="${IMAGE_NAME:-testpilot-backend:latest}"
CONTAINER="${CONTAINER:-testpilot-backend}"
HOST_PORT="${HOST_PORT:-3001}"
DATA_DIR="${DATA_DIR:-/opt/testpilot/data}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-/opt/testpilot/artifacts}"
REPOS_DIR="${REPOS_DIR:-/opt/testpilot/repos}"
ENV_FILE="${ENV_FILE:-${APP_DIR}/.env}"
HEALTH_URL="${HEALTH_URL:-http://localhost:${HOST_PORT}/api/health}"

log() { printf '\n\033[1;34m[deploy]\033[0m %s\n' "$*"; }
fail() { printf '\n\033[1;31m[deploy:error]\033[0m %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "docker is not installed or not on PATH"
[ -f "${ENV_FILE}" ] || fail "env file not found: ${ENV_FILE} (copy .env.example to .env and fill it in)"

cd "${APP_DIR}"

# 1. Pull latest code (best-effort; skip gracefully on a non-git checkout).
if [ -d "${APP_DIR}/.git" ]; then
  log "Pulling latest code..."
  git pull --ff-only || log "git pull skipped (dirty tree or no upstream)"
fi

# 2. Ensure persistent host directories exist.
log "Ensuring persistent storage directories..."
mkdir -p "${DATA_DIR}" "${ARTIFACTS_DIR}" "${REPOS_DIR}"

# 3. Build the image.
log "Building image ${IMAGE_NAME}..."
docker build -f "${APP_DIR}/Dockerfile.backend" -t "${IMAGE_NAME}" "${APP_DIR}"

# 4. Stop and remove the previous container (volumes/data are preserved).
if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER}"; then
  log "Stopping and removing previous container ${CONTAINER}..."
  docker stop "${CONTAINER}" >/dev/null
  docker rm "${CONTAINER}" >/dev/null
fi

# 5. Start the new container with persistent bind mounts.
log "Starting container ${CONTAINER}..."
docker run -d \
  --name "${CONTAINER}" \
  --restart unless-stopped \
  --env-file "${ENV_FILE}" \
  -e "DATABASE_PATH=/data/testpilot.db" \
  -e "ARTIFACTS_DIR=/artifacts" \
  -e "REPOS_DIR=/repos" \
  -p "${HOST_PORT}:3001" \
  -v "${DATA_DIR}:/data" \
  -v "${ARTIFACTS_DIR}:/artifacts" \
  -v "${REPOS_DIR}:/repos" \
  "${IMAGE_NAME}"

# 6. Wait for the health endpoint.
log "Waiting for ${HEALTH_URL} ..."
for i in $(seq 1 30); do
  if curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
    log "Health check passed: $(curl -fsS "${HEALTH_URL}")"
    log "Deployment complete ✅"
    exit 0
  fi
  sleep 2
done

log "Health check did not pass in time. Recent container logs:"
docker logs --tail 50 "${CONTAINER}" || true
fail "deployment failed health verification"
