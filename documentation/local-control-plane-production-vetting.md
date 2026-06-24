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
| Auth and tenancy | Local GraphQL now exposes explicit security modes. `trusted_open` is intentionally fully open and requires external access control; `api_key` preserves the shared-secret compatibility boundary. | Neither local mode provides principal-derived account isolation inside Plexus. Public or multi-tenant deployments still need OIDC/service-token auth plus resolver account scoping. | High | Use `trusted_open` only behind a documented external perimeter; add OIDC/service-token auth and account scoping for public or multi-tenant deployments. | `plx-b80481` |
| Migrations and readiness | `/readyz` verifies database reachability and schema contract load at startup. | No applied schema contract version is recorded, and readiness does not fail when DB schema is behind the service manifest. | High | Add committed migrations, schema contract version tracking, and readiness downgrade/upgrade gates. | `plx-037698` |
| Storage and vector boundaries | Local proof verifies MinIO report artifacts, Qdrant `VectorTopicMemory`, and no hosted GraphQL upstream forwarding. | Broader ordinary attachment paths still need audit and non-report smoke coverage. | Medium | Complete object-storage surface audit and add a non-report attachment smoke. | `plx-b8701d` |
| Realtime | Dashboard local mode can function with no-op/polling-compatible subscriptions in the current smoke. | The local facade does not serve real `graphql-transport-ws` subscriptions. | Medium | Decide polling versus websocket subscriptions backed by PostgreSQL outbox/LISTEN-NOTIFY. | `plx-8d7ae8` |
| Performance and query shape | Vetting captures `EXPLAIN` output for representative `FeedbackItem`, `ScoreResult`, and `Item` access paths. | Generic local queries filter `doc jsonb` fields; high-volume paths need reviewed columns or expression indexes. | High | Promote manifest index fields for high-volume models into indexed columns/expression indexes and test with larger fixtures. | `plx-eab1b2` |
| Observability and backup | Local proof has deterministic smoke scripts and proof artifacts. | Production metrics, alerts, backup, restore, and DR runbooks are not defined. | Medium | Add operational runbooks and executable backup/restore checks for PostgreSQL, MinIO, and Qdrant. | `plx-7039c2` |

## Current Interpretation

The MVP is credible as an architectural proof: the dashboard, CLI, prediction, feedback evaluation, report artifacts, and local vector memory can run against controlled local services. It is not production-ready for public or multi-tenant exposure. The highest-risk blockers are explicit deployment security posture, schema migration discipline, and high-volume query shape.

## Local Security Modes

| Mode | Behavior | Acceptable use | Not acceptable for |
| --- | --- | --- | --- |
| `trusted_open` | No Plexus authentication or account authorization. Any caller that can reach the GraphQL port can access local records. Requires `PLEXUS_BACKEND_MODE=local` and `PLEXUS_PROXY_UPSTREAM_DISABLED=true`. | Single-tenant local/K8s deployments protected by cluster networking, ingress policy, VPN, firewall, or another external perimeter. | Public endpoints, shared environments without network isolation, or multi-tenant deployments. |
| `api_key` | Requires `x-api-key` matching `PLEXUS_PROXY_API_KEY`. This is a shared-secret access boundary only. | Compatibility with existing local dashboard, CLI, worker, and smoke paths. | Claims of user identity, per-account authorization, or multi-tenant isolation. |

If `PLEXUS_PROXY_AUTH_MODE` is unset, the proxy infers `api_key` when `PLEXUS_PROXY_API_KEY` is set and `trusted_open` otherwise. Production-like deployments should set `PLEXUS_PROXY_AUTH_MODE` explicitly.
