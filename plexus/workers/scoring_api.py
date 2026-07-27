"""
HTTP API entrypoint for synchronous Plexus scoring.
"""

import json
import logging
import os
import secrets
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from plexus.workers.scoring_job import ScoringJobError, process_scoring_job_sync

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)


class ScoreRequest(BaseModel):
    scoring_job_id: str = Field(..., min_length=1)
    scorecard: str = Field(..., min_length=1)
    score: str = Field(..., min_length=1)
    item_id: str = Field(..., min_length=1)
    account_key: Optional[str] = Field(default=None, min_length=1)


def env_flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def scoring_api_auth_required() -> bool:
    return env_flag_enabled("SCORING_API_AUTH_REQUIRED")


def proxy_readiness_url(api_url: str) -> str:
    """Return the proxy readiness endpoint for a local GraphQL API URL."""
    parsed = urlsplit(api_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("PLEXUS_API_URL must be an absolute URL")
    return urlunsplit((parsed.scheme, parsed.netloc, "/readyz", "", ""))


def graphql_proxy_is_ready() -> bool:
    """Check the local proxy when the deployment explicitly requires it."""
    if not env_flag_enabled("PLEXUS_SCORING_REQUIRE_PROXY_READY"):
        return True
    api_url = os.getenv("PLEXUS_API_URL", "")
    try:
        request = Request(proxy_readiness_url(api_url), method="GET")
        with urlopen(request, timeout=2) as response:
            return response.status == 200
    except (HTTPError, URLError, TimeoutError, ValueError):
        return False


def log_auth_configuration() -> None:
    if os.getenv("SCORING_API_KEY"):
        logger.info("Scoring API inbound authentication is enabled")
        return
    if scoring_api_auth_required():
        logger.error("Scoring API inbound authentication is required but SCORING_API_KEY is not set")
    else:
        logger.warning("Scoring API inbound authentication is disabled because SCORING_API_KEY is not set")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log_auth_configuration()
    yield


app = FastAPI(
    title="Plexus Scoring API",
    version="0.1.0",
    lifespan=lifespan,
)


def require_scoring_api_key(
    scoring_api_key: Optional[str] = Header(default=None, alias="x-plexus-scoring-api-key"),
) -> None:
    expected_api_key = os.getenv("SCORING_API_KEY")
    if not expected_api_key:
        if scoring_api_auth_required():
            raise HTTPException(status_code=503, detail="Scoring API authentication is not configured.")
        return
    if not scoring_api_key or not secrets.compare_digest(scoring_api_key, expected_api_key):
        raise HTTPException(status_code=401, detail="Invalid scoring API key.")


def public_error_message(status_code: int) -> str:
    if status_code == 404:
        return "Requested scoring resource was not found."
    if status_code == 409:
        return "Scoring request is already being processed or conflicts with persisted state."
    if status_code < 500:
        return "Scoring request is invalid."
    return "Scoring request could not be processed."


def _make_json_safe(obj: Any) -> Any:
    """Recursively convert non-serializable types (datetime, Pydantic models) for JSON output."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return _make_json_safe(obj.model_dump())
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(item) for item in obj]
    return obj


def scoring_error_reason_code(error: ScoringJobError) -> str:
    if error.reason_code:
        return error.reason_code
    if error.status_code == 404:
        return "resource_not_found"
    if error.status_code == 400:
        return "invalid_request"
    if error.status_code >= 500:
        return "scoring_server_error"
    return "scoring_request_failed"


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> Dict[str, str]:
    if not graphql_proxy_is_ready():
        raise HTTPException(status_code=503, detail="GraphQL proxy is not ready.")
    return {"status": "ready"}


@app.post("/v1/score", dependencies=[Depends(require_scoring_api_key)])
async def score(request: ScoreRequest) -> JSONResponse:
    request_id = uuid4().hex
    try:
        result = await run_in_threadpool(
            process_scoring_job_sync,
            scoring_job_id=request.scoring_job_id,
            scorecard_name=request.scorecard,
            score_name=request.score,
            item_id=request.item_id,
            account_key=request.account_key,
        )
        return JSONResponse(_make_json_safe(result))
    except ScoringJobError as exc:
        logger.warning(
            "Scoring request failed request_id=%s status_code=%s reason_code=%s",
            request_id,
            exc.status_code,
            scoring_error_reason_code(exc),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "scoring_request_failed",
                "reason_code": scoring_error_reason_code(exc),
                "message": public_error_message(exc.status_code),
                "scoring_job_id": request.scoring_job_id,
                "request_id": request_id,
            },
        )
    except Exception:
        logger.exception(
            "Unexpected scoring failure request_id=%s",
            request_id,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "scoring_failed",
                "message": "Unexpected scoring failure.",
                "scoring_job_id": request.scoring_job_id,
                "request_id": request_id,
            },
        )
