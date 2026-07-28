FROM public.ecr.aws/docker/library/python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/workspace:/workspace/MCP

WORKDIR /var/task

# Required for git-based dependencies (for example openai-cost-calculator).
# Keep this before the source copy so normal worker code edits reuse the layer.
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Copy repository so the worker can import Plexus source directly.
COPY . /workspace

# The Console agent's model-facing runtime depends on MCP execute_tactus modules.
# Fail the image build if those modules are missing from the context.
RUN test -f /workspace/MCP/tools/tactus_runtime/execute.py && \
    test -f /workspace/MCP/tools/tactus_runtime/_item_helpers.py && \
    test -f /workspace/MCP/server.py && \
    test -f /workspace/plexus/procedures/console/chat_agent.tac

# Install Plexus, Lambda runtime interface client, and required dependencies.
# `plexus.score.test` imports the Celery-backed score-task module even when it
# runs synchronously, so the Console's post-submit verification needs Celery
# in addition to the lightweight scoring extra. Console-specific optional
# dependencies are declared by the package instead of resolved ad hoc here.
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --progress-bar off --upgrade pip && \
    python -m pip install --progress-bar off -e "/workspace[scoring,console]" awslambdaric && \
    python -c "import awslambdaric, boto3, celery, fastmcp, requests_aws4auth"

COPY dashboard/amplify/functions/consoleRunWorker/app.py /var/task/app.py

ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD ["app.handler"]
