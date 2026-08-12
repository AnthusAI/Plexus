#!/usr/bin/env bash
# Verify the command-service dependency closure before attempting an image build.
# This deliberately uses a fresh environment rather than the developer's broad
# test environment, then imports every enabled parser through the worker smoke.
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
audit_python="${PYTHON:-python3}"

if ! "$audit_python" -c 'import sys; raise SystemExit(not ((3, 11) <= sys.version_info[:2] < (3, 13)))'; then
  echo "error: command-service runtime audit requires Python >=3.11,<3.13; $audit_python is $($audit_python --version 2>&1)." >&2
  exit 1
fi

audit_dir="$(mktemp -d "${TMPDIR:-/tmp}/plexus-command-runtime-audit.XXXXXX")"
trap 'rm -rf "$audit_dir"' EXIT

"$audit_python" -m venv "$audit_dir"
"$audit_dir/bin/python" -m pip install --upgrade pip poetry-core
"$audit_dir/bin/pip" install --no-build-isolation "$root_dir[command-service-runtime]"

# Run outside the repository so imports come from the installed distribution.
cd "$audit_dir"
"$audit_dir/bin/python" -m plexus.command_worker.smoke
# Kombu's asynchronous SQS transport requires pycurl when it creates its HTTP
# client, so exercise that exact runtime path in the clean environment.
"$audit_dir/bin/python" -c 'from kombu.asynchronous.http.curl import CurlClient; CurlClient()'
