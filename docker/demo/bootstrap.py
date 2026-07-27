from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
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
    OPENAI_SECRET,
    PROXY_SERVICE,
    RELEASE,
    CommandRunner,
    DemoFailure,
    DemoHarness,
    GraphQLClient,
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
            return {
                "git_head": head,
                "image_tag": tag,
                "envoy_gateway": ENVOY_VERSION,
                "chart_package": str(chart_package.resolve()),
                "values_file": str(values.resolve()),
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

    def _ensure_local_control_plane(self, source: Path) -> None:
        # A tiny temporary harness is used only for its safe port-forward context.
        from docker.demo.core import DemoManifest, generated_run_id

        manifest = DemoManifest.new(generated_run_id(), "guardrail", 1.0, 1)
        harness = DemoHarness(manifest, self.output_dir)
        with harness.port_forward(NAMESPACE, f"svc/{PROXY_SERVICE}", 8000) as base_url:
            client = GraphQLClient(f"{base_url}/graphql")
            existing = client.execute(
                "query LocalAccount($id: ID!) { getAccount(id: $id) { id } }", {"id": ACCOUNT_ID}
            ).get("getAccount")
            if existing:
                return
            env = os.environ.copy()
            env.update({"PLEXUS_API_URL": f"{base_url}/graphql", "PLEXUS_API_KEY": ""})
            self.runner.run(
                (sys.executable, str(source / "services/private-graphql-proxy/scripts/seed_local_demo.py")),
                timeout=600,
                env=env,
            )


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
