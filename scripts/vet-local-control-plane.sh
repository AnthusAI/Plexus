#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PLEXUS_API_URL="${PLEXUS_API_URL:-http://localhost:18080/graphql}"
export PLEXUS_API_KEY="${PLEXUS_API_KEY:-local-smoke-key}"
export PLEXUS_PROXY_DATABASE_URL="${PLEXUS_PROXY_DATABASE_URL:-postgresql://plexus:plexus@localhost:55432/plexus_proxy}"
export SMOKE_DASHBOARD_URL="${SMOKE_DASHBOARD_URL:-http://localhost:3000}"
export SMOKE_PROOF_DIR="${SMOKE_PROOF_DIR:-$ROOT_DIR/tmp/local-control-plane-proof}"
export SMOKE_PRODUCTION_VETTING_PROOF_FILE="${SMOKE_PRODUCTION_VETTING_PROOF_FILE:-$SMOKE_PROOF_DIR/production-vetting.json}"

log() {
  printf '[vet-local-control-plane] %s\n' "$*"
}

ready_url="${PLEXUS_API_URL%/graphql}/readyz"
if ! curl -fsS "$ready_url" >/dev/null; then
  log "Local GraphQL proxy is not ready at $ready_url"
  exit 1
fi

mkdir -p "$(dirname "$SMOKE_PRODUCTION_VETTING_PROOF_FILE")"

(
  cd "$ROOT_DIR"
  poetry run python - <<'PY'
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

import psycopg
import requests


api_url = os.environ["PLEXUS_API_URL"]
api_key = os.environ["PLEXUS_API_KEY"]
database_url = os.environ["PLEXUS_PROXY_DATABASE_URL"]
dashboard_url = os.environ["SMOKE_DASHBOARD_URL"].rstrip("/")
proof_dir = Path(os.environ["SMOKE_PROOF_DIR"])
proof_file = Path(os.environ["SMOKE_PRODUCTION_VETTING_PROOF_FILE"])


checks: list[dict[str, Any]] = []


def add_check(
    *,
    area: str,
    status: str,
    severity: str,
    evidence: dict[str, Any],
    production_gap: str,
    next_required_work: str,
    kanbus: str,
) -> None:
    checks.append(
        {
            "area": area,
            "status": status,
            "severity": severity,
            "evidence": evidence,
            "productionGap": production_gap,
            "nextRequiredWork": next_required_work,
            "kanbus": kanbus,
        }
    )


def graphql(query: str, variables: dict[str, Any] | None = None, *, api_key_header: str | None = api_key) -> requests.Response:
    headers = {"content-type": "application/json"}
    if api_key_header is not None:
        headers["x-api-key"] = api_key_header
    return requests.post(
        api_url,
        headers=headers,
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )


def graphql_json(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    response = graphql(query, variables)
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    return body


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def plan_node_types(plan: Any) -> list[str]:
    types: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            node_type = node.get("Node Type")
            if isinstance(node_type, str):
                types.append(node_type)
            for child in node.values():
                if isinstance(child, list):
                    for item in child:
                        visit(item)
                elif isinstance(child, dict):
                    visit(child)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(plan)
    return types


def explain_query(conn: psycopg.Connection, name: str, query: str, params: tuple[Any, ...]) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("set local enable_seqscan = off")
        cur.execute("explain (format json) " + query, params)
        explain = cur.fetchone()[0]
    node_types = plan_node_types(explain)
    return {
        "name": name,
        "nodeTypes": node_types,
        "usesIndex": any("Index" in node_type or "Bitmap" in node_type for node_type in node_types),
        "plan": explain,
    }


def check_auth_and_tenancy() -> None:
    ready_response = requests.get(api_url.replace("/graphql", "/readyz"), timeout=10)
    ready_body = ready_response.json()
    auth_mode = ready_body.get("authMode")
    auth_mode_explicit = bool(ready_body.get("authModeExplicit"))
    upstream_disabled = bool(ready_body.get("upstreamDisabled"))
    external_access_required = bool(ready_body.get("externalAccessControlRequired"))

    unauthenticated = graphql("query VetUnauthenticated { listItems(limit: 1) { items { id } } }", api_key_header=None)

    create_mutation = """
    mutation VetCreateCrossAccountItem($input: CreateItemInput!) {
      createItem(input: $input) { id accountId text }
    }
    """
    graphql_json(
        create_mutation,
        {
            "input": {
                "id": "vet-cross-account-item",
                "accountId": "vet-other-account",
                "text": "Production vetting cross-account visibility probe.",
            }
        },
    )

    read_body = graphql_json(
        """
        query VetCrossAccountRead($id: ID!) {
          getItem(id: $id) { id accountId text }
        }
        """,
        {"id": "vet-cross-account-item"},
    )
    item = read_body["data"]["getItem"]

    if auth_mode == "trusted_open":
        declared_and_guarded = (
            auth_mode_explicit
            and upstream_disabled
            and external_access_required
            and unauthenticated.status_code == 200
        )
        add_check(
            area="auth_tenancy",
            status="pass" if declared_and_guarded else "risk",
            severity="medium" if declared_and_guarded else "high",
            evidence={
                "authMode": auth_mode,
                "authModeExplicit": auth_mode_explicit,
                "externalAccessControlRequired": external_access_required,
                "upstreamDisabled": upstream_disabled,
                "unauthenticatedStatus": unauthenticated.status_code,
                "trustedOpenCanReadAccountId": item.get("accountId"),
            },
            production_gap=(
                "Trusted-open mode intentionally performs no Plexus authentication or account authorization; "
                "deployment security depends on external access control."
            ),
            next_required_work="Document and verify the external access boundary for any trusted-open deployment; use OIDC/service-token auth for public or multi-tenant exposure.",
            kanbus="plx-b80481",
        )
        return

    if auth_mode != "api_key":
        add_check(
            area="auth_tenancy",
            status="risk",
            severity="high",
            evidence={
                "authMode": auth_mode,
                "authModeExplicit": auth_mode_explicit,
                "unauthenticatedStatus": unauthenticated.status_code,
                "sharedCredentialCanReadAccountId": item.get("accountId"),
            },
            production_gap="The local facade is running with an ambiguous or unrecognized auth mode.",
            next_required_work="Set PLEXUS_PROXY_AUTH_MODE explicitly to trusted_open or api_key.",
            kanbus="plx-b80481",
        )
        return

    add_check(
        area="auth_tenancy",
        status="risk",
        severity="high",
        evidence={
            "authMode": auth_mode,
            "authModeExplicit": auth_mode_explicit,
            "unauthenticatedStatus": unauthenticated.status_code,
            "sharedApiKeyCanReadAccountId": item.get("accountId"),
        },
        production_gap="API-key mode provides a shared-secret boundary but no principal-derived account isolation.",
        next_required_work="Use trusted_open only behind an external perimeter, or add OIDC/service-token authentication and account scoping for public or multi-tenant deployments.",
        kanbus="plx-b80481",
    )


def check_migration_readiness() -> None:
    ready_response = requests.get(api_url.replace("/graphql", "/readyz"), timeout=10)
    ready_body = ready_response.json()
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  to_regclass('local_data.schema_contract_versions') as local_contract_versions,
                  to_regclass('schema_contract_versions') as root_contract_versions,
                  to_regclass('schema_migrations') as schema_migrations
                """
            )
            row = cur.fetchone()

    add_check(
        area="migration_readiness",
        status="risk",
        severity="high",
        evidence={
            "readyzStatus": ready_response.status_code,
            "readyzBody": ready_body,
            "schemaVersionTables": {
                "localDataSchemaContractVersions": row[0],
                "rootSchemaContractVersions": row[1],
                "schemaMigrations": row[2],
            },
        },
        production_gap="/readyz proves database reachability but does not prove schema-contract version compatibility.",
        next_required_work="Add committed migrations plus schema contract version recording and readiness downgrade protection.",
        kanbus="plx-037698",
    )


def check_storage_vector_boundaries() -> None:
    report_proof = read_json(proof_dir / "report.json")
    vector_proof = read_json(proof_dir / "vector-topic-memory.json")
    upstream_response = requests.get(api_url.replace("/graphql", "/debug/upstream-requests"), timeout=10)
    upstream_requests = upstream_response.json()

    evidence = {
        "reportOutputAttachment": (report_proof or {}).get("outputAttachment"),
        "vectorStoreProvider": (vector_proof or {}).get("vectorStoreProvider"),
        "vectorTopicCount": (vector_proof or {}).get("topicCount"),
        "upstreamRequestCount": len(upstream_requests),
    }
    passed = (
        bool(evidence["reportOutputAttachment"])
        and evidence["vectorStoreProvider"] == "qdrant"
        and int(evidence["vectorTopicCount"] or 0) > 0
        and evidence["upstreamRequestCount"] == 0
    )

    add_check(
        area="storage_vector_boundaries",
        status="pass" if passed else "blocked",
        severity="medium" if passed else "high",
        evidence=evidence,
        production_gap="MinIO and Qdrant local boundaries are proven for report/vector smoke, but broader attachment surfaces still need audit coverage.",
        next_required_work="Complete ordinary attachment surface audit and add non-report attachment smoke coverage.",
        kanbus="plx-b8701d",
    )


def check_realtime_strategy() -> None:
    subscription_response = graphql(
        """
        subscription VetRealtime {
          onUpdateTask { id accountId status }
        }
        """
    )
    browser_screenshots = sorted(
        str(path.name)
        for path in (Path(os.environ["SMOKE_PROOF_DIR"]).parent / "local-control-plane-browser-smoke").glob("*.png")
    )
    dashboard_reachable = False
    try:
        urllib.request.urlopen(f"{dashboard_url}/lab/feedback", timeout=5)
        dashboard_reachable = True
    except (urllib.error.URLError, TimeoutError):
        dashboard_reachable = False

    add_check(
        area="realtime",
        status="risk",
        severity="medium",
        evidence={
            "httpSubscriptionStatus": subscription_response.status_code,
            "httpSubscriptionBody": subscription_response.text[:200],
            "dashboardReachable": dashboard_reachable,
            "browserSmokeScreenshots": browser_screenshots,
        },
        production_gap="Local dashboard compatibility uses no-op/polling-compatible behavior; the facade does not serve real websocket subscriptions.",
        next_required_work="Choose polling or graphql-transport-ws plus Postgres outbox/LISTEN-NOTIFY for the first production realtime path.",
        kanbus="plx-8d7ae8",
    )


def check_performance_query_shape() -> None:
    queries = [
        (
            "feedback_items_by_account_score_scorecard_edited",
            """
            select doc
            from local_data.feedback_item
            where doc ->> 'accountId' = %s
              and doc ->> 'scorecardId' = %s
              and doc ->> 'scoreId' = %s
            order by doc ->> 'editedAt' desc nulls last
            limit 50
            """,
            ("local-demo-account", "nira-demo-scorecard", "nira-demo-score"),
        ),
        (
            "score_results_by_item",
            """
            select doc
            from local_data.score_result
            where doc ->> 'itemId' = %s
            order by doc ->> 'updatedAt' desc nulls last
            limit 50
            """,
            ("nira-demo-item-1",),
        ),
        (
            "items_by_account_updated",
            """
            select doc
            from local_data.item
            where doc ->> 'accountId' = %s
            order by doc ->> 'updatedAt' desc nulls last
            limit 50
            """,
            ("local-demo-account",),
        ),
    ]

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  (select count(*) from local_data.feedback_item) as feedback_items,
                  (select count(*) from local_data.score_result) as score_results,
                  (select count(*) from local_data.item) as items
                """
            )
            counts = dict(zip(("feedbackItems", "scoreResults", "items"), cur.fetchone()))
        plans = [explain_query(conn, name, query, params) for name, query, params in queries]

    all_use_indexes = all(plan["usesIndex"] for plan in plans)
    add_check(
        area="performance_query_shape",
        status="pass" if all_use_indexes else "risk",
        severity="medium" if all_use_indexes else "high",
        evidence={
            "rowCounts": counts,
            "plans": [
                {
                    "name": plan["name"],
                    "usesIndex": plan["usesIndex"],
                    "nodeTypes": plan["nodeTypes"],
                }
                for plan in plans
            ],
        },
        production_gap="Current generic local list/index SQL filters JSON document fields; high-volume paths need reviewed generated columns/expression indexes.",
        next_required_work="Promote high-volume manifest index fields to indexed columns or expression indexes and re-run query plans under larger fixtures.",
        kanbus="plx-eab1b2",
    )


def check_observability_backup() -> None:
    add_check(
        area="observability_backup_restore",
        status="risk",
        severity="medium",
        evidence={
            "structuredMetrics": "not implemented in local facade",
            "databaseBackupRunbook": "not present",
            "minioBackupRunbook": "not present",
            "qdrantBackupRunbook": "not present",
        },
        production_gap="The MVP proof does not yet define operational metrics, alerts, backup, restore, or disaster recovery behavior.",
        next_required_work="Add production runbooks and smoke checks for backup/restore of PostgreSQL, MinIO, and Qdrant.",
        kanbus="plx-7039c2",
    )


for check in (
    check_auth_and_tenancy,
    check_migration_readiness,
    check_storage_vector_boundaries,
    check_realtime_strategy,
    check_performance_query_shape,
    check_observability_backup,
):
    try:
        check()
    except Exception as exc:
        add_check(
            area=check.__name__.removeprefix("check_"),
            status="blocked",
            severity="high",
            evidence={"error": str(exc)},
            production_gap="Vetting check could not complete.",
            next_required_work="Fix the vetting harness or local proof stack so this risk area can produce evidence.",
            kanbus="plx-e5297f",
        )


summary = {
    "pass": sum(1 for check in checks if check["status"] == "pass"),
    "risk": sum(1 for check in checks if check["status"] == "risk"),
    "blocked": sum(1 for check in checks if check["status"] == "blocked"),
}
payload = {
    "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "apiUrl": api_url,
    "summary": summary,
    "checks": checks,
}
proof_file.write_text(json.dumps(payload, indent=2, sort_keys=True))

print(f"Production vetting proof written to {proof_file}")
print(json.dumps(summary, sort_keys=True))
PY
)
