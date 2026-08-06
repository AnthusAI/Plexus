# syntax=docker/dockerfile:1.7
# Portable command-worker runtime. Deployment-specific executors are supplied
# through COMMAND_WORKER_EXECUTOR_FACTORY at runtime.
FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system --gid 10001 plexus && \
    useradd --system --uid 10001 --gid plexus --home-dir /app plexus

COPY pyproject.toml poetry.lock README.md ./
COPY plexus ./plexus

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir ".[command-worker]" && \
    plexus-command-worker --help >/dev/null

USER plexus

ENTRYPOINT ["plexus-command-worker"]
