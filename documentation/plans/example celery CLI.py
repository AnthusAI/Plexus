#!/usr/bin/env python3
# /// script
# dependencies = [
#     "click>=8.1.7",
#     "celery>=5.3.6",
#     "python-dotenv>=1.0.0",
#     "boto3>=1.34.0",
#     "botocore>=1.34.0",
#     "kombu[sqs]>=5.3.4",
# ]
# ///

import os
from typing import Any
import click
from celery import Celery
from dotenv import load_dotenv
from kombu.utils.url import safequote

load_dotenv()

aws_access_key = safequote(os.getenv("CELERY_AWS_ACCESS_KEY_ID"))
aws_secret_key = safequote(os.getenv("CELERY_AWS_SECRET_ACCESS_KEY"))

broker_url = "sqs://{aws_access_key}:{aws_secret_key}@".format(
    aws_access_key=aws_access_key,
    aws_secret_key=aws_secret_key,
    aws_region_name=os.getenv("CELERY_AWS_REGION_NAME"),
)
print("BROKER URL", broker_url)

backend_url_template = os.getenv("CELERY_RESULT_BACKEND_TEMPLATE")
backend_url = backend_url_template.format(
    aws_access_key=aws_access_key,
    aws_secret_key=aws_secret_key,
    aws_region_name=os.getenv("CELERY_AWS_REGION_NAME")
)
print("BACKEND URL", backend_url)

celery_app = Celery(
    "plexus-celery-tasks", 
    broker=broker_url,
    broker_transport_options = {'region': os.getenv("CELERY_AWS_REGION_NAME")},
    backend=backend_url,
)

@celery_app.task
def example_task(message: str) -> dict[str, Any]:
    return {"message": f"Processed: {message}"}

@click.group()
def cli() -> None:
    pass

@cli.command()
@click.argument("message")
def send(message: str) -> None:
    task_result = example_task.delay(message)
    click.echo(f"Task dispatched with ID: {task_result.id}")

@cli.command()
def worker() -> None:
    argv = [
        "worker",
        "--loglevel=DEBUG",
    ]
    celery_app.worker_main(argv)

if __name__ == "__main__":
    cli() 