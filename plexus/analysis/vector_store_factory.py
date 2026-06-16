"""
Factory helpers for topic-memory vector store providers.
"""

from __future__ import annotations

from typing import Any, Dict

from plexus.analysis.qdrant_vector_store import QdrantTopicMemoryVectorStore
from plexus.analysis.s3vectors_client import TopicMemoryVectorStore


def create_topic_memory_vector_store(config: Dict[str, Any]) -> Any:
    """
    Build a topic-memory vector store from normalized provider config.

    Expected config keys:
    - provider: "s3vectors" | "qdrant"
    - s3_vectors: { bucket_name, index_name, index_arn, region }
    - qdrant: { url, collection }
    """
    provider = (config.get("provider") or "s3vectors").strip().lower()

    if provider == "qdrant":
        qdrant = dict(config.get("qdrant", {}) or {})
        return QdrantTopicMemoryVectorStore(
            url=str(qdrant.get("url", "http://localhost:6333")),
            collection_name=str(qdrant.get("collection", "topic-memory-local")),
        )

    if provider == "s3vectors":
        s3_vectors = dict(config.get("s3_vectors", {}) or {})
        return TopicMemoryVectorStore(
            bucket_name=str(s3_vectors.get("bucket_name", "")),
            index_name=str(s3_vectors.get("index_name", "")),
            index_arn=s3_vectors.get("index_arn"),
            region=str(s3_vectors.get("region", "us-west-2")),
        )

    raise ValueError(
        f"Unsupported vector store provider '{provider}'. "
        "Expected one of: s3vectors, qdrant."
    )
