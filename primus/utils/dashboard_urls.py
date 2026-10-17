import os

DEFAULT_PRIMUS_APP_URL = "https://primus.anth.us"


def get_primus_app_base_url() -> str:
    return (os.environ.get("PRIMUS_APP_URL") or DEFAULT_PRIMUS_APP_URL).rstrip("/")


def build_primus_dashboard_url(path: str) -> str:
    return f"{get_primus_app_base_url()}/{path.lstrip('/')}"


def build_evaluation_dashboard_url(evaluation_id: str = "") -> str:
    return build_primus_dashboard_url(f"lab/evaluations/{evaluation_id}".rstrip("/"))


def build_procedure_dashboard_url(procedure_id: str) -> str:
    return build_primus_dashboard_url(f"lab/procedures/{procedure_id}")
