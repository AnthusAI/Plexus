#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHBOARD_DIR="$ROOT_DIR/dashboard"

log() {
  printf '[bootstrap-local-mvp] %s\n' "$*"
}

die() {
  printf '[bootstrap-local-mvp] ERROR: %s\n' "$*" >&2
  exit 1
}

ensure_brew() {
  if ! command -v brew >/dev/null 2>&1; then
    die "Homebrew is required. Install Homebrew first: https://brew.sh"
  fi
}

ensure_formula() {
  local formula="$1"
  if brew list --versions "$formula" >/dev/null 2>&1; then
    log "Homebrew formula already installed: $formula"
  else
    log "Installing Homebrew formula: $formula"
    brew install "$formula"
  fi
}

ensure_poetry() {
  if command -v poetry >/dev/null 2>&1; then
    log "Poetry already available: $(poetry --version)"
    return
  fi

  log "Poetry not found. Installing with Homebrew..."
  ensure_formula "poetry"
  command -v poetry >/dev/null 2>&1 || die "Poetry install completed but command is still unavailable."
  log "Poetry installed: $(poetry --version)"
}

ensure_docker_creds_helper() {
  local docker_config="$HOME/.docker/config.json"
  if [[ ! -f "$docker_config" ]]; then
    return
  fi

  if ! grep -q '"credsStore"[[:space:]]*:[[:space:]]*"desktop"' "$docker_config"; then
    return
  fi

  if command -v docker-credential-desktop >/dev/null 2>&1; then
    return
  fi

  log "Docker config uses credsStore=desktop but docker-credential-desktop is missing."
  ensure_formula "docker-credential-helper"

  if ! command -v docker-credential-osxkeychain >/dev/null 2>&1; then
    die "docker-credential-osxkeychain is unavailable after installing docker-credential-helper."
  fi

  cp "$docker_config" "$docker_config.codex-bak"
  perl -0pi -e 's/"credsStore"\s*:\s*"desktop"/"credsStore": "osxkeychain"/' "$docker_config"
  log "Updated ~/.docker/config.json credsStore from desktop to osxkeychain (backup: $docker_config.codex-bak)."
}

ensure_node20() {
  if command -v node >/dev/null 2>&1; then
    local major
    major="$(node -p 'process.versions.node.split(".")[0]')"
    if [[ "$major" == "20" ]]; then
      log "Node.js v20 already active: $(node -v)"
      return
    fi
  fi

  ensure_formula "node@20"
  export PATH="/opt/homebrew/opt/node@20/bin:$PATH"

  if ! command -v node >/dev/null 2>&1; then
    die "node command unavailable after installing node@20."
  fi

  local major
  major="$(node -p 'process.versions.node.split(".")[0]')"
  if [[ "$major" != "20" ]]; then
    die "Node major version is $major; expected 20. Ensure /opt/homebrew/opt/node@20/bin is first on PATH."
  fi

  log "Node.js v20 active: $(node -v)"
}

ensure_pg_tools() {
  if command -v psql >/dev/null 2>&1 && command -v pg_isready >/dev/null 2>&1; then
    log "PostgreSQL client tools already available."
    return
  fi

  ensure_formula "postgresql@16"
  export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"

  command -v psql >/dev/null 2>&1 || die "psql command unavailable after installing postgresql@16."
  command -v pg_isready >/dev/null 2>&1 || die "pg_isready command unavailable after installing postgresql@16."
  log "PostgreSQL client tools installed."
}

ensure_docker_ready() {
  command -v docker >/dev/null 2>&1 || die "Docker CLI is required but not found on PATH."
  if ! docker info >/dev/null 2>&1; then
    die "Docker daemon is not reachable. Start Docker Desktop, then rerun."
  fi
  log "Docker is available and daemon is reachable."
}

install_python_deps() {
  log "Installing Python dependencies via Poetry..."
  (
    cd "$ROOT_DIR"
    poetry install --no-interaction
  )
}

install_dashboard_deps() {
  log "Installing dashboard dependencies with npm ci..."
  (
    cd "$DASHBOARD_DIR"
    npm ci
  )
}

print_versions() {
  log "Dependency versions:"
  printf '  docker: %s\n' "$(docker --version)"
  printf '  poetry: %s\n' "$(poetry --version)"
  printf '  node:   %s\n' "$(node -v)"
  printf '  npm:    %s\n' "$(npm -v)"
  printf '  psql:   %s\n' "$(psql --version)"
  printf '  pg_isready: %s\n' "$(pg_isready --version)"
}

main() {
  ensure_brew
  ensure_docker_ready
  ensure_docker_creds_helper
  ensure_node20
  ensure_pg_tools
  ensure_poetry
  install_python_deps
  install_dashboard_deps
  print_versions
  log "Bootstrap complete."
}

main "$@"
