from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / "docker" / "helm" / "plexus-worker"


def read_template(name: str) -> str:
    return (CHART / "templates" / name).read_text()


def test_scoring_api_templates_create_service_gateway_and_route():
    service = read_template("service.yaml")
    gateway = read_template("gateway.yaml")
    route = read_template("httproute.yaml")

    assert 'eq .Values.workerType "scoring-api"' in service
    assert "kind: Service" in service
    assert "targetPort: {{ .Values.service.targetPort }}" in service

    assert 'eq .Values.workerType "scoring-api"' in gateway
    assert "kind: Gateway" in gateway
    assert "gatewayClassName:" in gateway

    assert 'eq .Values.workerType "scoring-api"' in route
    assert "kind: HTTPRoute" in route
    assert "pathPrefix" in route
    assert "backendRefs:" in route


def test_celery_secret_is_only_created_for_celery_mode():
    secret = read_template("secret.yaml")
    deployment = read_template("deployment.yaml")

    assert 'eq .Values.workerType "celery"' in secret
    assert 'if eq .Values.workerType "celery"' in deployment
    assert "CELERY_BROKER_URL" in deployment
    assert "broker-url" in secret
