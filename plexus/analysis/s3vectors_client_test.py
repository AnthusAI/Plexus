"""Tests for TopicMemoryVectorStore S3 Vectors client."""

from unittest.mock import MagicMock

import numpy as np

from plexus.analysis.s3vectors_client import EMBEDDING_DIM, TopicMemoryVectorStore


def test_health_check_succeeds():
    mock_client = MagicMock()
    mock_client.get_index.return_value = {"index": {"indexName": "topic-memory-idx-development"}}

    store = TopicMemoryVectorStore(
        bucket_name="plexus-vectors-development",
        index_name="topic-memory-idx-development",
        region="us-west-2",
        client=mock_client,
    )

    assert store.health_check() is True
    mock_client.get_index.assert_called_once()


def test_build_index_puts_vectors():
    mock_client = MagicMock()
    mock_client.list_vectors.return_value = {"vectors": []}

    docs = [
        {
            "doc_id": "d1",
            "text": "hello",
            "embedding": np.zeros(EMBEDDING_DIM, dtype=np.float32),
            "metadata": {"score_id": "s1"},
            "cluster_id": "",
            "cluster_version": "",
            "record_type": "item",
        },
        {
            "doc_id": "d2",
            "text": "world",
            "embedding": np.ones(EMBEDDING_DIM, dtype=np.float32),
            "metadata": {"score_id": "s1"},
            "cluster_id": "",
            "cluster_version": "",
            "record_type": "item",
        },
    ]

    store = TopicMemoryVectorStore(
        bucket_name="plexus-vectors-development",
        index_name="topic-memory-idx-development",
        region="us-west-2",
        client=mock_client,
    )
    result = store.build_index(docs)

    assert result["success_count"] == 2
    assert result["error_count"] == 0
    assert result["new_index_name"] == "topic-memory-idx-development"
    mock_client.put_vectors.assert_called_once()
    put_vectors = mock_client.put_vectors.call_args.kwargs["vectors"]
    assert put_vectors[0]["key"] == "item:d1"
    assert put_vectors[1]["key"] == "item:d2"


def test_build_index_reports_malformed_embeddings():
    mock_client = MagicMock()
    mock_client.list_vectors.return_value = {"vectors": []}

    docs = [
        {"doc_id": "ok", "embedding": np.zeros(EMBEDDING_DIM, dtype=np.float32), "metadata": {}},
        {"doc_id": "bad-none", "embedding": None, "metadata": {}},
        {"doc_id": "bad-short", "embedding": np.zeros(8, dtype=np.float32), "metadata": {}},
    ]

    store = TopicMemoryVectorStore(
        bucket_name="plexus-vectors-development",
        index_name="topic-memory-idx-development",
        region="us-west-2",
        client=mock_client,
    )
    result = store.build_index(docs)

    assert result["success_count"] == 1
    assert result["error_count"] == 2
    assert "bad-none" in result["failed_doc_ids"]
    assert "bad-short" in result["failed_doc_ids"]


def test_bulk_update_cluster_weights_updates_metadata():
    mock_client = MagicMock()
    mock_client.get_vectors.return_value = {
        "vectors": [
            {
                "key": "cluster:5",
                "data": {"float32": [0.1] * EMBEDDING_DIM},
                "metadata": {"record_type": "cluster", "cluster_id": "5"},
            }
        ]
    }

    store = TopicMemoryVectorStore(
        bucket_name="plexus-vectors-development",
        index_name="topic-memory-idx-development",
        region="us-west-2",
        client=mock_client,
    )
    store.bulk_update_cluster_weights(
        [
            {
                "cluster_id": "5",
                "memory_weight": 0.8,
                "memory_tier": "hot",
                "metadata": {"score_id": "97"},
            }
        ]
    )

    mock_client.put_vectors.assert_called_once()
    updated = mock_client.put_vectors.call_args.kwargs["vectors"][0]
    assert updated["key"] == "cluster:5"
    assert updated["metadata"]["memory_weight"] == 0.8
    assert updated["metadata"]["memory_tier"] == "hot"
    assert updated["metadata"]["score_id"] == "97"
