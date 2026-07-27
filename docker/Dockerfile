# syntax=docker/dockerfile:1.7
# Kubernetes-ready Plexus Worker Image
#
# This image can run multiple worker types:
# - Score processing worker (SQS-based)
# - Celery worker (RabbitMQ/Redis)
# - Console chat worker (polling-based)
#
# Use environment variables or CMD override to select worker type

FROM python:3.11-slim

# Add metadata labels
LABEL maintainer="Anthus AI <engineering@anthus.ai>" \
      description="Plexus Worker for Kubernetes" \
      version="1.52.0"

# Install system dependencies
# Build dependencies needed for Python packages with C extensions (hdbscan, etc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libpq5 \
    libcurl4 \
    graphviz \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r plexus --gid=1000 && \
    useradd -r -g plexus --uid=1000 --home-dir=/app --shell=/bin/bash plexus

# Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copy repository for local installation
COPY --chown=plexus:plexus . /app

# Install the scoring, evaluation, and infrastructure extras.
# The ML training stack (torch, transformers, xgboost, ...) is excluded;
# evaluation includes only the local embeddings required for feedback RCA.
ARG PLEXUS_EXTRAS="scoring,evaluation,infra"
# PyPI's Linux ARM64 torch distribution includes CUDA runtime packages.  The
# Docker Desktop worker is CPU-only, so install the matching CPU wheel first;
# the sentence-transformers dependency then reuses it instead of downloading a
# multi-gigabyte GPU stack.
ARG TORCH_CPU_VERSION="2.7.1"
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    python -m pip install --index-url https://download.pytorch.org/whl/cpu "torch==${TORCH_CPU_VERSION}+cpu" && \
    python -m pip install -e ".[$PLEXUS_EXTRAS]" && \
    python -c "import importlib.util; from importlib.metadata import version; from pathlib import Path; importlib.util.find_spec('virtuus') and Path('/usr/local/lib/VERSION').write_text(version('virtuus') + '\\n', encoding='utf-8')"

# Download NLTK data during build (required for some scoring operations)
RUN python -c "import nltk; \
    nltk.download('punkt', download_dir='/usr/local/share/nltk_data'); \
    nltk.download('punkt_tab', download_dir='/usr/local/share/nltk_data')"

# Set NLTK data path
ENV NLTK_DATA=/usr/local/share/nltk_data

# Create directories for runtime data with appropriate permissions
RUN mkdir -p /app/data /app/logs /app/tmp && \
    chown -R plexus:plexus /app/data /app/logs /app/tmp && \
    chmod 750 /app/data /app/logs /app/tmp

# Set working directory for scorecard cache
ENV SCORECARD_CACHE_DIR=/app/data/scorecards

# Set entrypoint script permissions (already copied with COPY . /app above)
RUN chmod 750 /app/docker/entrypoint.sh

# Switch to non-root user
USER plexus

# Health check endpoint (optional, can be customized per worker type)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default to score processing worker
# Override with environment variable WORKER_TYPE or CMD
ENV WORKER_TYPE=score-processor

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["score-processor"]
