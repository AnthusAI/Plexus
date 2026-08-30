"""Programmatic scoring entry point for eval pipelines.

This module exposes a thin, dependency-light scoring API that eval pipelines
(scanner corpus eval, CI gates) can call directly without starting a GraphQL
server, seeding scorecard metadata, or importing the dashboard/Evaluation
orchestration stack.

The scoring logic reuses the same span-overlap matching as
``plexus.scores.SourceSpanOverlapScore`` but is invoked as a plain function
over in-memory data, not as a Score class over Items.
"""

from .recall import evaluate_recall

__all__ = ["evaluate_recall"]
