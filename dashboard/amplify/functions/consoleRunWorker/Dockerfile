FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/workspace:/workspace/MCP

WORKDIR /var/task

# Copy repository so the worker can import Plexus source directly.
COPY . /workspace

# The Console agent's model-facing runtime depends on MCP execute_tactus modules.
# Fail the image build if those modules are missing from the context.
RUN test -f /workspace/MCP/tools/tactus_runtime/execute.py && \
    test -f /workspace/MCP/tools/tactus_runtime/_item_helpers.py && \
    test -f /workspace/MCP/server.py

# Required for git-based dependencies (for example openai-cost-calculator).
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install Plexus, Lambda runtime interface client, and required dependencies.
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -e /workspace && \
    python -m pip install --no-cache-dir "python-statemachine>=2.5.0" awslambdaric

COPY dashboard/amplify/functions/consoleRunWorker/app.py /var/task/app.py

ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD ["app.handler"]
