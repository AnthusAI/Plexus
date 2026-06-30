#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$DASHBOARD_DIR/.." && pwd)"

cd "$DASHBOARD_DIR"

set -a
[ -f ../.env ] && . ../.env
[ -f ./.env.local ] && . ./.env.local
set +a

if ! command -v poetry >/dev/null 2>&1; then
  echo "Missing poetry for dashboard dev env fallback (.plexus/config.yaml)." >&2
  exit 1
fi

if ! EXPORT_LINES="$(
  cd "$REPO_ROOT" && poetry run python - <<'PY'
import os
import shlex
import sys

from plexus.config.loader import ConfigLoader, load_config

try:
    load_config()
except Exception as exc:
    print(f"Failed to load .plexus/config.yaml via load_config(): {exc}", file=sys.stderr)
    raise

env = os.environ

def pick(primary: str, fallback: str | None = None) -> str:
    value = env.get(primary)
    if value:
        return value
    if fallback:
        return env.get(fallback, "")
    return ""

values = {
    env_var: env.get(env_var, "")
    for env_var in sorted(set(ConfigLoader.ENV_VAR_MAPPING.values()))
    if not env_var.startswith("_")
}

values.update({
    "NEXT_PUBLIC_PLEXUS_API_URL": pick("NEXT_PUBLIC_PLEXUS_API_URL", "PLEXUS_API_URL"),
    "NEXT_PUBLIC_PLEXUS_API_KEY": pick("NEXT_PUBLIC_PLEXUS_API_KEY", "PLEXUS_API_KEY"),
    "NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY": pick("NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY", "PLEXUS_ACCOUNT_KEY"),
    "NEXT_PUBLIC_PLEXUS_API_REGION": pick("NEXT_PUBLIC_PLEXUS_API_REGION", "PLEXUS_API_REGION"),
    "NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET": pick("NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET", "CONSOLE_RESPONSE_TARGET"),
    "CONSOLE_RESPONSE_TARGET": pick("CONSOLE_RESPONSE_TARGET", "NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET"),
})

for key, value in values.items():
    if value:
        print(f"export {key}={shlex.quote(value)}")
PY
)"; then
  echo "Failed to hydrate dashboard dev env from .plexus/config.yaml via poetry run python." >&2
  exit 1
fi

printf '%s\n' "$EXPORT_LINES"
