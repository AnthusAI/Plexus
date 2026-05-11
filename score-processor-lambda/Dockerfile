FROM python:3.11-slim

# Install git for pip to clone git repos + runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libpq5 \
    libcurl4 \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/workspace:/workspace/MCP

WORKDIR /var/task

# Copy repository so Plexus can be installed directly from pyproject.toml.
COPY . /workspace

# Install Plexus and Lambda runtime interface client.
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -e /workspace && \
    python -m pip install --no-cache-dir awslambdaric

# Download NLTK data during build
RUN python -c "import nltk; nltk.download('punkt', download_dir='/usr/local/share/nltk_data'); nltk.download('punkt_tab', download_dir='/usr/local/share/nltk_data')"

COPY score-processor-lambda/handler.py ./handler.py

ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD ["handler.lambda_handler"]
