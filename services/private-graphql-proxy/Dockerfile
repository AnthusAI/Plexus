FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/private-graphql-proxy/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/private-graphql-proxy/proxy ./proxy

# Create entrypoint script for database URL construction
# This constructs the PostgreSQL connection URL from individual environment variables
# at runtime, allowing Kubernetes to inject the password from a Secret without
# needing shell variable expansion in the deployment manifest.
# Required env vars: DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
RUN echo '#!/bin/sh\n\
if [ -n "$DB_USER" ] && [ -n "$DB_PASSWORD" ] && [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ] && [ -n "$DB_NAME" ]; then\n\
  export PLEXUS_PROXY_DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"\n\
fi\n\
exec uvicorn proxy.app:app --host 0.0.0.0 --port 8000' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
