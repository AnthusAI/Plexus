"""
Shared constants for Plexus infrastructure.

This module contains constants that are used across multiple stacks.
"""

# ECR Repository Name Template (without environment suffix)
LAMBDA_SCORE_PROCESSOR_REPOSITORY_BASE = "plexus/lambda/score-processor"
CONSOLE_WORKER_REPOSITORY_BASE = "plexus-console-worker"
COMMAND_WORKER_REPOSITORY_BASE = "plexus-command-worker"

# AWS Region
DEFAULT_REGION = "us-west-2"
