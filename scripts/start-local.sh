#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export DOCKER_CONFIG="${DOCKER_CONFIG:-$PWD/.runtime/docker}"
mkdir -p "$DOCKER_CONFIG"
python3 scripts/configure-local.py
python3 scripts/configure-cloud.py
if [ -f .runtime/compose.cloud.json ]; then
  export COMPOSE_FILE="compose.yaml:.runtime/compose.cloud.json"
fi
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 180
curl --fail --silent --show-error http://localhost:8080/healthz
curl --fail --silent --show-error http://localhost:8080/api/config
python3 scripts/readiness.py
