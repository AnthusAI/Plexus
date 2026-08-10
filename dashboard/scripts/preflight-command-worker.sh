#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_DIR"

python -m pytest tests/command_worker/test_task_gateway_contract.py -q
python -m pytest dashboard/amplify/functions/taskDispatcher/test_index.py -q
python -m pytest tests/command_worker -q

cd "$REPO_DIR/dashboard"
npm test -- --runInBand amplify/data/resolvers/submitCommand.test.ts
npm test -- --runInBand amplify/command-service/resource.test.ts
npm run typecheck:backend

