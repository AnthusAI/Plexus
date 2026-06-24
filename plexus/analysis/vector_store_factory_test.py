"""Tests for topic-memory vector store factory."""

from unittest.mock import patch

import pytest

from plexus.analysis.vector_store_factory import create_topic_memory_vector_store


def test_factory_builds_qdrant_store():
    with patch("plexus.analysis.vector_store_factory.QdrantTopicMemoryVectorStore") as mock_cls:
        mock_instance = object()
        mock_cls.return_value = mock_instance
        store = create_topic_memory_vector_store(
            {
                "provider": "qdrant",
                "qdrant": {
                    "url": "http://localhost:19002",
                    "collection": "topic-memory-local",
                },
            }
        )

    assert store is mock_instance
    mock_cls.assert_called_once_with(
        url="http://localhost:19002",
        collection_name="topic-memory-local",
    )


def test_factory_builds_s3_vectors_store():
    with patch("plexus.analysis.vector_store_factory.TopicMemoryVectorStore") as mock_cls:
        mock_instance = object()
        mock_cls.return_value = mock_instance
        store = create_topic_memory_vector_store(
            {
                "provider": "s3vectors",
                "s3_vectors": {
                    "bucket_name": "bucket",
                    "index_name": "index",
                    "index_arn": "arn:aws:s3vectors:idx",
                    "region": "us-west-2",
                },
            }
        )

    assert store is mock_instance
    mock_cls.assert_called_once_with(
        bucket_name="bucket",
        index_name="index",
        index_arn="arn:aws:s3vectors:idx",
        region="us-west-2",
    )


def test_factory_rejects_unknown_provider():
    with pytest.raises(ValueError) as exc:
        create_topic_memory_vector_store({"provider": "unknown"})
    assert "Unsupported vector store provider" in str(exc.value)
