from primus.utils.dashboard_urls import (
    DEFAULT_PRIMUS_APP_URL,
    build_evaluation_dashboard_url,
    build_procedure_dashboard_url,
)


def test_evaluation_url_uses_configured_app_url_without_double_slash(monkeypatch):
    monkeypatch.setenv("PRIMUS_APP_URL", "https://lab.example.com/")
    assert build_evaluation_dashboard_url("eval-123") == "https://lab.example.com/lab/evaluations/eval-123"


def test_evaluation_list_url_when_no_evaluation_id(monkeypatch):
    monkeypatch.setenv("PRIMUS_APP_URL", "https://lab.example.com")
    assert build_evaluation_dashboard_url() == "https://lab.example.com/lab/evaluations"


def test_procedure_url_falls_back_to_default_app_url(monkeypatch):
    monkeypatch.delenv("PRIMUS_APP_URL", raising=False)
    assert build_procedure_dashboard_url("proc-1") == f"{DEFAULT_PRIMUS_APP_URL}/lab/procedures/proc-1"
