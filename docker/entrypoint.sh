#!/bin/bash
set -e

# Entrypoint script for Plexus Kubernetes workers
# Supports multiple worker types based on WORKER_TYPE env var or CMD argument

WORKER_TYPE="${WORKER_TYPE:-${1:-score-processor}}"

echo "🚀 Starting Plexus worker: $WORKER_TYPE"

case "$WORKER_TYPE" in
    score-processor)
        echo "📊 Starting score processing worker (SQS-based)"
        # Run the score processor worker
        # This will continuously poll SQS and process scoring jobs
        exec python -m plexus.workers.score_processor_worker
        ;;

    celery)
        echo "🐝 Starting Celery worker"
        # Start Celery worker for task queue processing
        # Configure broker URL via CELERY_BROKER_URL env var
        CELERY_APP="${CELERY_APP:-plexus.workers.celery_app}"
        CELERY_QUEUE="${CELERY_QUEUE:-scoring-requests}"
        CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-4}"
        LOG_LEVEL="${LOG_LEVEL:-info}"

        exec celery -A "$CELERY_APP" worker \
            --loglevel="$LOG_LEVEL" \
            --concurrency="$CELERY_CONCURRENCY" \
            --queues="$CELERY_QUEUE"
        ;;

    console-worker)
        echo "💬 Starting Console chat worker"
        # Run the console local worker for chat message processing
        exec python -m plexus.console.local_worker
        ;;

    *)
        echo "❌ Unknown worker type: $WORKER_TYPE"
        echo "Valid types: score-processor, celery, console-worker"
        exit 1
        ;;
esac
