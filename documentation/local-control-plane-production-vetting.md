# Local Control Plane Production Vetting

This document tracks production-readiness evidence for the local Plexus control-plane MVP. It is intentionally separate from the demo runbook: the demo proves the path works, while this register records what still needs to be made production-grade.

Run the evidence harness after the local proof stack:

```bash
bash scripts/prove-local-control-plane.sh
bash scripts/vet-local-control-plane.sh
```

The vetting harness writes `tmp/local-control-plane-proof/production-vetting.json`.

## Risk Register

| Area | Current evidence | Production gap | Severity | Next required work | Kanbus issue |
| --- | --- | --- | --- | --- | --- |
| Auth and tenancy | Local GraphQL requires the configured demo API key when present. The vetting harness proves that the same API key can read records across account IDs. | No principal-derived account isolation exists in the facade yet. | High | Add OIDC/service-token auth and enforce account access before resolver execution. | `plx-e0f180` |
| Migrations and readiness | `/readyz` verifies database reachability and schema contract load at startup. | No applied schema contract version is recorded, and readiness does not fail when DB schema is behind the service manifest. | High | Add committed migrations, schema contract version tracking, and readiness downgrade/upgrade gates. | `plx-037698` |
| Storage and vector boundaries | Local proof verifies MinIO report artifacts, Qdrant `VectorTopicMemory`, and no hosted GraphQL upstream forwarding. | Broader ordinary attachment paths still need audit and non-report smoke coverage. | Medium | Complete object-storage surface audit and add a non-report attachment smoke. | `plx-b8701d` |
| Realtime | Dashboard local mode can function with no-op/polling-compatible subscriptions in the current smoke. | The local facade does not serve real `graphql-transport-ws` subscriptions. | Medium | Decide polling versus websocket subscriptions backed by PostgreSQL outbox/LISTEN-NOTIFY. | `plx-8d7ae8` |
| Performance and query shape | Vetting captures `EXPLAIN` output for representative `FeedbackItem`, `ScoreResult`, and `Item` access paths. | Generic local queries filter `doc jsonb` fields; high-volume paths need reviewed columns or expression indexes. | High | Promote manifest index fields for high-volume models into indexed columns/expression indexes and test with larger fixtures. | `plx-eab1b2` |
| Observability and backup | Local proof has deterministic smoke scripts and proof artifacts. | Production metrics, alerts, backup, restore, and DR runbooks are not defined. | Medium | Add operational runbooks and executable backup/restore checks for PostgreSQL, MinIO, and Qdrant. | `plx-7039c2` |

## Current Interpretation

The MVP is credible as an architectural proof: the dashboard, CLI, prediction, feedback evaluation, report artifacts, and local vector memory can run against controlled local services. It is not production-ready. The highest-risk blockers are auth/tenancy enforcement, schema migration discipline, and high-volume query shape.
