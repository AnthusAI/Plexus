"""
Celery application for Plexus workers.

This module provides a Celery app that can be used to process scoring requests
from RabbitMQ queues. It's designed to work in Kubernetes with the private
GraphQL proxy for data storage.
"""

import os
import logging
from celery import Celery
from kombu import Queue, Exchange

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create Celery app
broker_url = os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "rpc://")

app = Celery(
    "plexus",
    broker=broker_url,
    backend=result_backend,
    include=[
        "plexus.workers.celery_tasks",
        "plexus.cli.score_chat.celery"
    ]
)

# Celery configuration
app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Result backend settings
    result_expires=3600,  # 1 hour
    result_persistent=False,

    # Worker settings
    worker_prefetch_multiplier=int(os.getenv("CELERY_PREFETCH_MULTIPLIER", "4")),
    worker_max_tasks_per_child=int(os.getenv("MAX_JOBS_PER_WORKER", "100")),
    worker_disable_rate_limits=True,

    # Queue settings
    task_default_queue=os.getenv("CELERY_QUEUE", "scoring-requests"),
    task_default_exchange="plexus",
    task_default_exchange_type="topic",
    task_default_routing_key="scoring.request",

    # Define queues
    task_queues=(
        Queue(
            os.getenv("CELERY_QUEUE", "scoring-requests"),
            Exchange("plexus", type="topic"),
            routing_key="scoring.#"
        ),
    ),

    # Task routing
    task_routes={
        "plexus.workers.celery_tasks.process_scoring_job": {
            "queue": os.getenv("CELERY_QUEUE", "scoring-requests"),
            "routing_key": "scoring.request"
        },
        "plexus.score_chat.message": {
            "queue": "chat-messages",
            "routing_key": "scoring.chat"
        },
    },

    # Error handling
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
)

logger.info(f"Celery app initialized with broker: {broker_url}")
logger.info(f"Default queue: {app.conf.task_default_queue}")
logger.info(f"Worker max tasks per child: {app.conf.worker_max_tasks_per_child}")

if __name__ == "__main__":
    app.start()
