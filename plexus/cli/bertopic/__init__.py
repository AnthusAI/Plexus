"""
BERTopic module for topic modeling on call transcripts.

This module is deprecated and redirects to the new location at 'plexus.analysis.topics'.
Use 'plexus.analysis.topics' instead.
"""

from plexus.analysis.topics import (
    transform_transcripts,
    transform_transcripts_llm,
    transform_transcripts_itemize,
    inspect_data,
    analyze_topics,
    test_ollama_chat
)

__all__ = [
    'transform_transcripts',
    'transform_transcripts_llm',
    'transform_transcripts_itemize',
    'inspect_data',
    'analyze_topics',
    'test_ollama_chat',
] 