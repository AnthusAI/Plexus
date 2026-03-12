FROM python:3.11-slim

# Install git for pip to clone git repos + runtime deps
RUN apt-get update && apt-get install -y \
    git \
    libpq5 \
    libcurl4 \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

COPY score-processor-lambda/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Download NLTK data during build
RUN python -c "import nltk; nltk.download('punkt', download_dir='/usr/local/share/nltk_data'); nltk.download('punkt_tab', download_dir='/usr/local/share/nltk_data')"

WORKDIR /var/task
COPY plexus/ ./plexus/
COPY score-processor-lambda/handler.py ./handler.py

ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD ["handler.lambda_handler"]
