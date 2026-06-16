"""Tests for QdrantTopicMemoryVectorStore."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from plexus.analysis.qdrant_vector_store import (
    EMBEDDING_DIM,
    QdrantTopicMemoryVectorStore,
    _to_qdrant_point_id,
)


def test_health_check_creates_missing_collection():
    mock_client = MagicMock()
    mock_client.get_collection.side_effect = [Exception("missing"), {"status": "ok"}]

    store = QdrantTopicMemoryVectorStore(
        url="http://localhost:19002",
        collection_name="topic-memory-local",
        client=mock_client,
    )
    assert store.health_check() is True
    mock_client.create_collection.assert_called_once()


def test_build_index_puts_points():
    mock_client = MagicMock()
    mock_client.get_collection.return_value = {"status": "ok"}
    mock_client.count.return_value = {"count": 2}

    docs = [
        {
            "doc_id": "d1",
            "embedding": np.zeros(EMBEDDING_DIM, dtype=np.float32),
            "metadata": {"score_id": "s1"},
        },
        {
            "doc_id": "d2",
            "embedding": np.ones(EMBEDDING_DIM, dtype=np.float32),
            "metadata": {"score_id": "s1"},
        },
    ]

    store = QdrantTopicMemoryVectorStore(
        url="http://localhost:19002",
        collection_name="topic-memory-local",
        client=mock_client,
    )
    result = store.build_index(docs)

    assert result["success_count"] == 2
    assert result["error_count"] == 0
    assert result["new_index_name"] == "topic-memory-local"
    mock_client.upsert.assert_called_once()
    points = mock_client.upsert.call_args.kwargs["points"]
    assert points[0]["id"] == _to_qdrant_point_id("item:d1")
    assert points[1]["id"] == _to_qdrant_point_id("item:d2")


def test_persist_clusters_puts_cluster_points():
    mock_client = MagicMock()
    mock_client.get_collection.return_value = {"status": "ok"}

    clusters = [
        {
            "cluster_id": "7",
            "centroid_embedding": np.ones(EMBEDDING_DIM, dtype=np.float32),
            "cluster_version": "v1",
            "label": "Address Clarifications",
            "member_count": 3,
            "p95_distance": 0.22,
            "metadata": {"score_id": "97"},
        }
    ]

    store = QdrantTopicMemoryVectorStore(
        url="http://localhost:19002",
        collection_name="topic-memory-local",
        client=mock_client,
    )
    store.persist_clusters(clusters)

    mock_client.upsert.assert_called_once()
    point = mock_client.upsert.call_args.kwargs["points"][0]
    assert point["id"] == _to_qdrant_point_id("cluster:7")
    assert point["payload"]["metadata"]["record_type"] == "cluster"
    assert point["payload"]["metadata"]["score_id"] == "97"


def test_bulk_update_cluster_weights_updates_payload_metadata():
    mock_client = MagicMock()
    mock_client.retrieve.return_value = [
        {
            "id": _to_qdrant_point_id("cluster:5"),
            "vector": [0.1] * EMBEDDING_DIM,
            "payload": {
                "key": "cluster:5",
                "metadata": {"record_type": "cluster", "cluster_id": "5"},
            },
        }
    ]

    store = QdrantTopicMemoryVectorStore(
        url="http://localhost:19002",
        collection_name="topic-memory-local",
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

    mock_client.upsert.assert_called_once()
    point = mock_client.upsert.call_args.kwargs["points"][0]
    assert point["id"] == _to_qdrant_point_id("cluster:5")
    assert point["payload"]["metadata"]["memory_weight"] == 0.8
    assert point["payload"]["metadata"]["memory_tier"] == "hot"
    assert point["payload"]["metadata"]["score_id"] == "97"


def test_find_nearest_clusters_orders_by_similarity_and_applies_threshold():
    mock_client = MagicMock()
    mock_client.search.return_value = [
        SimpleNamespace(
            payload={"key": "cluster:2", "metadata": {"record_type": "cluster", "cluster_id": "2"}},
            score=0.7,
        ),
        SimpleNamespace(
            payload={"key": "cluster:1", "metadata": {"record_type": "cluster", "cluster_id": "1"}},
            score=0.9,
        ),
        SimpleNamespace(
            payload={"key": "item:d1", "metadata": {"record_type": "item"}},
            score=0.99,
        ),
        SimpleNamespace(
            payload={"key": "cluster:3", "metadata": {"record_type": "cluster", "cluster_id": "3"}},
            score=0.2,
        ),
    ]

    store = QdrantTopicMemoryVectorStore(
        url="http://localhost:19002",
        collection_name="topic-memory-local",
        client=mock_client,
    )
    emb = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    results = store.find_nearest_clusters(emb, k=5, threshold=0.5)

    assert [r["cluster_id"] for r in results] == ["1", "2"]
    assert results[0]["similarity_score"] > results[1]["similarity_score"]
    assert results[0]["similarity_score"] == 0.9
    assert results[1]["similarity_score"] == 0.7
