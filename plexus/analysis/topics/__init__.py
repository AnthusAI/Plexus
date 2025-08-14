"""Topic analysis module for Plexus.

This module contains tools for analyzing topics in text data, including BERTopic implementation
for topic modeling on call transcripts and other text sources.
"""

from .transformer import transform_transcripts, transform_transcripts_llm, transform_transcripts_itemize, inspect_data
# Lazy import: from .analyzer import analyze_topics  # This loads BERTopic/PyTorch, so import only when needed
from .ollama_test import test_ollama_chat

# Import analyze_topics only when actually needed to avoid loading PyTorch at startup
def analyze_topics(*args, **kwargs):
    """Lazy wrapper for analyze_topics to avoid loading PyTorch unless needed."""
    from .analyzer import analyze_topics as _analyze_topics
    return _analyze_topics(*args, **kwargs)

__all__ = [
    'transform_transcripts',
    'transform_transcripts_llm',
    'transform_transcripts_itemize',
    'inspect_data',
    'analyze_topics',
    'test_ollama_chat',
] 