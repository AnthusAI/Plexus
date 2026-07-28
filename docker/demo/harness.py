from __future__ import annotations

import concurrent.futures
import csv
import hashlib
import json
import re
import socket
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import requests

from docker.demo.core import (
    AcceptanceMetrics,
    DemoManifest,
    HUGGING_FACE_DATASET,
    HUGGING_FACE_REVISION,
    PHASES,
    SOURCE_SHA256,
    SOURCE_URL,
    acceptance_outcome,
    assert_cleanup_scope,
    benchmark_rows,
    redact_text,
    render_artifacts,
    stable_resource_id,
    utc_now,
)


NAMESPACE = "plexus-local"
RELEASE = "plexus"
WORKER_DEPLOYMENT = "plexus-plexus-worker"
PROXY_DEPLOYMENT = "plexus-graphql-proxy"
WORKER_SERVICE = "plexus-plexus-worker"
PROXY_SERVICE = "plexus-graphql-proxy"
OBJECT_STORE_DEPLOYMENT = "plexus-local-object-store"
OBJECT_STORE_SERVICE = "plexus-local-object-store"
OPENAI_SECRET = "plexus-local-llm-keys"
PROXY_API_KEY = "local-dev-key"
OBJECT_STORE_TLS_SECRET = "plexus-local-object-store-tls"
ACCOUNT_ID = "local-demo-account"
ACCOUNT_KEY = "local-demo"
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class DemoFailure(RuntimeError):
    """A privacy-safe demo assertion or command failure."""


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    elapsed_seconds: float


class CommandRunner:
    def __init__(self, event_log: Path, secrets: Sequence[str] = ()):
        self.event_log = event_log
        self.secrets = tuple(secret for secret in secrets if secret)
        event_log.parent.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: int = 300,
        check: bool = True,
        input_text: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        started = time.monotonic()
        safe_command = redact_text(" ".join(argv), self.secrets)
        try:
            completed = subprocess.run(
                list(argv),
                input=input_text,
                text=True,
                capture_output=True,
                timeout=timeout,
                env=dict(env) if env is not None else None,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - started
            safe_event = {
                "at": utc_now(),
                "command": safe_command,
                "returncode": None,
                "elapsed_seconds": round(elapsed, 3),
                "timed_out": True,
                "timeout_seconds": timeout,
            }
            with self.event_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(safe_event, sort_keys=True) + "\n")
            raise DemoFailure(f"command timed out after {timeout}s: {safe_command}") from exc
        elapsed = time.monotonic() - started
        result = CommandResult(
            argv=tuple(argv),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            elapsed_seconds=elapsed,
        )
        safe_event = {
            "at": utc_now(),
            "command": safe_command,
            "returncode": completed.returncode,
            "elapsed_seconds": round(elapsed, 3),
        }
        with self.event_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe_event, sort_keys=True) + "\n")
        if check and completed.returncode != 0:
            details = redact_text(
                ("stdout:\n" + completed.stdout[-1500:] + "\nstderr:\n" + completed.stderr[-1500:]),
                self.secrets,
            )
            raise DemoFailure(f"command failed ({completed.returncode}): {safe_command}\n{details}")
        return result


class GraphQLClient:
    def __init__(self, endpoint: str, api_key: str | None = None):
        self.endpoint = endpoint
        self.session = requests.Session()
        self.api_key = api_key

    def execute(self, query: str, variables: Mapping[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.post(
            self.endpoint,
            json={"query": query, "variables": dict(variables or {})},
            headers={"x-api-key": self.api_key} if self.api_key else {},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            safe_errors = [
                {"message": error.get("message"), "path": error.get("path")}
                for error in payload["errors"]
            ]
            raise DemoFailure(f"GraphQL operation failed: {json.dumps(safe_errors)}")
        return payload.get("data") or {}


@dataclass
class DemoHarness:
    manifest: DemoManifest
    output_dir: Path
    promote: bool = False
    resume: bool = False
    interrupt_after_optimizer: bool = False

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.output_dir / "manifest.json"
        self.runner = CommandRunner(self.output_dir / "events.jsonl")

    @property
    def ids(self) -> dict[str, str]:
        run_id = self.manifest.run_id
        return {
            "scorecard": stable_resource_id(run_id, "scorecard"),
            "section": stable_resource_id(run_id, "section"),
            "score": stable_resource_id(run_id, "score"),
            "version": stable_resource_id(run_id, "baseline-version"),
        }

    def run_all(self) -> None:
        phase_methods = {
            "infrastructure": self.infrastructure,
            "seed": self.seed,
            "prediction": self.prediction,
            "evaluation": self.evaluation,
            "reporting": self.reporting,
            "optimization": self.optimization,
            "recovery": self.recovery,
        }
        for phase in PHASES:
            if self.resume and self.manifest.completed(phase):
                continue
            try:
                summary = phase_methods[phase]()
                self.manifest.record_phase(phase, passed=True, summary=summary)
            except Exception as exc:
                self.manifest.record_phase(phase, passed=False, error=str(exc))
                self._persist()
                raise
            self._persist()

    def _persist(self) -> None:
        self.manifest.save(self.manifest_path)
        render_artifacts(self.manifest, self.output_dir)

    def infrastructure(self) -> dict[str, Any]:
        context = self.runner.run(("kubectl", "config", "current-context")).stdout.strip()
        if context != "docker-desktop":
            raise DemoFailure(f"expected kubectl context docker-desktop, got {context!r}")

        nodes = self._json_command(("kubectl", "get", "nodes", "-o", "json"))
        ready_nodes = [
            item
            for item in nodes.get("items", [])
            if _condition_true(item, "Ready")
        ]
        if not ready_nodes:
            raise DemoFailure("Docker Desktop Kubernetes has no Ready node")

        storage = self._json_command(("kubectl", "get", "storageclass", "-o", "json"))
        default_storage = [
            item["metadata"]["name"]
            for item in storage.get("items", [])
            if item.get("metadata", {}).get("annotations", {}).get(
                "storageclass.kubernetes.io/is-default-class"
            )
            == "true"
        ]
        if not default_storage:
            raise DemoFailure("cluster has no default StorageClass")

        helm = self.runner.run(("helm", "status", RELEASE, "-n", NAMESPACE, "-o", "json"))
        helm_status = json.loads(helm.stdout)
        if helm_status.get("info", {}).get("status") != "deployed":
            raise DemoFailure("plexus Helm release is not deployed")

        for deployment in (WORKER_DEPLOYMENT, PROXY_DEPLOYMENT, OBJECT_STORE_DEPLOYMENT):
            self.runner.run(
                (
                    "kubectl",
                    "rollout",
                    "status",
                    f"deployment/{deployment}",
                    "-n",
                    NAMESPACE,
                    "--timeout=180s",
                ),
                timeout=200,
            )

        pods = self._json_command(("kubectl", "get", "pods", "-n", NAMESPACE, "-o", "json"))
        required = {
            WORKER_DEPLOYMENT,
            PROXY_DEPLOYMENT,
            OBJECT_STORE_DEPLOYMENT,
            f"{RELEASE}-postgresql",
        }
        observed: set[str] = set()
        for pod in pods.get("items", []):
            name = pod.get("metadata", {}).get("name", "")
            if pod.get("status", {}).get("phase") == "Running" and _pod_ready(pod):
                for prefix in required:
                    if name.startswith(prefix):
                        observed.add(prefix)
        if observed != required:
            raise DemoFailure(f"required Ready pods missing: {sorted(required - observed)}")

        workload_refs = (
            ("deployment", WORKER_DEPLOYMENT),
            ("deployment", PROXY_DEPLOYMENT),
            ("deployment", OBJECT_STORE_DEPLOYMENT),
            ("statefulset", f"{RELEASE}-postgresql"),
        )
        for kind, name in workload_refs:
            workload = self._json_command(
                ("kubectl", "get", kind, name, "-n", NAMESPACE, "-o", "json")
            )
            containers = (
                workload.get("spec", {})
                .get("template", {})
                .get("spec", {})
                .get("containers", [])
            )
            if not containers or any(
                not container.get("livenessProbe") or not container.get("readinessProbe")
                for container in containers
            ):
                raise DemoFailure(f"{kind}/{name} is missing a liveness or readiness probe")

        pvcs = self._json_command(("kubectl", "get", "pvc", "-n", NAMESPACE, "-o", "json"))
        if not pvcs.get("items") or any(
            pvc.get("status", {}).get("phase") != "Bound" for pvc in pvcs["items"]
        ):
            raise DemoFailure("one or more Plexus PVCs are not Bound")

        gateways = self._json_command(
            ("kubectl", "get", "gateway,httproute", "-n", NAMESPACE, "-o", "json")
        )
        kinds = {item.get("kind") for item in gateways.get("items", [])}
        if not {"Gateway", "HTTPRoute"}.issubset(kinds):
            raise DemoFailure("Gateway or HTTPRoute is missing")
        for item in gateways.get("items", []):
            accepted = _condition_true(item, "Accepted") or _condition_true(item, "Programmed")
            if not accepted:
                raise DemoFailure(f"{item.get('kind')} is not accepted/programmed")

        envoy = self._json_command(
            ("kubectl", "get", "deployment", "-n", "envoy-gateway-system", "-o", "json")
        )
        envoy_images = [
            container.get("image", "")
            for item in envoy.get("items", [])
            for container in item.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        ]
        if not any("v1.8.1" in image or ":1.8.1" in image for image in envoy_images):
            raise DemoFailure("Envoy Gateway 1.8.1 deployment was not found")

        dns = self.runner.run(
            (
                "kubectl",
                "exec",
                "-n",
                NAMESPACE,
                f"deployment/{WORKER_DEPLOYMENT}",
                "--",
                "getent",
                "hosts",
                PROXY_SERVICE,
            )
        ).stdout.strip()
        if not dns:
            raise DemoFailure("worker could not resolve GraphQL proxy through cluster DNS")
        object_store_dns = self.runner.run(
            (
                "kubectl",
                "exec",
                "-n",
                NAMESPACE,
                f"deployment/{WORKER_DEPLOYMENT}",
                "--",
                "getent",
                "hosts",
                OBJECT_STORE_SERVICE,
            )
        ).stdout.strip()
        if not object_store_dns:
            raise DemoFailure("worker could not resolve the local object store through cluster DNS")

        bucket_job = self._json_command(
            (
                "kubectl",
                "get",
                "job",
                f"{OBJECT_STORE_DEPLOYMENT}-buckets",
                "-n",
                NAMESPACE,
                "-o",
                "json",
            )
        )
        if int(bucket_job.get("status", {}).get("succeeded") or 0) != 1:
            raise DemoFailure("local object-store bucket provisioning has not completed")

        return {
            "context": context,
            "ready_nodes": len(ready_nodes),
            "storage_class": default_storage[0],
            "helm_revision": helm_status.get("version"),
            "envoy_gateway": "1.8.1",
            "pvc_count": len(pvcs["items"]),
            "object_store": "ready",
            "probed_workloads": len(workload_refs),
        }

    def seed(self) -> dict[str, Any]:
        rows = load_banking77_rows()
        split = benchmark_rows(rows)
        ids = self.ids
        seed_anchor = self.manifest.metadata.get("seed_anchor")
        if not seed_anchor:
            seed_anchor = utc_now()
            self.manifest.metadata["seed_anchor"] = seed_anchor
        anchor = datetime.fromisoformat(seed_anchor.replace("Z", "+00:00"))

        with self.graphql() as client:
            account = client.execute(
                "query DemoAccount($id: ID!) { getAccount(id: $id) { id key } }",
                {"id": ACCOUNT_ID},
            ).get("getAccount")
            if not account or account.get("key") != ACCOUNT_KEY:
                raise DemoFailure("local-demo account is missing; seed_local_demo.py must run first")

            self._ensure_model(
                client,
                "Scorecard",
                {
                    "id": ids["scorecard"],
                    "name": f"K8s Demo {self.manifest.run_id}",
                    "key": ids["scorecard"],
                    "externalId": ids["scorecard"],
                    "description": "Run-scoped public BANKING77 optimization acceptance fixture.",
                    "guidelines": "Classify whether a request reports a declined cash withdrawal.",
                    "accountId": ACCOUNT_ID,
                    "createdAt": seed_anchor,
                    "updatedAt": seed_anchor,
                },
                "id key accountId",
                ("id", "key", "accountId"),
            )
            self._ensure_model(
                client,
                "ScorecardSection",
                {
                    "id": ids["section"],
                    "name": "Banking Intent Checks",
                    "order": 1,
                    "scorecardId": ids["scorecard"],
                    "createdAt": seed_anchor,
                    "updatedAt": seed_anchor,
                },
                "id scorecardId",
                ("id", "scorecardId"),
            )
            self._ensure_model(
                client,
                "Score",
                {
                    "id": ids["score"],
                    "name": "Declined Cash Withdrawal",
                    "key": ids["score"],
                    "externalId": ids["score"],
                    "description": "Detects requests about a cash withdrawal being declined.",
                    "order": 1,
                    "type": "TactusScore",
                    "sectionId": ids["section"],
                    "scorecardId": ids["scorecard"],
                    "championVersionId": ids["version"],
                    "createdAt": seed_anchor,
                    "updatedAt": seed_anchor,
                },
                "id key scorecardId championVersionId",
                ("id", "key", "scorecardId", "championVersionId"),
            )
            self._ensure_model(
                client,
                "ScoreVersion",
                {
                    "id": ids["version"],
                    "scoreId": ids["score"],
                    "configuration": initial_score_configuration(ids["score"], ids["score"]),
                    "guidelines": (
                        "Answer Yes for a cash-withdrawal failure. Answer No for a withdrawal fee. "
                        "The initial rubric intentionally omits the unrecognized-withdrawal boundary."
                    ),
                    "isFeatured": True,
                    "note": f"Kubernetes demo baseline {self.manifest.run_id}",
                    "createdByUserId": "demo-user",
                    "createdAt": seed_anchor,
                    "updatedAt": seed_anchor,
                },
                "id scoreId configuration",
                ("id", "scoreId", "configuration"),
            )

            for partition, selected_rows in (("feedback", split.feedback), ("regression", split.regression)):
                for position, row in enumerate(selected_rows):
                    item_id = stable_resource_id(
                        self.manifest.run_id,
                        f"item-{partition}-{position:03d}-{row.source_label}-{row.row_index}",
                    )
                    feedback_id = stable_resource_id(
                        self.manifest.run_id,
                        f"feedback-{partition}-{position:03d}-{row.source_label}-{row.row_index}",
                    )
                    edited_at = (
                        anchor - timedelta(hours=1) + timedelta(seconds=position)
                        if partition == "feedback"
                        else anchor - timedelta(days=2) + timedelta(seconds=position)
                    ).isoformat().replace("+00:00", "Z")
                    self._ensure_model(
                        client,
                        "Item",
                        {
                            "id": item_id,
                            "accountId": ACCOUNT_ID,
                            "scoreId": ids["score"],
                            "externalId": item_id,
                            "description": "Public BANKING77 demo fixture",
                            "text": row.text,
                            "metadata": {
                                "demo_run_id": self.manifest.run_id,
                                "dataset": HUGGING_FACE_DATASET,
                                "revision": HUGGING_FACE_REVISION,
                                "partition": partition,
                                "source_label": row.source_label,
                                "row_index": row.row_index,
                            },
                            "isEvaluation": True,
                            "createdByType": "seed",
                            "createdAt": edited_at,
                            "updatedAt": edited_at,
                        },
                        "id accountId scoreId externalId",
                        ("id", "accountId", "scoreId", "externalId"),
                    )
                    initial_answer = (
                        "Yes"
                        if row.source_label in {"declined_cash_withdrawal", "cash_withdrawal_not_recognised"}
                        else "No"
                    )
                    self._ensure_model(
                        client,
                        "FeedbackItem",
                        {
                            "id": feedback_id,
                            "accountId": ACCOUNT_ID,
                            "scorecardId": ids["scorecard"],
                            "scoreId": ids["score"],
                            "itemId": item_id,
                            "cacheKey": f"{ids['score']}:{item_id}",
                            "initialAnswerValue": initial_answer,
                            "finalAnswerValue": row.expected,
                            "initialCommentValue": "Public benchmark initial label.",
                            "finalCommentValue": "Public benchmark final label.",
                            "editCommentValue": "Run-scoped public benchmark fixture.",
                            "editorName": "Kubernetes Demo",
                            "isAgreement": initial_answer == row.expected,
                            "isInvalid": False,
                            "editedAt": edited_at,
                            "createdAt": edited_at,
                            "updatedAt": edited_at,
                        },
                        "id scorecardId scoreId itemId finalAnswerValue",
                        ("id", "scorecardId", "scoreId", "itemId", "finalAnswerValue"),
                    )
                    self.manifest.add_resource("FeedbackItem", feedback_id)
                    self.manifest.add_resource("Item", item_id)
                    if partition == "regression":
                        self.manifest.metadata.setdefault("regression_feedback_ids", []).append(feedback_id)
                    elif "sample_item_id" not in self.manifest.metadata:
                        self.manifest.metadata["sample_item_id"] = item_id

            for model, key in (
                ("ScoreVersion", "version"),
                ("Score", "score"),
                ("ScorecardSection", "section"),
                ("Scorecard", "scorecard"),
            ):
                self.manifest.add_resource(model, ids[key])

        if not self.manifest.metadata.get("dataset_id"):
            regression_ids = list(dict.fromkeys(self.manifest.metadata["regression_feedback_ids"]))
            if len(regression_ids) != 100:
                raise DemoFailure(f"expected 100 regression feedback IDs, got {len(regression_ids)}")
            command = self._worker_command(
                "plexus",
                "score",
                "dataset-curate",
                "--scorecard",
                ids["scorecard"],
                "--score",
                ids["score"],
                "--max-items",
                "100",
                "--feedback-item-ids",
                ",".join(regression_ids),
                "--eligibility-rule",
                f"k8s demo run {self.manifest.run_id} regression fixture",
                "--json-only",
            )
            result = self.runner.run(command, timeout=1200)
            payload = extract_last_json(result.stdout)
            dataset_id = curated_dataset_identity(payload)
            self.manifest.metadata["dataset_id"] = dataset_id
            self.manifest.metadata["dataset_s3_key"] = payload.get("s3_key")

        return {
            "feedback_items": 100,
            "regression_items": 100,
            "benchmark_checksum": split.checksum,
            "source_sha256": SOURCE_SHA256,
            "dataset_id": self.manifest.metadata["dataset_id"],
        }

    def prediction(self) -> dict[str, Any]:
        ids = self.ids
        item_id = self.manifest.metadata.get("sample_item_id")
        if not item_id:
            raise DemoFailure("seed phase did not record a sample item")
        payload_base = {"scorecard": ids["scorecard"], "score": ids["score"], "item_id": item_id}

        with self.port_forward(NAMESPACE, f"svc/{WORKER_SERVICE}", 8000) as worker_url:
            health = requests.get(f"{worker_url}/healthz", timeout=10)
            ready = requests.get(f"{worker_url}/readyz", timeout=10)
            if health.status_code != 200 or ready.status_code != 200:
                raise DemoFailure("worker health or readiness endpoint failed")
            direct_payload = {
                **payload_base,
                "scoring_job_id": stable_resource_id(self.manifest.run_id, "direct-score-job"),
            }
            direct = requests.post(f"{worker_url}/v1/score", json=direct_payload, timeout=120)
            if direct.status_code != 200:
                raise DemoFailure(f"direct worker scoring returned HTTP {direct.status_code}")

        envoy_namespace, envoy_service, envoy_port = self._envoy_service()
        with self.port_forward(envoy_namespace, f"svc/{envoy_service}", envoy_port) as envoy_url:
            incomplete = requests.post(f"{envoy_url}/v1/score", json={}, timeout=30)
            if incomplete.status_code != 422:
                raise DemoFailure(f"incomplete Envoy request returned {incomplete.status_code}, expected 422")

            attempt = datetime.now(timezone.utc).strftime("%H%M%S%f")
            duplicate_payload = {
                **payload_base,
                "scoring_job_id": stable_resource_id(self.manifest.run_id, f"duplicate-{attempt}"),
            }
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                duplicate_responses = list(
                    executor.map(
                        lambda _: requests.post(
                            f"{envoy_url}/v1/score", json=duplicate_payload, timeout=120
                        ),
                        range(2),
                    )
                )
            duplicate_codes = sorted(response.status_code for response in duplicate_responses)
            if duplicate_codes not in ([200, 409], [200, 200]):
                raise DemoFailure(f"duplicate scoring contract returned {duplicate_codes}")
            replay = requests.post(f"{envoy_url}/v1/score", json=duplicate_payload, timeout=30)
            if replay.status_code != 200:
                raise DemoFailure("completed duplicate retry did not return persisted result")

            def score_distinct(index: int) -> int:
                response = requests.post(
                    f"{envoy_url}/v1/score",
                    json={
                        **payload_base,
                        "scoring_job_id": stable_resource_id(
                            self.manifest.run_id, f"concurrent-{attempt}-{index}"
                        ),
                    },
                    timeout=120,
                )
                return response.status_code

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                concurrent_codes = list(executor.map(score_distinct, range(5)))
            if concurrent_codes != [200] * 5:
                raise DemoFailure(f"concurrent scoring returned {concurrent_codes}")

        logs = self.runner.run(
            (
                "kubectl",
                "logs",
                "-n",
                NAMESPACE,
                f"deployment/{WORKER_DEPLOYMENT}",
                "--since=10m",
            )
        ).stdout
        if duplicate_payload["scoring_job_id"] not in logs:
            raise DemoFailure("worker logs did not correlate the scoring job ID")
        for marker in ("Processing scoring job:", "Storing score result for scoring job"):
            if marker not in logs:
                raise DemoFailure(f"worker logs did not contain processing marker {marker!r}")
        if any(marker in logs for marker in ("text_preview", "Sample data:", "transcript_preview")):
            raise DemoFailure("worker logs contained a prohibited sample-text marker")
        return {
            "health": 200,
            "ready": 200,
            "incomplete_envoy": 422,
            "duplicate_codes": duplicate_codes,
            "replay": 200,
            "concurrent_successes": 5,
        }

    def evaluation(self) -> dict[str, Any]:
        ids = self.ids
        dataset_id = self.manifest.metadata.get("dataset_id")
        if not dataset_id:
            raise DemoFailure("seed phase did not create a regression dataset")

        feedback_id = self.manifest.metadata.get("feedback_evaluation_id")
        if not feedback_id:
            feedback_id = self._run_evaluation(
                "feedback",
                (
                    "plexus",
                    "evaluate",
                    "feedback",
                    "--scorecard",
                    ids["scorecard"],
                    "--score",
                    ids["score"],
                    "--version",
                    ids["version"],
                    "--days",
                    "7",
                    "--max-items",
                    "100",
                    "--sampling-mode",
                    "newest",
                    "--notes",
                    f"Kubernetes demo {self.manifest.run_id} feedback baseline",
                ),
            )
            self.manifest.metadata["feedback_evaluation_id"] = feedback_id

        regression_id = self.manifest.metadata.get("regression_evaluation_id")
        if not regression_id:
            regression_id = self._run_evaluation(
                "accuracy",
                (
                    "plexus",
                    "evaluate",
                    "accuracy",
                    "--scorecard",
                    ids["scorecard"],
                    "--score",
                    ids["score"],
                    "--version",
                    ids["version"],
                    "--dataset-id",
                    str(dataset_id),
                    "--number-of-samples",
                    "100",
                    "--notes",
                    f"Kubernetes demo {self.manifest.run_id} regression baseline",
                    "--json-only",
                ),
            )
            self.manifest.metadata["regression_evaluation_id"] = regression_id

        with self.graphql() as client:
            feedback = self._evaluation_info(client, feedback_id)
            regression = self._evaluation_info(client, regression_id)
        for label, evaluation in (("feedback", feedback), ("regression", regression)):
            if evaluation.get("status") != "COMPLETED":
                raise DemoFailure(f"{label} evaluation is {evaluation.get('status')}, expected COMPLETED")
            if evaluation.get("totalItems") != 100 or evaluation.get("processedItems") != 100:
                raise DemoFailure(f"{label} evaluation did not complete exactly 100 items")
            if evaluation.get("errorMessage"):
                raise DemoFailure(f"{label} evaluation completed with an error")

        feedback_ac1 = metric_value(feedback.get("metrics"), "Alignment")
        regression_ac1 = metric_value(regression.get("metrics"), "Alignment")
        baseline_accuracy = evaluation_accuracy_fraction(feedback.get("accuracy"))
        if not 0.55 <= baseline_accuracy <= 0.85:
            raise DemoFailure(
                f"baseline accuracy {baseline_accuracy:.4f} is outside strict demo range 0.55..0.85"
            )
        self.manifest.metadata.update(
            {
                "baseline_accuracy": baseline_accuracy,
                "baseline_feedback_ac1": feedback_ac1,
                "baseline_regression_ac1": regression_ac1,
                "baseline_cost_usd": float(feedback.get("cost") or 0)
                + float(regression.get("cost") or 0),
            }
        )
        return {
            "feedback_evaluation_id": feedback_id,
            "regression_evaluation_id": regression_id,
            "feedback_items": 100,
            "regression_items": 100,
            "baseline_accuracy": baseline_accuracy,
            "feedback_ac1": feedback_ac1,
            "regression_ac1": regression_ac1,
            "cost_usd": self.manifest.metadata["baseline_cost_usd"],
        }

    def reporting(self) -> dict[str, Any]:
        ids = self.ids
        overview_command = (
            "plexus", "feedback", "report", "overview", "--scorecard", ids["scorecard"],
            "--score", ids["score"], "--days", "7", "--max-feedback-items", "100",
            "--max-concurrent", "4", "--format", "json",
        )
        commands = {
            "alignment": (
                "plexus", "feedback", "report", "alignment", "--scorecard", ids["scorecard"],
                "--score", ids["score"], "--days", "7", "--format", "json",
            ),
            "score_results": (
                "plexus", "feedback", "report", "score-results-report", "--scorecard",
                ids["scorecard"], "--score", ids["score"], "--id",
                str(self.manifest.metadata["sample_item_id"]), "--format", "json",
            ),
            "champion_history": (
                "plexus", "feedback", "report", "score-champion-version-timeline", "--scorecard",
                ids["scorecard"], "--score", ids["score"], "--days", "7", "--format", "json",
            ),
        }
        summaries: dict[str, Any] = dict(self.manifest.metadata.get("report_summaries") or {})
        if "overview" not in summaries:
            reports = self._report_records()
            try:
                summaries["overview"] = persisted_report_summary(
                    reports, ids["scorecard"], ids["score"], name_contains="Feedback Overview"
                )
            except DemoFailure:
                self.runner.run(self._worker_command(*overview_command), timeout=3600)
                summaries["overview"] = persisted_report_summary(
                    self._report_records(),
                    ids["scorecard"],
                    ids["score"],
                    name_contains="Feedback Overview",
                )
        for name, command in commands.items():
            if name in summaries:
                continue
            result = self.runner.run(self._worker_command(*command), timeout=3600)
            payload = extract_last_json(result.stdout)
            summaries[name] = safe_report_summary(payload, ids["scorecard"], ids["score"])
        self.manifest.metadata["report_summaries"] = summaries
        return {"reports": summaries, "count": len(summaries)}

    def _report_records(self) -> list[dict[str, Any]]:
        with self.graphql() as client:
            result = client.execute(
                "query DemoReports($accountId: String!) { "
                "listReports(filter: {accountId: {eq: $accountId}}, limit: 1000) { "
                "items { id name parameters } } }",
                {"accountId": ACCOUNT_ID},
            ).get("listReports") or {}
        return list(result.get("items") or [])

    def optimization(self) -> dict[str, Any]:
        ids = self.ids
        payload = self._resumable_optimizer_payload(ids)
        if payload is None:
            dispatch_count = int(self.manifest.metadata.get("optimizer_dispatch_count") or 0) + 1
            if dispatch_count != 1:
                raise DemoFailure("optimizer dispatch is not automatically retried")
            self.manifest.metadata["optimizer_dispatch_count"] = dispatch_count
            self._persist()
            command = optimizer_cli_command(self.manifest, ids)
            result = self.runner.run(self._worker_command(*command), timeout=14400)
            payload = extract_last_json(result.stdout)
            if (
                self.interrupt_after_optimizer
                and not self.manifest.metadata.get("optimizer_controlled_interruption_consumed")
            ):
                self.manifest.metadata["optimizer_controlled_interruption_consumed"] = True
                self.manifest.metadata["optimizer_completed_before_interruption"] = True
                self._persist()
                raise DemoFailure(
                    "controlled acceptance interruption after optimizer completion"
                )
        logical = payload.get("result") if isinstance(payload.get("result"), dict) else payload
        if not logical.get("success", True) or logical.get("status") == "error":
            raise DemoFailure("optimizer returned a logical failure")
        winning_version = logical.get("winning_version_id")
        feedback_delta = float(logical.get("recent_improvement") or 0.0)
        regression_delta = float(logical.get("regression_improvement") or 0.0)
        costs = logical.get("costs") or {}
        overall_cost = (((costs.get("totals") or {}).get("overall") or {}).get("incurred"))
        if overall_cost is None:
            raise DemoFailure("optimizer did not return its persisted total cost ledger")
        overall_cost = float(overall_cost)
        if overall_cost > self.manifest.max_cost_usd:
            raise DemoFailure(
                f"optimizer cost ${overall_cost:.4f} exceeded ${self.manifest.max_cost_usd:.2f} ceiling"
            )
        strict_candidate = bool(winning_version) and feedback_delta >= 0.05 and regression_delta >= -0.02
        safely_rejected = not strict_candidate and not winning_version

        promoted = False
        final_feedback_ac1: float | None = None
        final_evaluation_id: str | None = None
        if strict_candidate and self.promote:
            promotion = self._promote(ids["score"], str(winning_version))
            if not promotion.get("success"):
                raise DemoFailure("winning candidate did not pass champion-promotion safeguards")
            promoted = True
            final_evaluation_id = self._run_evaluation(
                "final-feedback",
                (
                    "plexus", "evaluate", "feedback", "--scorecard", ids["scorecard"], "--score",
                    ids["score"], "--version", str(winning_version), "--days", "7", "--max-items",
                    "100", "--sampling-mode", "newest", "--baseline",
                    str(self.manifest.metadata["feedback_evaluation_id"]), "--notes",
                    f"Kubernetes demo {self.manifest.run_id} promoted final verification",
                ),
            )
            with self.graphql() as client:
                final_eval = self._evaluation_info(client, final_evaluation_id)
            if final_eval.get("status") != "COMPLETED" or final_eval.get("processedItems") != 100:
                raise DemoFailure("promoted candidate final evaluation did not complete 100 items")
            final_feedback_ac1 = metric_value(final_eval.get("metrics"), "Alignment")

        metrics = AcceptanceMetrics(
            baseline_accuracy=float(self.manifest.metadata["baseline_accuracy"]),
            baseline_feedback_ac1=float(self.manifest.metadata["baseline_feedback_ac1"]),
            baseline_regression_ac1=float(self.manifest.metadata["baseline_regression_ac1"]),
            candidate_feedback_ac1=float(self.manifest.metadata["baseline_feedback_ac1"]) + feedback_delta,
            candidate_regression_ac1=float(self.manifest.metadata["baseline_regression_ac1"]) + regression_delta,
            final_feedback_ac1=final_feedback_ac1,
            evaluation_items=100,
            regression_items=100,
            execution_errors=0,
            candidate_promoted=promoted,
            candidates_safely_rejected=safely_rejected,
        )
        outcome = acceptance_outcome(metrics, self.manifest.profile)
        if not outcome.passed:
            failed = [item["name"] for item in outcome.assertions if not item["passed"]]
            raise DemoFailure(f"optimizer acceptance failed: {', '.join(failed)}")
        if self.resume and self.manifest.metadata.get("optimizer_completed_before_interruption"):
            if self.manifest.metadata.get("optimizer_dispatch_count") != 1:
                raise DemoFailure("optimizer reran during completed-artifact resume")
        self.manifest.metadata.update(
            {
                "winning_version_id": winning_version,
                "optimizer_feedback_delta": feedback_delta,
                "optimizer_regression_delta": regression_delta,
                "candidate_promoted": promoted,
                "final_evaluation_id": final_evaluation_id,
            }
        )
        return {
            "status": logical.get("status"),
            "winning_version_id": winning_version,
            "feedback_delta": feedback_delta,
            "regression_delta": regression_delta,
            "promoted": promoted,
            "cost_usd": overall_cost,
            "final_evaluation_id": final_evaluation_id,
            "assertions": list(outcome.assertions),
        }

    def _resumable_optimizer_payload(self, ids: Mapping[str, str]) -> dict[str, Any] | None:
        prior_phase = self.manifest.phases.get("optimization") or {}
        if not self.resume or not prior_phase or prior_phase.get("passed"):
            return None

        listed = self.runner.run(
            self._worker_command(
                "plexus", "procedure", "list", "--account", "local-demo", "--scorecard",
                ids["scorecard"], "--limit", "100", "--output", "json",
            ),
            timeout=300,
        )
        procedure_listing = extract_last_json(listed.stdout)
        procedure_items = procedure_listing.get("items") or []
        if not isinstance(procedure_items, list):
            raise DemoFailure("optimizer resume discovery returned an invalid procedure list")

        if len(procedure_items) != 1:
            raise DemoFailure(
                "optimizer resume refused to retry: expected exactly one run-scoped procedure, "
                f"found {len(procedure_items)}"
            )
        procedure_id = str(procedure_items[0].get("id") or "")
        summary_result = self.runner.run(
            self._worker_command(
                "plexus", "procedure", "optimizer-summary", procedure_id, "--output", "json"
            ),
            timeout=300,
        )
        summary = extract_last_json(summary_result.stdout)
        task_id = completed_optimizer_identity(summary, ids, procedure_id)

        code = (
            "import json,sys;"
            "from plexus.dashboard.api.client import PlexusDashboardClient;"
            "from plexus.cli.shared.task_output_storage import download_task_output_artifact;"
            "client=PlexusDashboardClient();"
            "task=(client.execute('query DemoTask($id: ID!){getTask(id:$id){id output}}',{'id':sys.argv[1]}).get('getTask') or {});"
            "payload=json.loads(download_task_output_artifact(task_id=sys.argv[1],compact_output=task.get('output'),client=client));"
            "result=payload.get('result') or {};"
            "costs=result.get('costs') or {};"
            "safe={'result':{'success':result.get('success'),'status':result.get('status'),"
            "'winning_version_id':result.get('winning_version_id'),"
            "'recent_improvement':result.get('recent_improvement'),"
            "'regression_improvement':result.get('regression_improvement'),"
            "'costs':{'totals':costs.get('totals')}}};"
            "print(json.dumps(safe))"
        )
        artifact = self.runner.run(
            self._worker_command("python", "-c", code, task_id), timeout=300
        )
        payload = extract_last_json(artifact.stdout)
        logical = payload.get("result") or {}
        if not isinstance(logical.get("costs"), dict):
            raise DemoFailure("completed optimizer artifact has no structured cost ledger")
        self.manifest.metadata.update(
            {
                "optimizer_procedure_id": procedure_id,
                "optimizer_task_id": task_id,
                "optimizer_resumed_from_completed_artifact": True,
            }
        )
        return payload

    def recovery(self) -> dict[str, Any]:
        ids = self.ids
        item_id = self.manifest.metadata["sample_item_id"]
        before = self._json_command(
            ("kubectl", "get", "pods", "-n", NAMESPACE, "-o", "json")
        )
        restart_counts_before = sum(
            status.get("restartCount", 0)
            for pod in before.get("items", [])
            for status in pod.get("status", {}).get("containerStatuses", [])
        )
        for deployment in (WORKER_DEPLOYMENT, PROXY_DEPLOYMENT):
            self.runner.run(
                ("kubectl", "rollout", "restart", f"deployment/{deployment}", "-n", NAMESPACE)
            )
            self.runner.run(
                (
                    "kubectl", "rollout", "status", f"deployment/{deployment}", "-n", NAMESPACE,
                    "--timeout=300s",
                ),
                timeout=320,
            )

        with self.graphql() as client:
            persisted = client.execute(
                "query PersistedItem($id: ID!) { getItem(id: $id) { id scoreId } }", {"id": item_id}
            ).get("getItem")
        if not persisted or persisted.get("scoreId") != ids["score"]:
            raise DemoFailure("seeded PostgreSQL item did not persist across restarts")

        with self.port_forward(NAMESPACE, f"svc/{WORKER_SERVICE}", 8000) as worker_url:
            ready = requests.get(f"{worker_url}/readyz", timeout=10)
            if ready.status_code != 200:
                raise DemoFailure("worker was not ready after restart")

        envoy_namespace, envoy_service, envoy_port = self._envoy_service()
        with self.port_forward(envoy_namespace, f"svc/{envoy_service}", envoy_port) as envoy_url:
            repeated = requests.post(
                f"{envoy_url}/v1/score",
                json={
                    "scorecard": ids["scorecard"],
                    "score": ids["score"],
                    "item_id": item_id,
                    "scoring_job_id": stable_resource_id(
                        self.manifest.run_id, "recovery-score-job"
                    ),
                },
                timeout=120,
            )
        if repeated.status_code != 200:
            raise DemoFailure(
                f"post-restart Envoy prediction returned HTTP {repeated.status_code}"
            )

        deployment = self.manifest.metadata.get("deployment") or {}
        chart_package = deployment.get("chart_package")
        values_file = deployment.get("values_file")
        if not chart_package or not Path(chart_package).is_file():
            raise DemoFailure("recovery upgrade requires the immutable chart package created by run --deploy")
        if not values_file or not Path(values_file).is_file():
            raise DemoFailure("recovery upgrade requires the exact sanitized values used by run --deploy")
        revision_before = json.loads(
            self.runner.run(("helm", "status", RELEASE, "-n", NAMESPACE, "-o", "json")).stdout
        ).get("version")
        self.runner.run(
            (
                "helm", "upgrade", RELEASE, str(chart_package), "-n", NAMESPACE,
                "--values", str(values_file),
            ),
            timeout=600,
        )
        revision_after = json.loads(
            self.runner.run(("helm", "status", RELEASE, "-n", NAMESPACE, "-o", "json")).stdout
        ).get("version")
        if not revision_after or int(revision_after) <= int(revision_before or 0):
            raise DemoFailure("identical Helm upgrade did not create a new successful revision")
        return {
            "worker_ready": True,
            "postgresql_persisted": True,
            "repeated_prediction": repeated.status_code,
            "helm_revision_before": revision_before,
            "helm_revision_after": revision_after,
            "prior_restart_count": restart_counts_before,
            "values_bytes": Path(values_file).stat().st_size,
        }

    def verify_retained(self) -> dict[str, Any]:
        ids = self.ids
        self.infrastructure()
        with self.graphql() as client:
            scorecard = client.execute(
                "query VerifyScorecard($id: ID!) { getScorecard(id: $id) { id accountId } }",
                {"id": ids["scorecard"]},
            ).get("getScorecard")
            score = client.execute(
                "query VerifyScore($id: ID!) { getScore(id: $id) { id scorecardId championVersionId } }",
                {"id": ids["score"]},
            ).get("getScore")
            if not scorecard or not score or score.get("scorecardId") != ids["scorecard"]:
                raise DemoFailure("retained scorecard/score fixture is incomplete")
            for key in ("feedback_evaluation_id", "regression_evaluation_id"):
                evaluation_id = self.manifest.metadata.get(key)
                if not evaluation_id:
                    raise DemoFailure(f"retained manifest is missing {key}")
                evaluation = self._evaluation_info(client, evaluation_id)
                if evaluation.get("status") != "COMPLETED" or evaluation.get("processedItems") != 100:
                    raise DemoFailure(f"retained evaluation {evaluation_id} is not a completed 100-item run")
        summary = {"scorecard": True, "score": True, "evaluations": 2, "mutations": 0}
        self.manifest.record_phase("verification", passed=True, summary=summary)
        self._persist()
        return summary

    def cleanup(self) -> dict[str, int]:
        owned_ids = [resource_id for values in self.manifest.resources.values() for resource_id in values]
        assert_cleanup_scope(self.manifest.run_id, owned_ids)
        deleted: dict[str, int] = {}
        with self.graphql() as client:
            generated = self._discover_generated_resources(client)
            generated_order = (
                "ReportBlock", "Report", "Evaluation", "Procedure", "Task", "DataSet",
                "DataSourceVersion", "DataSource",
            )
            for model in generated_order:
                count = 0
                for resource_id in generated.get(model, []):
                    self._delete_model(client, model, resource_id)
                    count += 1
                deleted[model] = count

            order = ("FeedbackItem", "Item", "ScoreVersion", "Score", "ScorecardSection", "Scorecard")
            for model in order:
                count = 0
                for resource_id in reversed(self.manifest.resources.get(model, [])):
                    self._delete_model(client, model, resource_id)
                    count += 1
                deleted[model] = count
        return deleted

    def _discover_generated_resources(self, client: GraphQLClient) -> dict[str, list[str]]:
        score_id = self.ids["score"]
        resources: dict[str, list[str]] = {}
        for model in ("Evaluation", "Task", "DataSet", "Procedure"):
            result = client.execute(
                f"query Owned{model}s($scoreId: String!) {{ "
                f"list{model}s(filter: {{scoreId: {{eq: $scoreId}}}}, limit: 1000) {{ "
                "items { id scoreId } } }",
                {"scoreId": score_id},
            ).get(f"list{model}s") or {}
            items = result.get("items") or []
            if any(item.get("scoreId") != score_id for item in items):
                raise DemoFailure(f"cleanup discovery returned a foreign {model}")
            resources[model] = [item["id"] for item in items]

        dataset_versions: list[str] = []
        data_sources: list[str] = []
        for dataset_id in resources.get("DataSet", []):
            dataset = client.execute(
                "query OwnedDataSet($id: ID!) { getDataSet(id: $id) { id scoreId dataSourceVersionId } }",
                {"id": dataset_id},
            ).get("getDataSet") or {}
            if dataset.get("scoreId") != score_id:
                raise DemoFailure("cleanup refused a dataset not owned by the run-scoped score")
            version_id = dataset.get("dataSourceVersionId")
            if version_id:
                dataset_versions.append(version_id)
                version = client.execute(
                    "query OwnedDataSourceVersion($id: ID!) { getDataSourceVersion(id: $id) { id dataSourceId } }",
                    {"id": version_id},
                ).get("getDataSourceVersion") or {}
                if version.get("dataSourceId"):
                    data_sources.append(version["dataSourceId"])
        resources["DataSourceVersion"] = list(dict.fromkeys(dataset_versions))
        resources["DataSource"] = list(dict.fromkeys(data_sources))

        reports = client.execute(
            "query DemoReports($accountId: String!) { "
            "listReports(filter: {accountId: {eq: $accountId}}, limit: 1000) { "
            "items { id parameters } } }",
            {"accountId": ACCOUNT_ID},
        ).get("listReports") or {}
        owned_reports = [
            report["id"]
            for report in reports.get("items") or []
            if score_id in json.dumps(report.get("parameters") or "")
            or self.manifest.run_id in json.dumps(report.get("parameters") or "")
        ]
        report_blocks: list[str] = []
        for report_id in owned_reports:
            blocks = client.execute(
                "query DemoReportBlocks($reportId: String!) { "
                "listReportBlocks(filter: {reportId: {eq: $reportId}}, limit: 1000) { items { id reportId } } }",
                {"reportId": report_id},
            ).get("listReportBlocks") or {}
            for block in blocks.get("items") or []:
                if block.get("reportId") != report_id:
                    raise DemoFailure("cleanup discovery returned a foreign ReportBlock")
                report_blocks.append(block["id"])
        resources["Report"] = owned_reports
        resources["ReportBlock"] = report_blocks
        return resources

    @staticmethod
    def _delete_model(client: GraphQLClient, model: str, resource_id: str) -> None:
        mutation = (
            f"mutation DeleteDemo{model}($input: Delete{model}Input!) {{ "
            f"delete{model}(input: $input) {{ id }} }}"
        )
        deleted = client.execute(mutation, {"input": {"id": resource_id}}).get(f"delete{model}")
        if not deleted or deleted.get("id") != resource_id:
            raise DemoFailure(f"failed to delete owned {model} {resource_id}")

    @contextmanager
    def graphql(self) -> Iterator[GraphQLClient]:
        with self.port_forward(NAMESPACE, f"svc/{PROXY_SERVICE}", 8000) as base_url:
            yield GraphQLClient(f"{base_url}/graphql", PROXY_API_KEY)

    @contextmanager
    def port_forward(self, namespace: str, resource: str, remote_port: int) -> Iterator[str]:
        local_port = _free_port()
        process = subprocess.Popen(
            (
                "kubectl", "port-forward", "-n", namespace, resource,
                f"{local_port}:{remote_port}",
            ),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            for _ in range(80):
                if process.poll() is not None:
                    details = process.stderr.read() if process.stderr else ""
                    raise DemoFailure(f"port-forward failed: {redact_text(details)}")
                try:
                    with socket.create_connection(("127.0.0.1", local_port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise DemoFailure(f"port-forward to {resource} did not become ready")
            yield f"http://127.0.0.1:{local_port}"
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def _ensure_model(
        self,
        client: GraphQLClient,
        model: str,
        input_doc: Mapping[str, Any],
        selection: str,
        compare_fields: Sequence[str],
    ) -> None:
        resource_id = str(input_doc["id"])
        query = f"query GetDemo{model}($id: ID!) {{ get{model}(id: $id) {{ {selection} }} }}"
        existing = client.execute(query, {"id": resource_id}).get(f"get{model}")
        if existing:
            mismatches = [
                field
                for field in compare_fields
                if _canonical(existing.get(field)) != _canonical(input_doc.get(field))
            ]
            if mismatches:
                raise DemoFailure(
                    f"existing {model} {resource_id} conflicts in fields {', '.join(mismatches)}"
                )
            return
        mutation = (
            f"mutation CreateDemo{model}($input: Create{model}Input!) {{ "
            f"create{model}(input: $input) {{ {selection} }} }}"
        )
        created = client.execute(mutation, {"input": dict(input_doc)}).get(f"create{model}")
        if not created or created.get("id") != resource_id:
            raise DemoFailure(f"failed to create run-scoped {model}")

    def _run_evaluation(self, label: str, command: Sequence[str]) -> str:
        id_path = f"/tmp/{stable_resource_id(self.manifest.run_id, label)}.id"
        full_command = self._worker_command(*command, "--emit-id-file", id_path)
        self.runner.run(full_command, timeout=7200)
        result = self.runner.run(
            self._worker_command("python", "-c", "import pathlib,sys;print(pathlib.Path(sys.argv[1]).read_text().strip())", id_path)
        )
        evaluation_id = result.stdout.strip()
        if not evaluation_id or not re.fullmatch(r"[A-Za-z0-9-]{8,128}", evaluation_id):
            raise DemoFailure(f"{label} evaluation did not emit a valid ID")
        return evaluation_id

    def _evaluation_info(self, client: GraphQLClient, evaluation_id: str) -> dict[str, Any]:
        result = client.execute(
            """
            query DemoEvaluation($id: ID!) {
              getEvaluation(id: $id) {
                id type status accuracy cost totalItems processedItems errorMessage
                scorecardId scoreId scoreVersionId metrics parameters taskId
              }
            }
            """,
            {"id": evaluation_id},
        ).get("getEvaluation")
        if not result:
            raise DemoFailure(f"evaluation {evaluation_id} was not persisted")
        return result

    def _promote(self, score_id: str, version_id: str) -> dict[str, Any]:
        code = (
            "import json,sys;"
            "from MCP.tools.tactus_runtime.execute import _default_score_set_champion;"
            "print(json.dumps(_default_score_set_champion({'score_id':sys.argv[1],'version_id':sys.argv[2]})))"
        )
        result = self.runner.run(
            self._worker_command("python", "-c", code, score_id, version_id), timeout=300
        )
        payload = extract_last_json(result.stdout)
        return payload

    def _envoy_service(self) -> tuple[str, str, int]:
        services = self._json_command(
            (
                "kubectl", "get", "svc", "-A", "-l",
                "gateway.envoyproxy.io/owning-gateway-name=plexus-plexus-worker-gateway",
                "-o", "json",
            )
        )
        items = services.get("items") or []
        if len(items) != 1:
            raise DemoFailure(f"expected one Envoy data-plane Service, found {len(items)}")
        item = items[0]
        ports = item.get("spec", {}).get("ports", [])
        if not ports:
            raise DemoFailure("Envoy data-plane Service has no ports")
        port = next((entry["port"] for entry in ports if entry.get("port") == 80), ports[0]["port"])
        return item["metadata"]["namespace"], item["metadata"]["name"], int(port)

    def _worker_command(self, *args: str) -> tuple[str, ...]:
        return (
            "kubectl", "exec", "-n", NAMESPACE, f"deployment/{WORKER_DEPLOYMENT}", "--", *args
        )

    def _json_command(self, argv: Sequence[str]) -> dict[str, Any]:
        result = self.runner.run(argv)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise DemoFailure(f"command did not return valid JSON: {' '.join(argv)}") from exc


def initial_score_configuration(score_id: str, score_key: str) -> str:
    return f'''name: Declined Cash Withdrawal
key: {score_key}
id: {score_id}
class: TactusScore
valid_classes:
  - "Yes"
  - "No"
code: |
  default_model "openai/gpt-5.4-nano"

  ClassifyProcedure {{
    classes = {{"Yes", "No"}},
    system_message = [[
    You classify banking support requests.
    Return Yes when the customer says a cash withdrawal was declined, failed, blocked, or did not work.
    Return No when the request is specifically about a fee or charge for a cash withdrawal.
    This intentionally incomplete baseline does not define the unrecognized-withdrawal boundary.
    Give one short reason, then put exactly one final label on the last line: Yes or No.
    ]],
    user_message = [[
    <request>
    {{{{ text }}}}
    </request>
    ]]
  }}
'''


def optimizer_cli_command(manifest: DemoManifest, ids: Mapping[str, str]) -> list[str]:
    recent_baseline_id = manifest.metadata.get("feedback_evaluation_id")
    regression_baseline_id = manifest.metadata.get("regression_evaluation_id")
    if not recent_baseline_id or not regression_baseline_id:
        raise DemoFailure("optimizer requires both verified baseline evaluation IDs")
    return [
        "plexus", "procedure", "optimize", "--scorecard", ids["scorecard"], "--score",
        ids["score"], "--days", "7", "--max-samples", "100", "--max-iterations",
        str(manifest.max_iterations), "--num-candidates", "1", "--max-cost-usd",
        str(manifest.max_cost_usd), "--improvement-threshold", "0.05",
        "--evaluation-timeout-minutes", "30", "--resume-recent-eval",
        str(recent_baseline_id), "--resume-regression-eval", str(regression_baseline_id),
        "--agent-model", "hypothesis_planner=gpt-5.4-nano", "--agent-model",
        "code_editor=gpt-5.4-nano", "--agent-model", "cycle_analyst=gpt-5.4-nano",
        "--agent-model", "report_writer=gpt-5.4-nano", "--agent-model",
        "reviewer=gpt-5.4-nano", "--agent-model", "early_stop_advisor=gpt-5.4-nano",
        "--output", "json",
    ]


def load_banking77_rows() -> list[dict[str, Any]]:
    with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
        raw = response.read()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise DemoFailure(f"BANKING77 source checksum mismatch: {digest}")
    decoded = raw.decode("utf-8")
    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(decoded.splitlines())
    for row_index, row in enumerate(reader):
        rows.append({"row_index": row_index, "text": row.get("text"), "label": row.get("category")})
    return rows


def extract_last_json(text: str) -> dict[str, Any]:
    cleaned = ANSI_RE.sub("", text or "")
    decoder = json.JSONDecoder()
    candidates: list[tuple[int, int, Any]] = []
    for index, character in enumerate(cleaned):
        if character not in "{[":
            continue
        try:
            value, consumed = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        candidates.append((index, index + consumed, value))
    candidates.sort(key=lambda candidate: (candidate[1], -candidate[0]), reverse=True)
    for _, _, value in candidates:
        if isinstance(value, dict):
            return value
        if isinstance(value, list):
            return {"items": value}
    raise DemoFailure("command completed without a machine-readable JSON result")


def completed_optimizer_identity(
    summary: Mapping[str, Any], ids: Mapping[str, str], procedure_id: str
) -> str:
    procedure = summary.get("procedure") or {}
    effective_status = str((summary.get("summary") or {}).get("effective_status") or "").upper()
    if summary.get("procedure_id") != procedure_id or procedure.get("id") != procedure_id:
        raise DemoFailure("optimizer resume summary referenced a different procedure")
    if procedure.get("scorecard_id") != ids["scorecard"] or procedure.get("score_id") != ids["score"]:
        raise DemoFailure("optimizer resume summary escaped the run-scoped score")
    if effective_status != "COMPLETED":
        raise DemoFailure(
            f"optimizer resume refused to retry incomplete procedure {procedure_id}: "
            f"effective status {effective_status or 'UNKNOWN'}"
        )
    task_id = procedure.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise DemoFailure("completed optimizer summary has no task output identity")
    return task_id


def curated_dataset_identity(payload: Mapping[str, Any]) -> str:
    dataset_id = payload.get("dataset_id")
    if not isinstance(dataset_id, str) or not dataset_id or payload.get("row_count") != 100:
        raise DemoFailure("regression dataset curation did not create exactly 100 rows")
    return dataset_id


def metric_value(metrics: Any, name: str) -> float:
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except json.JSONDecodeError as exc:
            raise DemoFailure("evaluation metrics are not valid JSON") from exc
    if isinstance(metrics, Mapping):
        value = metrics.get(name) if name in metrics else metrics.get(name.lower())
        if isinstance(value, Mapping):
            value = value.get("value")
        if value is not None:
            return float(value)
    if isinstance(metrics, list):
        for metric in metrics:
            if str(metric.get("name") or "").lower() == name.lower():
                return float(metric.get("value"))
    raise DemoFailure(f"evaluation metrics are missing {name}")


def evaluation_accuracy_fraction(value: Any) -> float:
    try:
        persisted_percent = float(value)
    except (TypeError, ValueError) as exc:
        raise DemoFailure("evaluation accuracy is not numeric") from exc
    if not 0.0 <= persisted_percent <= 100.0:
        raise DemoFailure("evaluation accuracy is outside 0..100 percent")
    return persisted_percent / 100.0


def safe_report_summary(payload: Mapping[str, Any], scorecard_id: str, score_id: str) -> dict[str, Any]:
    serialized = json.dumps(payload, default=str)
    if scorecard_id not in serialized and score_id not in serialized:
        raise DemoFailure("report output did not reference the run-scoped scorecard or score")
    ids: list[str] = []
    _collect_safe_ids(payload, ids)
    return {"referenced_run_scope": True, "record_ids": sorted(set(ids))[:20]}


def persisted_report_summary(
    reports: Sequence[Mapping[str, Any]],
    scorecard_id: str,
    score_id: str,
    *,
    name_contains: str | None = None,
) -> dict[str, Any]:
    owned: list[str] = []
    for report in reports:
        if name_contains and name_contains not in str(report.get("name") or ""):
            continue
        parameters = report.get("parameters")
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                continue
        if not isinstance(parameters, Mapping):
            continue
        if parameters.get("scorecard") == scorecard_id and parameters.get("score") == score_id:
            report_id = report.get("id")
            if isinstance(report_id, str) and report_id:
                owned.append(report_id)
    if not owned:
        raise DemoFailure("persisted report did not reference the run-scoped scorecard and score")
    return {"referenced_run_scope": True, "record_ids": sorted(set(owned))}


def _collect_safe_ids(value: Any, target: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in {"id", "report_id", "reportId", "report_block_id", "reportBlockId"} and isinstance(nested, str):
                target.append(nested)
            elif key.lower() not in {"text", "transcript", "quote", "evidence", "content", "output", "log"}:
                _collect_safe_ids(nested, target)
    elif isinstance(value, list):
        for nested in value:
            _collect_safe_ids(nested, target)


def _condition_true(resource: Mapping[str, Any], condition_type: str) -> bool:
    conditions = resource.get("status", {}).get("conditions", [])
    if resource.get("kind") == "Gateway":
        conditions += [
            condition
            for listener in resource.get("status", {}).get("listeners", [])
            for condition in listener.get("conditions", [])
        ]
    if resource.get("kind") == "HTTPRoute":
        conditions += [
            condition
            for parent in resource.get("status", {}).get("parents", [])
            for condition in parent.get("conditions", [])
        ]
    return any(
        condition.get("type") == condition_type and condition.get("status") == "True"
        for condition in conditions
    )


def _pod_ready(pod: Mapping[str, Any]) -> bool:
    return any(
        condition.get("type") == "Ready" and condition.get("status") == "True"
        for condition in pod.get("status", {}).get("conditions", [])
    )


def _canonical(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
