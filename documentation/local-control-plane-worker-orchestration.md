# Local Worker Orchestration Runbook

This runbook proves local worker execution paths against the local control plane without Lambda dispatch.

## What this replaces in local mode

- `TaskDispatcher` Lambda -> `plexus command dispatcher` in `PLEXUS_DISPATCH_MODE=local`
- `ConsoleRunWorker` Lambda -> `plexus chat worker --response-target local:<name>`

This is a local/K8s execution model with polling workers. AWS mode remains unchanged.

## Required environment

Use the same local control-plane baseline from the MVP runbook:

- `PLEXUS_BACKEND_MODE=local`
- `PLEXUS_PROXY_UPSTREAM_DISABLED=true`
- `PLEXUS_API_URL=http://localhost:18080/graphql`
- `PLEXUS_API_KEY=local-smoke-key`
- `PLEXUS_ACCOUNT_KEY=local-demo`

For chat worker smoke:

- `SMOKE_CHAT_RESPONSE_TARGET=local:smoke-worker` (default in script)

## Worker smoke commands

Run from repo root:

```bash
cd /Users/ryan.porter/Projects/Plexus-codex-control-plane
bash scripts/smoke-local-task-dispatch.sh
bash scripts/smoke-local-chat-worker.sh
```

What each smoke verifies:

- `smoke-local-task-dispatch.sh`
  - Creates a pending `Task` in local GraphQL.
  - Runs `plexus command dispatcher --once` in local mode.
  - Verifies the task transitions to `COMPLETED` with `dispatchStatus=DISPATCHED`.
  - Verifies local dispatch metadata and non-empty command stdout.
  - Asserts `/debug/upstream-requests` is empty.

- `smoke-local-chat-worker.sh`
  - Creates a `ChatSession` and pending `ChatMessage` with local response target.
  - Runs `plexus chat worker --once` for that target.
  - Verifies the trigger message reaches `responseStatus=COMPLETED`.
  - Verifies assistant reply persistence in the same session.
  - Uses deterministic prompt content (`multiply 7 by 6`) to keep smoke stable.
  - Disables auto-title generation for smoke (`CONSOLE_AUTO_TITLE_ENABLED=false`) so no external model key is required.
  - Asserts `/debug/upstream-requests` is empty.

## One-command worker proof

Run:

```bash
cd /Users/ryan.porter/Projects/Plexus-codex-control-plane
bash scripts/prove-local-worker-orchestration.sh
```

The proof writes:

- `tmp/local-control-plane-proof/task-dispatch.json`
- `tmp/local-control-plane-proof/chat-worker.json`
- `tmp/local-control-plane-proof/worker-orchestration.json`

To include full stack proof before worker checks:

```bash
WORKER_PROOF_RUN_BASE=1 bash scripts/prove-local-worker-orchestration.sh
```

## K8s deployment mapping

The local smoke commands map directly to long-running workers in Kubernetes:

- Dispatcher deployment command:
  - `python -m plexus.cli command dispatcher --interval 1 --limit 25 --account local-demo`
- Chat worker deployment command:
  - `python -m plexus.cli chat worker --response-target local:smoke-worker --limit 5`

Use one replica each for MVP. Scale after task/chat queue behavior is observed.

## Troubleshooting

- `Local dispatcher requires account context`:
  - Set `PLEXUS_ACCOUNT_KEY` or pass `--account`.

- Chat worker exits with local-target error:
  - Ensure `CONSOLE_RESPONSE_TARGET` or `--response-target` is `local:<name>`, not `cloud`.

- Smoke reports upstream requests:
  - Confirm proxy is running with `PLEXUS_PROXY_UPSTREAM_DISABLED=true`.

- Chat smoke does not find assistant response:
  - Re-run with clean seed stack and default deterministic prompt.
  - Check `/tmp/plexus-smoke-chat-worker.out` for worker-side errors.
