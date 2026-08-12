# syntax=docker/dockerfile:1.7
FROM public.ecr.aws/lambda/python:3.12@sha256:da65e34b539ef0ac96c700d106565d18b1b650b6ba5290a8a79d5f97945d52b1 AS build

ARG PLEXUS_REF

ENV PATH=/opt/plexus-venv/bin:${PATH} \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/plexus-venv

RUN dnf install -y git && dnf clean all

RUN python -m venv "${VIRTUAL_ENV}" && \
    python -m pip install --no-cache-dir "poetry==2.3.2"

RUN --mount=type=secret,id=github_token \
    printf '%s' "${PLEXUS_REF}" | grep -Eq '^[0-9a-f]{40}$' && \
    GITHUB_TOKEN="$(cat /run/secrets/github_token)" && \
    test -n "${GITHUB_TOKEN}" && \
    git config --global url."https://x-access-token:${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/" && \
    mkdir -p /workspace/plexus && \
    cd /workspace/plexus && \
    git init && \
    git remote add origin https://github.com/AnthusAI/Plexus.git && \
    git fetch --depth=1 origin "${PLEXUS_REF}" && \
    git checkout --detach FETCH_HEAD && \
    test "$(git rev-parse HEAD)" = "${PLEXUS_REF}" && \
    poetry install --only main --extras scoring --no-root --no-ansi --compile && \
    poetry build --format wheel --output /tmp/plexus-dist && \
    python -m pip install --no-cache-dir --no-deps /tmp/plexus-dist/plexus-*.whl && \
    git config --global --unset-all url."https://x-access-token:${GITHUB_TOKEN}@github.com/".insteadOf && \
    rm -f /root/.gitconfig && \
    rm -rf /root/.cache /workspace/plexus "${VIRTUAL_ENV}/src"

RUN python -c "import nltk; nltk.download('punkt', download_dir='/opt/nltk_data'); nltk.download('punkt_tab', download_dir='/opt/nltk_data')"

FROM public.ecr.aws/lambda/python:3.12@sha256:da65e34b539ef0ac96c700d106565d18b1b650b6ba5290a8a79d5f97945d52b1

ARG PLEXUS_REF

LABEL org.opencontainers.image.source="https://github.com/AnthusAI/Plexus" \
      org.opencontainers.image.revision="${PLEXUS_REF}"

ENV NLTK_DATA=/usr/local/share/nltk_data:/tmp/nltk_data \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=build /opt/plexus-venv/lib/python3.12/site-packages ${LAMBDA_TASK_ROOT}
COPY --from=build /opt/nltk_data /usr/local/share/nltk_data

CMD ["plexus.runtime.async_score_processor.handler.lambda_handler"]
