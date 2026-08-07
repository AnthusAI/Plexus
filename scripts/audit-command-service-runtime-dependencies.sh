#!/usr/bin/env bash
# Verify the command-service dependency closure before attempting an image build.
# This deliberately uses a fresh environment rather than the developer's broad
# test environment, then imports every enabled parser through the worker smoke.
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
audit_dir="$(mktemp -d "${TMPDIR:-/tmp}/plexus-command-runtime-audit.XXXXXX")"
trap 'rm -rf "$audit_dir"' EXIT

"${PYTHON:-python3}" -m venv "$audit_dir"
"$audit_dir/bin/python" -m pip install --upgrade pip poetry-core
"$audit_dir/bin/pip" install --no-build-isolation "$root_dir[command-service-runtime]"

# Run outside the repository so imports come from the installed distribution.
cd "$audit_dir"
"$audit_dir/bin/python" -m plexus.command_worker.smoke
