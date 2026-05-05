#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."
docker compose -f docker-compose.smoke.yml up --build --abort-on-container-exit --exit-code-from smoke-tests smoke-tests
