import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / "docker" / "helm" / "plexus-worker"


def render_worker_chart(*set_values, values_file=None, expect_success=True):
    command = [
        "helm",
        "template",
        "test",
        str(CHART),
        "--namespace",
        "test",
    ]
    for value in set_values:
        command.extend(["--set", value])
    if values_file:
        command.extend(["--values", str(values_file)])

    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if expect_success:
        assert result.returncode == 0, result.stderr
        return [doc for doc in yaml.safe_load_all(result.stdout) if doc]
    assert result.returncode != 0
    return result


def find_manifest(docs, kind, name=None):
    for doc in docs:
        if doc.get("kind") != kind:
            continue
        if name is None or doc.get("metadata", {}).get("name") == name:
            return doc
    raise AssertionError(f"Could not find {kind}/{name or '*'}")


def container_env(deployment):
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    return {entry["name"]: entry for entry in container.get("env", [])}


def test_scoring_api_renders_service_gateway_and_route():
    docs = render_worker_chart(
        "workerType=scoring-api",
        "service.enabled=true",
        "scoringApi.gateway.enabled=true",
    )

    service = find_manifest(docs, "Service", "test-plexus-worker")
    assert service["spec"]["selector"]["worker-type"] == "scoring-api"
    assert service["spec"]["ports"][0]["targetPort"] == "http"

    gateway = find_manifest(docs, "Gateway", "test-plexus-worker-gateway")
    assert gateway["spec"]["gatewayClassName"] == "envoy-gateway"

    route = find_manifest(docs, "HTTPRoute", "test-plexus-worker-route")
    assert route["spec"]["rules"][0]["matches"][0]["path"] == {
        "type": "PathPrefix",
        "value": "/v1/score",
    }
    assert route["spec"]["rules"][0]["backendRefs"][0]["name"] == "test-plexus-worker"


def test_celery_broker_secret_only_renders_for_celery_mode():
    scoring_docs = render_worker_chart("workerType=scoring-api")
    assert not [
        doc
        for doc in scoring_docs
        if doc.get("kind") == "Secret"
        and doc.get("metadata", {}).get("name") == "test-plexus-worker-celery-secrets"
    ]

    celery_docs = render_worker_chart("workerType=celery", "celery.broker.url=amqp://example")
    celery_secret = find_manifest(celery_docs, "Secret", "test-plexus-worker-celery-secrets")
    assert celery_secret["stringData"]["broker-url"] == "amqp://example"
    env = container_env(find_manifest(celery_docs, "Deployment", "test-plexus-worker"))
    assert "CELERY_BROKER_URL" in env


def test_worker_type_is_not_part_of_deployment_selector_labels():
    docs = render_worker_chart("workerType=scoring-api")
    deployment = find_manifest(docs, "Deployment", "test-plexus-worker")

    assert "worker-type" not in deployment["spec"]["selector"]["matchLabels"]
    assert deployment["spec"]["template"]["metadata"]["labels"]["worker-type"] == "scoring-api"


def test_scoring_api_auth_uses_separate_secret_key_and_fail_closed_env():
    docs = render_worker_chart(
        "workerType=scoring-api",
        "scoringApi.auth.enabled=true",
        "scoringApi.auth.apiKey=test-inbound-key",
    )

    secret = find_manifest(docs, "Secret", "test-plexus-worker-secrets")
    assert secret["stringData"]["scoring-api-key"] == "test-inbound-key"
    assert "x-plexus-scoring-api-key" not in secret["stringData"]

    env = container_env(find_manifest(docs, "Deployment", "test-plexus-worker"))
    assert env["SCORING_API_AUTH_REQUIRED"]["value"] == "true"
    assert env["SCORING_API_KEY"]["valueFrom"]["secretKeyRef"] == {
        "name": "test-plexus-worker-secrets",
        "key": "scoring-api-key",
    }


def test_missing_worker_api_url_fails_render(tmp_path):
    values_file = tmp_path / "missing-api-url.yaml"
    values_file.write_text(
        """
plexus:
  api:
    url: ""
global:
  services:
    graphqlProxy:
      host: ""
      port: ""
      path: "/graphql"
""".strip()
    )

    result = render_worker_chart(values_file=values_file, expect_success=False)

    assert "worker API URL" in result.stderr


def test_non_local_environment_rejects_mutable_worker_image_tag():
    result = render_worker_chart(
        "global.environment=production",
        "image.tag=latest",
        expect_success=False,
    )

    assert "image.tag must be immutable" in result.stderr


def test_non_local_environment_accepts_immutable_worker_image_tag():
    docs = render_worker_chart(
        "global.environment=production",
        "image.tag=git-sha-abcdef1",
    )

    deployment = find_manifest(docs, "Deployment", "test-plexus-worker")
    image = deployment["spec"]["template"]["spec"]["containers"][0]["image"]
    assert image == "plexus-worker:git-sha-abcdef1"
