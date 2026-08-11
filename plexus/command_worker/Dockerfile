# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e
# Portable command-worker runtime. Deployment-specific executors are supplied
# through COMMAND_WORKER_EXECUTOR_FACTORY at runtime.
FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5 \
    POETRY_VIRTUALENVS_CREATE=false \
    PLEXUS_NLTK_DATA_DIR=/tmp/nltk_data \
    MPLCONFIGDIR=/tmp/matplotlib \
    PATH="/usr/local/bin:${PATH}"

WORKDIR /app

RUN groupadd --system --gid 10001 plexus && \
    useradd --system --uid 10001 --gid plexus --home-dir /app plexus

COPY pyproject.toml poetry.lock README.md ./
COPY plexus ./plexus

RUN --mount=type=cache,target=/root/.cache/pip \
    apt-get update && \
    # biblicus pulls hdbscan for feedback RCA. On ARM/Python 3.12 there is no
    # wheel, so compile it while building rather than deferring the failure to
    # an enabled command at runtime.
    apt-get install --yes --no-install-recommends build-essential && \
    python -m pip install --upgrade pip "poetry==2.1.3" && \
    # hdbscan's isolated PEP 517 build needs these exact requirements. Prime
    # the shared pip cache before Poetry creates its temporary build venv so a
    # transient PyPI read timeout cannot strand an enabled feedback action.
    python -m pip install --upgrade "cython<4" "numpy<3" && \
    poetry install --only main --extras command-service-runtime --no-interaction --no-ansi && \
    python -c 'from plexus.command_worker.executors.plexus_cli import create_executor; assert create_executor()' && \
    python -m plexus.command_worker.smoke && \
    python -m pip uninstall --yes cython && \
    apt-get purge --yes --auto-remove build-essential && \
    rm -rf /var/lib/apt/lists/*

USER plexus

ENTRYPOINT ["plexus-command-worker"]
