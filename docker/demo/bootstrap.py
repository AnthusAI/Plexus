from __future__ import annotations

import base64
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import yaml

from docker.demo.harness import (
    ACCOUNT_ID,
    NAMESPACE,
    OBJECT_STORE_DEPLOYMENT,
    OBJECT_STORE_TLS_SECRET,
    OPENAI_SECRET,
    PROXY_API_KEY,
    PROXY_SERVICE,
    RELEASE,
    CommandRunner,
    DemoFailure,
    DemoHarness,
    GraphQLClient,
    extract_last_json,
)


ENVOY_NAMESPACE = "envoy-gateway-system"
ENVOY_RELEASE = "envoy-gateway"
ENVOY_VERSION = "1.8.1"


class SnapshotDeployer:
    """Build and deploy an immutable HEAD snapshot without touching the checkout."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.runner = CommandRunner(output_dir / "events.jsonl")

    def deploy(self) -> dict[str, Any]:
        context = self.runner.run(("kubectl", "config", "current-context")).stdout.strip()
        if context != "docker-desktop":
            raise DemoFailure(f"snapshot deployment requires docker-desktop context, got {context!r}")
        head = self.runner.run(("git", "rev-parse", "HEAD")).stdout.strip()
        tag = f"k8s-demo-{head[:12]}"

        snapshot_root = Path(tempfile.mkdtemp(prefix="plexus-k8s-demo-snapshot-"))
        archive = snapshot_root / "source.tar"
        source = snapshot_root / "source"
        source.mkdir()
        try:
            self.runner.run(("git", "archive", "--format=tar", "-o", str(archive), "HEAD"))
            with tarfile.open(archive) as handle:
                handle.extractall(source)

            self._ensure_image("plexus-worker", tag, source / "docker/Dockerfile", source)
            self._ensure_image(
                "plexus-graphql-proxy",
                tag,
                source / "services/private-graphql-proxy/Dockerfile",
                source,
            )
            self._install_envoy()
            self._ensure_llm_secret()
            self._ensure_object_store_tls_secret()

            chart = source / "docker/helm/plexus-stack"
            values = self.output_dir / "values-local.yaml"
            write_effective_local_values(
                chart / "values-local.yaml.example",
                values,
                worker_tag=tag,
                proxy_tag=tag,
            )
            self.runner.run(("helm", "dependency", "build", str(chart)), timeout=600)
            package_result = self.runner.run(
                ("helm", "package", str(chart), "--destination", str(self.output_dir)), timeout=300
            )
            chart_package = self.output_dir / "plexus-stack-1.0.0.tgz"
            if not chart_package.exists():
                raise DemoFailure(f"Helm package was not created: {package_result.stdout.strip()}")
            self.runner.run(
                (
                    "helm", "upgrade", "--install", RELEASE, str(chart_package), "--namespace", NAMESPACE,
                    "--create-namespace", "--values", str(values),
                ),
                timeout=1200,
            )
            for deployment in (
                "plexus-graphql-proxy",
                "plexus-plexus-worker",
                OBJECT_STORE_DEPLOYMENT,
            ):
                self.runner.run(
                    (
                        "kubectl", "rollout", "status", f"deployment/{deployment}", "-n", NAMESPACE,
                        "--timeout=300s",
                    ),
                    timeout=320,
                )
            self._ensure_local_control_plane(source)
            artifact_ticket_smoke = self._artifact_ticket_smoke()
            return {
                "git_head": head,
                "image_tag": tag,
                "envoy_gateway": ENVOY_VERSION,
                "chart_package": str(chart_package.resolve()),
                "values_file": str(values.resolve()),
                "artifact_ticket_smoke": artifact_ticket_smoke,
            }
        finally:
            shutil.rmtree(snapshot_root)
    def _ensure_image(self, repository: str, tag: str, dockerfile: Path, context: Path) -> None:
        image = f"{repository}:{tag}"
        present = self.runner.run(("docker", "image", "inspect", image), check=False)
        if present.returncode == 0:
            return
        self.runner.run(
            ("docker", "build", "--tag", image, "--file", str(dockerfile), str(context)),
            timeout=3600,
        )

    def _install_envoy(self) -> None:
        self.runner.run(
            (
                "helm", "upgrade", "--install", ENVOY_RELEASE,
                "oci://docker.io/envoyproxy/gateway-helm", "--version", ENVOY_VERSION,
                "--namespace", ENVOY_NAMESPACE, "--create-namespace",
            ),
            timeout=600,
        )
        self.runner.run(
            (
                "kubectl", "wait", "--namespace", ENVOY_NAMESPACE,
                "--for=condition=Available", "deployment/envoy-gateway", "--timeout=180s",
            ),
            timeout=200,
        )
        gateway_class = {
            "apiVersion": "gateway.networking.k8s.io/v1",
            "kind": "GatewayClass",
            "metadata": {"name": "envoy-gateway"},
            "spec": {"controllerName": "gateway.envoyproxy.io/gatewayclass-controller"},
        }
        self.runner.run(
            ("kubectl", "apply", "-f", "-"),
            input_text=yaml.safe_dump(gateway_class),
        )
        self.runner.run(
            ("kubectl", "wait", "--for=condition=Accepted", "gatewayclass/envoy-gateway", "--timeout=180s"),
            timeout=200,
        )

    def _ensure_llm_secret(self) -> None:
        namespace = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {"name": NAMESPACE},
        }
        self.runner.run(
            ("kubectl", "apply", "-f", "-"),
            input_text=json.dumps(namespace),
        )
        existing = self.runner.run(
            (
                "kubectl",
                "get",
                "secret",
                OPENAI_SECRET,
                "-n",
                NAMESPACE,
                "-o",
                'go-template={{if index .data "openai-api-key"}}present{{end}}',
            ),
            check=False,
        )
        if existing.returncode == 0:
            if existing.stdout.strip() != "present":
                raise DemoFailure(f"existing {OPENAI_SECRET} Secret has no openai-api-key entry")
            return
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            try:
                from plexus.config.loader import load_config

                load_config()
            except Exception as exc:
                raise DemoFailure("could not load the approved local Plexus configuration") from exc
            api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise DemoFailure("OPENAI_API_KEY is required to create the Kubernetes LLM secret")
        secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": OPENAI_SECRET, "namespace": NAMESPACE},
            "type": "Opaque",
            "data": {"openai-api-key": base64.b64encode(api_key.encode()).decode()},
        }
        self.runner.run(
            ("kubectl", "apply", "-f", "-"),
            input_text=json.dumps(secret),
        )

    def _ensure_object_store_tls_secret(self) -> None:
        existing = self.runner.run(
            (
                "kubectl",
                "get",
                "secret",
                OBJECT_STORE_TLS_SECRET,
                "-n",
                NAMESPACE,
                "-o",
                'go-template={{if and (index .data "public.crt") (index .data "private.key") (index .data "ca.crt")}}present{{end}}',
            ),
            check=False,
        )
        if existing.returncode == 0:
            if existing.stdout.strip() != "present":
                raise DemoFailure(
                    f"existing {OBJECT_STORE_TLS_SECRET} Secret lacks a certificate, key, or CA"
                )
            return

        certificate_dir = Path(tempfile.mkdtemp(prefix="plexus-k8s-minio-tls-"))
        try:
            ca_key = certificate_dir / "ca.key"
            ca_cert = certificate_dir / "ca.crt"
            server_key = certificate_dir / "private.key"
            server_csr = certificate_dir / "server.csr"
            server_cert = certificate_dir / "public.crt"
            extensions = certificate_dir / "server.ext"
            extensions.write_text(
                "subjectAltName=DNS:plexus-local-object-store,"
                "DNS:plexus-local-object-store.plexus-local.svc,"
                "DNS:plexus-local-object-store.plexus-local.svc.cluster.local\n"
                "extendedKeyUsage=serverAuth\n",
                encoding="utf-8",
            )
            self.runner.run(("openssl", "genrsa", "-out", str(ca_key), "2048"))
            self.runner.run(
                (
                    "openssl", "req", "-x509", "-new", "-sha256", "-days", "3650",
                    "-key", str(ca_key), "-subj", "/CN=Plexus local object-store CA",
                    "-out", str(ca_cert),
                )
            )
            self.runner.run(
                (
                    "openssl", "req", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", str(server_key), "-subj", "/CN=plexus-local-object-store",
                    "-out", str(server_csr),
                )
            )
            self.runner.run(
                (
                    "openssl", "x509", "-req", "-sha256", "-days", "825",
                    "-in", str(server_csr), "-CA", str(ca_cert), "-CAkey", str(ca_key),
                    "-CAcreateserial", "-extfile", str(extensions), "-out", str(server_cert),
                )
            )
            self.runner.run(
                (
                    "kubectl", "create", "secret", "generic", OBJECT_STORE_TLS_SECRET,
                    "-n", NAMESPACE,
                    f"--from-file=public.crt={server_cert}",
                    f"--from-file=private.key={server_key}",
                    f"--from-file=ca.crt={ca_cert}",
                )
            )
        finally:
            shutil.rmtree(certificate_dir)

    def _ensure_local_control_plane(self, source: Path) -> None:
        # A tiny temporary harness is used only for its safe port-forward context.
        from docker.demo.core import DemoManifest, generated_run_id

        manifest = DemoManifest.new(generated_run_id(), "guardrail", 1.0, 1)
        harness = DemoHarness(manifest, self.output_dir)
        with harness.port_forward(NAMESPACE, f"svc/{PROXY_SERVICE}", 8000) as base_url:
            client = GraphQLClient(f"{base_url}/graphql", PROXY_API_KEY)
            existing = client.execute(
                "query LocalAccount($id: ID!) { getAccount(id: $id) { id } }", {"id": ACCOUNT_ID}
            ).get("getAccount")
            if existing:
                return
            env = os.environ.copy()
            env.update({
                "PLEXUS_API_URL": f"{base_url}/graphql",
                "PLEXUS_API_KEY": PROXY_API_KEY,
                "PLEXUS_GRAPHQL_AUTH_MODE": "api_key",
            })
            self.runner.run(
                (sys.executable, str(source / "services/private-graphql-proxy/scripts/seed_local_demo.py")),
                timeout=600,
                env=env,
            )

    def _artifact_ticket_smoke(self) -> dict[str, Any]:
        code = (
            "import hashlib,json;"
            "from plexus.dashboard.api.client import PlexusDashboardClient;"
            "from plexus.storage.graphql_artifact_store import ArtifactTicketError,ArtifactTransferRequest,GraphQLArtifactStore;"
            "body=b'plexus-k8s-artifact-smoke';"
            "digest=hashlib.sha256(body).hexdigest();"
            "client=PlexusDashboardClient();store=GraphQLArtifactStore(client);"
            "write=ArtifactTransferRequest(operation='WRITE',resource_type='TASK',resource_id='local-demo-task',artifact_type='TASK_ATTACHMENT',filename='integration-smoke.bin',content_type='application/octet-stream',size_bytes=len(body),sha256=digest);"
            "metadata=store.upload_bytes(write,body);"
            "read=ArtifactTransferRequest(operation='READ',resource_type='TASK',resource_id='local-demo-task',artifact_type='TASK_ATTACHMENT',filename='integration-smoke.bin',content_type='application/octet-stream',size_bytes=len(body),sha256=digest);"
            "downloaded=store.download_bytes(read);"
            "missing=ArtifactTransferRequest(operation='READ',resource_type='TASK',resource_id='missing-task',artifact_type='TASK_ATTACHMENT',filename='integration-smoke.bin',content_type='application/octet-stream',size_bytes=len(body),sha256=digest);"
            "rejected=False;"
            "\ntry: store.request_tickets([missing])\nexcept ArtifactTicketError: rejected=True\n"
            "print(json.dumps({'canonical_key':metadata.get('_s3_key')=='tasks/local-demo-task/integration-smoke.bin','checksum_verified':downloaded==body,'missing_resource_rejected':rejected}))"
        )
        result = self.runner.run(
            (
                "kubectl", "exec", "-n", NAMESPACE,
                "deployment/plexus-plexus-worker", "--", "python", "-c", code,
            ),
            timeout=300,
        )
        payload = extract_last_json(result.stdout)
        required = ("canonical_key", "checksum_verified", "missing_resource_rejected")
        if not all(payload.get(key) is True for key in required):
            raise DemoFailure("in-cluster GraphQL artifact ticket smoke assertions failed")
        return {key: True for key in required}


def write_effective_local_values(
    source: Path,
    destination: Path,
    *,
    worker_tag: str,
    proxy_tag: str,
) -> None:
    values = yaml.safe_load(source.read_text(encoding="utf-8"))
    values["plexus-worker"]["image"] = {
        "repository": "plexus-worker",
        "tag": worker_tag,
        "pullPolicy": "IfNotPresent",
    }
    # The acceptance optimizer evaluates candidates concurrently in-process.
    # Keep its bounded concurrency and measured memory requirement explicit in
    # the immutable values artifact instead of relying on imperative overrides.
    values["plexus-worker"].setdefault("env", {})["MAX_JOBS_PER_WORKER"] = "2"
    values["plexus-worker"]["resources"] = {
        "requests": {"cpu": "500m", "memory": "1Gi"},
        "limits": {"cpu": 2, "memory": "4Gi"},
    }
    values["graphql-proxy"]["image"] = {
        "repository": "plexus-graphql-proxy",
        "tag": proxy_tag,
        "pullPolicy": "IfNotPresent",
    }
    llm = values["plexus-worker"].get("llm") or {}
    if "apiKey" in llm or any(
        isinstance(provider, dict) and provider.get("apiKey")
        for provider in (llm.get("openai"), llm.get("anthropic"))
    ):
        raise DemoFailure("effective local values must not contain LLM API keys")
    destination.write_text(yaml.safe_dump(values, sort_keys=False), encoding="utf-8")
