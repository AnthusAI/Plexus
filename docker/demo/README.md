# Plexus Kubernetes Demo Acceptance Suite

This suite is the canonical, executable demonstration of Plexus on Docker
Desktop Kubernetes. It verifies the platform by running real product paths:
score configuration, synchronous prediction, feedback and regression
evaluations, OpenAI RCA, persisted reports, guarded prompt optimization,
champion promotion, restart recovery, and Helm reconciliation.

It is deliberately a test suite. Every phase has assertions, a nonzero failure
exit, and machine-readable evidence. It never treats a log message or a
synthetic metric as proof that a product feature worked.

## Canonical strict run

From the repository root:

```bash
poetry run python -m docker.demo.runner run \
  --deploy \
  --promote \
  --profile strict \
  --max-cost-usd 10 \
  --max-iterations 2
```

`--deploy` exports committed `HEAD` into a temporary directory, builds native
worker and proxy images from that snapshot, installs pinned Envoy Gateway
`1.8.1`, packages the snapshot Helm chart outside the checkout, and installs or
upgrades `plexus` in `plexus-local`. Dirty worktree files are never copied into
the images. The temporary source tree is deleted after deployment.

The OpenAI key is read from the existing `plexus-local-llm-keys` Secret. If the
Secret does not exist, the runner loads the approved local Plexus configuration
and creates the Secret through stdin. The key is never written to Helm values,
the command log, or result artifacts.

The local GraphQL proxy runs in explicit API-key mode and authorizes procedure,
task, optimizer, dataset, evaluation, and score-result artifact transfers with
short-lived signed HTTPS tickets. The deployer creates one reusable local CA and
MinIO TLS Secret if it is absent; subsequent upgrades reuse that Secret. Workers
mount only the CA for ticket transfers. MinIO signing credentials are held in
Kubernetes Secrets and injected into the proxy. Worker MinIO credentials remain
temporarily available only because evaluation/report consumers are outside PR
#513's migration scope; the suite does not claim fully credential-free storage.

Prerequisites:

- Docker Desktop Kubernetes is enabled and the active context is
  `docker-desktop`.
- Docker, `kubectl`, Helm, Poetry, and Python 3.11 are available.
- The configured OpenAI project can use `gpt-5.4-nano`.
- The machine can reach Docker Hub, Bitnami, Hugging Face, GitHub, and OpenAI.

Run without `--deploy` only when intentionally validating an already-running
release. The complete recovery test requires the immutable Helm package created
by `--deploy`.

## Public benchmark

The suite uses BANKING77 (`CC-BY-4.0`) and records both levels of source
pinning:

- Hugging Face definition revision:
  `90d4e2ee5521c04fc1488f065b8b083658768c57`
- Underlying source-data commit:
  `9d081458ff52e53cf7e848f414e6e9344e4e6696`
- `train.csv` SHA-256:
  `b06e26ac675513959a63135f11b94ea7786ed02da65db93a5650d8838cbc664b`

The Hugging Face loader definition points to an unpinned GitHub `master` URL,
so pinning only the Hugging Face revision is insufficient. The runner downloads
the CSV at the immutable source commit and refuses a checksum mismatch.

BANKING77 does not contain a class named `cash_withdrawal`. The executable
fixture uses the actual class names:

| Source class | Count | Plexus label |
| --- | ---: | --- |
| `declined_cash_withdrawal` | 100 | `Yes` |
| `cash_withdrawal_charge` | 50 | `No` |
| `cash_withdrawal_not_recognised` | 50 | `No` |

Each source class is split deterministically in half. The result is one balanced
100-item feedback set and one disjoint balanced 100-item regression set. Only
revision, row index, label mapping, counts, and checksums enter artifacts; raw
queries and previews do not.

The initial GPT-5.4-nano rubric handles declined withdrawals and withdrawal
fees but intentionally omits the unrecognized-withdrawal boundary. This creates
a realistic prompt defect for RCA and hill-climbing to discover.

The optimizer's `num_candidates` parameter caps normal rubric lanes while its
structural lane is additive. The suite requests one normal lane, yielding the
required two candidates per cycle (one rubric and one protected structural
candidate) within the two-iteration ceiling.

## Pass contract

The strict profile requires:

- ready node, DNS, default storage, Envoy `1.8.1`, healthy deployments, accepted
  Gateway/HTTPRoute, and Bound PVCs;
- exactly 100 completed feedback predictions and 100 completed regression
  predictions, with zero execution errors;
- baseline accuracy between `0.55` and `0.85`;
- an optimizer candidate that improves feedback AC1 by at least `0.05` while
  regression AC1 declines by no more than `0.02`;
- promotion only after those thresholds pass, followed by a fresh 100-item
  evaluation reproducing the improvement;
- report outputs linked to the run-scoped score;
- successful worker/proxy restart, persisted PostgreSQL data, readiness, and an
  identical upgrade from the packaged snapshot chart.

The optional `guardrail` profile passes when a candidate improves safely or
when all worse candidates are correctly rejected. It never reports a strict
optimization success.

There are no automatic optimizer retries, label substitutions, or fallback
results. Provider, dataset, evaluation, RCA, reporting, budget, and procedure
failures remain failures.

## Repeatability and retained runs

The default run ID is UTC plus random entropy, for example
`20260723T163000Z-a1b2c3`. Every scorecard, score, version, item, and feedback
record uses that run scope. Generated evaluations, datasets, reports, tasks, and
procedures are linked to the run-scoped score.

```bash
# Continue the first incomplete phase.
poetry run python -m docker.demo.runner resume \
  --run-id 20260723T163000Z-a1b2c3 \
  --output-dir /tmp/plexus-k8s-demo/20260723T163000Z-a1b2c3 \
  --promote

# Verify persisted state without creating application records.
poetry run python -m docker.demo.runner verify \
  --run-id 20260723T163000Z-a1b2c3 \
  --output-dir /tmp/plexus-k8s-demo/20260723T163000Z-a1b2c3

# Explicitly remove only records owned by this exact run.
poetry run python -m docker.demo.runner cleanup \
  --run-id 20260723T163000Z-a1b2c3 \
  --output-dir /tmp/plexus-k8s-demo/20260723T163000Z-a1b2c3 \
  --confirm
```

Re-running `run` with an existing incomplete run resumes it. Re-running a fully
completed run performs read-only verification. Conflicting existing records or
an invalid run ID fail rather than being overwritten.

If the optimizer product procedure completed but the harness process failed
while consuming its result, `resume` verifies the single run-scoped procedure
and task attachment, reads only the sanitized decision/metric/cost fields, and
continues with guarded promotion. It refuses to rerun an incomplete optimizer;
starting another optimization always requires a new run ID.

The acceptance-only interruption hook proves this path deterministically:

```bash
RUN_ID=20260728T200000Z-resume
poetry run python -m docker.demo.runner run \
  --run-id "$RUN_ID" --deploy --promote --profile strict \
  --max-cost-usd 10 --max-iterations 2 --interrupt-after-optimizer

# The first command is expected to fail immediately after the optimizer task
# and its output artifact complete. Resume consumes that artifact through a
# GraphQL ticket and asserts the optimizer dispatch count remains exactly one.
poetry run python -m docker.demo.runner resume \
  --run-id "$RUN_ID" --output-dir "/tmp/plexus-k8s-demo/$RUN_ID" --promote
```

## Evidence

Artifacts default to `/tmp/plexus-k8s-demo/<run-id>/`:

- `junit.xml` — pytest phase results for CI and test viewers
- `results.json` — aggregate pass/fail result
- `report.md` — human-readable phase and metric summary
- `manifest.json` — run identity, resource ownership, checkpoints, and safe IDs
- `events.jsonl` — command, exit status, and elapsed time without command output
- `plexus-stack-1.0.0.tgz` — immutable chart used for deployment and the repeat
  Helm upgrade
- `values-local.yaml` — sanitized, exact non-secret values used for both Helm
  operations

Artifacts may contain resource IDs, aggregate metrics, counts, version IDs,
candidate decisions, costs, token totals, checksums, and safe error summaries.
They must not contain API keys, raw BANKING77 rows, transcript text, evidence
quotes, or raw report/log payloads.

Elapsed time and spend are measured per phase in the result artifacts. The
parent optimizer LLM budget defaults to `$10`; evaluations additionally expose
their persisted costs. The first fully green strict run should be used as the
published duration/cost baseline for the current hardware and model snapshot.

## Measured local baseline

Two retained strict runs passed on 2026-07-23 using Docker Desktop with 8 GB of
memory and GPT-5.4-nano. One exercised artifact-aware resume after the product
optimizer had completed; the other passed all seven phases directly in one
command. Read-only verification of the first still passed after the second run.

| Measurement | Observed range |
| --- | ---: |
| Complete direct strict run | 23m 09s |
| Paired baseline evaluations | 4m 13s–8m 57s |
| Reporting | 6m 24s–8m 04s |
| Optimizer plus final verification | 10m 24s–11m 10s |
| Restart and Helm recovery | 54s |
| Baseline accuracy | 78%–79% |
| Optimizer cost ledger | $0.04155–$0.04362 |

The optimizer ledger currently counts the supplied paired baseline evaluations
as incurred entries even though the suite created them before the optimizer.
The separately persisted paired-baseline cost was `$0.01034–$0.01047`; do not
add it to the optimizer ledger when estimating total spend. Correct reused-cost
attribution remains a follow-up rough edge.
