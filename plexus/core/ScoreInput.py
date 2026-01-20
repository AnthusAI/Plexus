"""
Lightweight Score.Input class definition.

This module contains only the Score.Input class without any heavyweight dependencies,
allowing it to be imported without triggering psycopg or other complex imports.
"""

from pydantic import BaseModel
from typing import Optional, List, Any


class ScoreInput(BaseModel):
    """
    Standard input structure for all Score classifications in Plexus.

    The Input class standardizes how content is passed to Score classifiers,
    supporting both the content itself and contextual metadata.

    Attributes:
        text: The content to classify. Can be a transcript, document, etc.
        metadata: Additional context like source, timestamps, or tracking IDs
        results: Optional list of previous classification results
    """
    text: str
    metadata: dict = {}
    results: Optional[List[Any]] = None
