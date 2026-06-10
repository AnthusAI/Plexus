"""
HTTP API entrypoint for synchronous Plexus scoring.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from plexus.workers.scoring_job import ScoringJobError, process_scoring_job_sync

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Plexus Scoring API",
    version="0.1.0",
)


class ScoreRequest(BaseModel):
    scoring_job_id: str = Field(..., min_length=1)
    scorecard: str = Field(..., min_length=1)
    score: str = Field(..., min_length=1)
    item_id: str = Field(..., min_length=1)
    account_key: Optional[str] = Field(default=None, min_length=1)


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> Dict[str, str]:
    return {"status": "ready"}


@app.post("/v1/score")
async def score(request: ScoreRequest) -> JSONResponse:
    try:
        result = await run_in_threadpool(
            process_scoring_job_sync,
            scoring_job_id=request.scoring_job_id,
            scorecard_name=request.scorecard,
            score_name=request.score,
            item_id=request.item_id,
            account_key=request.account_key,
        )
        return JSONResponse(result)
    except ScoringJobError as exc:
        logger.warning(
            "Scoring request failed for scoring_job_id=%s: %s",
            request.scoring_job_id,
            exc,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "scoring_request_failed",
                "message": str(exc),
                "scoring_job_id": request.scoring_job_id,
            },
        )
    except Exception as exc:
        logger.exception(
            "Unexpected scoring failure for scoring_job_id=%s",
            request.scoring_job_id,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "scoring_failed",
                "message": str(exc),
                "scoring_job_id": request.scoring_job_id,
            },
        )
