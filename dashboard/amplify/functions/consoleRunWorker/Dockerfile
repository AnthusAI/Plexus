FROM public.ecr.aws/lambda/python:3.12

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /var/task

# Copy repository so the worker can import Plexus source directly.
COPY . /workspace

# Required for git-based dependencies (for example openai-cost-calculator).
RUN dnf install -y git && dnf clean all && rm -rf /var/cache/dnf

# Install Plexus and dependencies required for procedure execution.
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -e /workspace && \
    python -m pip install --no-cache-dir "python-statemachine>=2.5.0"

COPY dashboard/amplify/functions/consoleRunWorker/app.py /var/task/app.py

CMD ["app.handler"]
