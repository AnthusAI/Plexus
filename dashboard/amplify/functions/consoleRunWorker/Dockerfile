FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /var/task

# Copy repository so the worker can import Plexus source directly.
COPY . /workspace

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
