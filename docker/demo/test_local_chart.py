from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import yaml

from docker.demo.bootstrap import write_effective_local_values


def test_local_chart_renders_ready_persistent_object_store_with_secret_backed_worker(
    tmp_path: Path,
) -> None:
    """The local release owns storage needed by datasets and report attachments."""
    source_root = Path(__file__).resolve().parents[2] / "docker" / "helm"
    helm_root = tmp_path / "helm"
    shutil.copytree(source_root, helm_root)
    chart = helm_root / "plexus-stack"
    helm_env = {
        **os.environ,
        "HELM_REPOSITORY_CONFIG": str(tmp_path / "repositories.yaml"),
        "HELM_REPOSITORY_CACHE": str(tmp_path / "repository-cache"),
    }
    subprocess.run(
        ("helm", "repo", "add", "bitnami", "https://charts.bitnami.com/bitnami"),
        check=True,
        capture_output=True,
        env=helm_env,
    )
    subprocess.run(
        ("helm", "dependency", "build", str(chart)),
        check=True,
        capture_output=True,
        env=helm_env,
    )
    rendered = subprocess.run(
        (
            "helm",
            "template",
            "plexus",
            str(chart),
            "--namespace",
            "plexus-local",
            "--values",
            str(chart / "values-local.yaml.example"),
        ),
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    documents = [document for document in yaml.safe_load_all(rendered) if document]
    by_identity = {
        (document["kind"], document["metadata"]["name"]): document for document in documents
    }
    assert ("Deployment", "plexus-local-object-store") in by_identity
    assert ("Service", "plexus-local-object-store") in by_identity
    assert ("PersistentVolumeClaim", "plexus-local-object-store") in by_identity
    assert ("Secret", "plexus-local-object-store") in by_identity
    assert ("Job", "plexus-local-object-store-buckets") in by_identity

    worker = by_identity[("Deployment", "plexus-plexus-worker")]
    env = {
        item["name"]: item
        for item in worker["spec"]["template"]["spec"]["containers"][0]["env"]
    }
    assert env["AWS_ENDPOINT_URL"]["value"] == "https://plexus-local-object-store:9000"
    assert env["PLEXUS_OBJECT_STORE_ENDPOINT"]["value"] == env["AWS_ENDPOINT_URL"]["value"]
    assert env["PLEXUS_GRAPHQL_AUTH_MODE"]["value"] == "api_key"
    assert env["PLEXUS_ARTIFACT_CA_BUNDLE"]["value"] == "/app/certs/minio-ca.crt"
    assert env["AWS_CA_BUNDLE"]["value"] == env["PLEXUS_ARTIFACT_CA_BUNDLE"]["value"]
    assert env["AMPLIFY_STORAGE_DATASETS_BUCKET_NAME"]["value"] == "plexus-local-datasets"
    assert env["AWS_ACCESS_KEY_ID"]["valueFrom"]["secretKeyRef"]["name"] == (
        "plexus-local-object-store"
    )
    assert "value" not in env["AWS_ACCESS_KEY_ID"]
    assert env["AWS_SECRET_ACCESS_KEY"]["valueFrom"]["secretKeyRef"]["name"] == (
        "plexus-local-object-store"
    )
    assert env["PLEXUS_GRAPHQL_AUTH_MODE"]["value"] == "api_key"
    assert "OPENAI_API_KEY" in env
    assert "ANTHROPIC_API_KEY" not in env

    recovery = by_identity[("CronJob", "plexus-plexus-worker-procedure-recovery")]
    recovery_env = {
        item["name"]: item
        for item in recovery["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["env"]
    }
    assert recovery_env["PLEXUS_GRAPHQL_AUTH_MODE"]["value"] == "api_key"
    assert recovery_env["PLEXUS_API_KEY"]["valueFrom"]["secretKeyRef"]["name"] == env[
        "PLEXUS_API_KEY"
    ]["valueFrom"]["secretKeyRef"]["name"]
    worker_volumes = worker["spec"]["template"]["spec"]["volumes"]
    assert any(
        volume.get("secret", {}).get("secretName") == "plexus-local-object-store-tls"
        for volume in worker_volumes
    )

    object_store = by_identity[("Deployment", "plexus-local-object-store")]
    object_store_container = object_store["spec"]["template"]["spec"]["containers"][0]
    assert object_store_container["args"] == [
        "server", "/data", "--certs-dir", "/etc/minio/certs"
    ]
    assert object_store_container["readinessProbe"]["httpGet"]["scheme"] == "HTTPS"
    assert any(
        volume.get("secret", {}).get("secretName") == "plexus-local-object-store-tls"
        for volume in object_store["spec"]["template"]["spec"]["volumes"]
    )

    proxy = by_identity[("Deployment", "plexus-graphql-proxy")]
    proxy_env = {
        item["name"]: item
        for item in proxy["spec"]["template"]["spec"]["containers"][0]["env"]
    }
    assert proxy_env["PLEXUS_ARTIFACT_STORE_ACCESS_KEY_ID"]["valueFrom"]["secretKeyRef"]["name"] == (
        "plexus-local-object-store"
    )
    assert proxy_env["PLEXUS_ARTIFACT_STORE_SECRET_ACCESS_KEY"]["valueFrom"]["secretKeyRef"]["name"] == (
        "plexus-local-object-store"
    )
    proxy_config = by_identity[("ConfigMap", "plexus-graphql-proxy")]["data"]
    assert proxy_config["PLEXUS_PROXY_AUTH_MODE"] == "api_key"
    assert proxy_config["PLEXUS_ARTIFACT_TICKETS_ENABLED"] == "true"
    assert proxy_config["PLEXUS_ARTIFACT_STORE_ENDPOINT"] == (
        "https://plexus-local-object-store:9000"
    )

    bucket_job = by_identity[("Job", "plexus-local-object-store-buckets")]
    args = bucket_job["spec"]["template"]["spec"]["containers"][0]["args"]
    rendered_args = " ".join(args)
    assert "https://plexus-local-object-store:9000" in rendered_args
    assert "--insecure" not in rendered_args
    for bucket in (
        "plexus-local-datasets",
        "plexus-local-report-block-details",
        "plexus-local-rubric-memory",
        "plexus-local-task-attachments",
        "plexus-local-score-result-attachments",
    ):
        assert bucket in rendered_args


def test_effective_values_pin_built_images_without_embedding_llm_secret(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / "docker" / "helm" / "plexus-stack" / (
        "values-local.yaml.example"
    )
    destination = tmp_path / "values-local.yaml"
    write_effective_local_values(
        source,
        destination,
        worker_tag="worker-build",
        proxy_tag="proxy-build",
    )
    values = yaml.safe_load(destination.read_text())
    assert values["plexus-worker"]["image"]["tag"] == "worker-build"
    assert values["graphql-proxy"]["image"]["tag"] == "proxy-build"
    assert values["plexus-worker"]["env"]["MAX_JOBS_PER_WORKER"] == "2"
    assert values["plexus-worker"]["resources"] == {
        "requests": {"cpu": "500m", "memory": "1Gi"},
        "limits": {"cpu": 2, "memory": "4Gi"},
    }
    assert values["plexus-worker"]["llm"]["existingSecret"] == "plexus-local-llm-keys"
    assert "apiKey" not in values["plexus-worker"]["llm"]


def test_worker_chart_accepts_explicit_iam_without_injecting_api_key() -> None:
    chart = Path(__file__).resolve().parents[2] / "docker" / "helm" / "plexus-worker"
    rendered = subprocess.run(
        (
            "helm",
            "template",
            "plexus",
            str(chart),
            "--set",
            "plexus.api.url=https://example.invalid/graphql",
            "--set",
            "plexus.api.authMode=iam",
            "--set",
            "procedureRecovery.enabled=true",
        ),
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    documents = [document for document in yaml.safe_load_all(rendered) if document]
    workloads = [
        document
        for document in documents
        if document["kind"] in {"Deployment", "CronJob"}
    ]
    assert {document["kind"] for document in workloads} == {"Deployment", "CronJob"}
    for workload in workloads:
        pod_spec = (
            workload["spec"]["template"]["spec"]
            if workload["kind"] == "Deployment"
            else workload["spec"]["jobTemplate"]["spec"]["template"]["spec"]
        )
        env = {item["name"]: item for item in pod_spec["containers"][0]["env"]}
        assert env["PLEXUS_GRAPHQL_AUTH_MODE"]["value"] == "iam"
        assert "PLEXUS_API_KEY" not in env


def test_worker_chart_rejects_unknown_graphql_auth_mode() -> None:
    chart = Path(__file__).resolve().parents[2] / "docker" / "helm" / "plexus-worker"
    rendered = subprocess.run(
        (
            "helm",
            "template",
            "plexus",
            str(chart),
            "--set",
            "plexus.api.url=https://example.invalid/graphql",
            "--set",
            "plexus.api.authMode=automatic",
        ),
        check=False,
        capture_output=True,
        text=True,
    )

    assert rendered.returncode != 0
    assert "plexus.api.authMode must be one of api_key or iam" in rendered.stderr
