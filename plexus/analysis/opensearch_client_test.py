"""Tests for TopicMemoryIndex OpenSearch client."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from plexus.analysis.opensearch_client import (
    EMBEDDING_DIM,
    LIVE_ALIAS,
    TopicMemoryIndex,
)


@pytest.fixture
def mock_client():
    return MagicMock()


def test_client_initializes_with_endpoint_and_region(mock_client):
    """TopicMemoryIndex constructs with endpoint and region, no exception."""
    idx = TopicMemoryIndex(
        endpoint="search-xxx.us-west-2.es.amazonaws.com",
        region="us-west-2",
        client=mock_client,
    )
    assert idx.endpoint == "search-xxx.us-west-2.es.amazonaws.com"
    assert idx.region == "us-west-2"
    assert idx._client is mock_client


def test_health_check_succeeds(mock_client):
    """Health check returns True when cluster is green."""
    mock_client.cluster.health.return_value = {"status": "green"}
    idx = TopicMemoryIndex(endpoint="x", region="us-west-2", client=mock_client)
    assert idx.health_check() is True


def test_health_check_fails_on_connection_error(mock_client):
    """Health check returns False when cluster is unreachable."""
    mock_client.cluster.health.side_effect = ConnectionError("unreachable")
    idx = TopicMemoryIndex(endpoint="x", region="us-west-2", client=mock_client)
    assert idx.health_check() is False


def test_health_check_yellow_is_healthy(mock_client):
    """Health check returns True for yellow status."""
    mock_client.cluster.health.return_value = {"status": "yellow"}
    idx = TopicMemoryIndex(endpoint="x", region="us-west-2", client=mock_client)
    assert idx.health_check() is True


def test_build_index_creates_timestamped_index(mock_client):
    """build_index creates index matching topic-memory-YYYYMMDD-HHMMSS."""
    mock_client.indices.create.return_value = {"acknowledged": True}
    mock_client.bulk.return_value = {"errors": False}
    mock_client.indices.get_alias.side_effect = Exception("no alias")
    docs = [
        {
            "doc_id": f"d{i}",
            "text": "hello",
            "embedding": np.zeros(EMBEDDING_DIM, dtype=np.float32),
            "metadata": {},
            "cluster_id": "",
            "cluster_version": "",
            "record_type": "item",
        }
        for i in range(3)
    ]
    idx = TopicMemoryIndex(endpoint="x", region="us-west-2", client=mock_client)
    result = idx.build_index(docs)
    mock_client.indices.create.assert_called_once()
    call_kwargs = mock_client.indices.create.call_args[1]
    index_name = call_kwargs.get("index", "")
    assert index_name.startswith("topic-memory-")
    assert result["success_count"] == 3
    assert result["error_count"] == 0


def test_build_index_calls_bulk(mock_client):
    """Bulk API is called with documents."""
    mock_client.indices.create.return_value = {"acknowledged": True}
    mock_client.bulk.return_value = {"errors": False}
    mock_client.indices.get_alias.side_effect = Exception("no alias")
    docs = [
        {
            "doc_id": "d1",
            "text": "hello",
            "embedding": np.zeros(EMBEDDING_DIM, dtype=np.float32),
            "metadata": {},
            "cluster_id": "c1",
            "cluster_version": "v1",
            "record_type": "item",
        }
    ]
    idx = TopicMemoryIndex(endpoint="x", region="us-west-2", client=mock_client)
    idx.build_index(docs)
    mock_client.bulk.assert_called_once()
    body = mock_client.bulk.call_args[1]["body"]
    assert len(body) >= 2
    assert body[0]["index"]["_id"] == "d1"
    assert "embedding" in body[1]


def test_swap_alias_remove_add_delete(mock_client):
    """swap_alias does update_aliases then delete old index."""
    idx = TopicMemoryIndex(endpoint="x", region="us-west-2", client=mock_client)
    idx.swap_alias("topic-memory-new", "topic-memory-old")
    mock_client.indices.update_aliases.assert_called_once()
    actions = mock_client.indices.update_aliases.call_args[1]["body"]["actions"]
    assert {"remove": {"index": "topic-memory-old", "alias": LIVE_ALIAS}} in actions
    assert {"add": {"index": "topic-memory-new", "alias": LIVE_ALIAS}} in actions
    mock_client.indices.delete.assert_called_once_with(index="topic-memory-old")


def test_partial_bulk_failures_reported(mock_client):
    """Malformed embeddings produce error_count and failed_doc_ids."""
    mock_client.indices.create.return_value = {"acknowledged": True}
    mock_client.bulk.return_value = {"errors": False}
    mock_client.indices.get_alias.side_effect = Exception("no alias")
    docs = [
        {"doc_id": "d1", "text": "a", "embedding": np.zeros(EMBEDDING_DIM), "metadata": {}},
        {"doc_id": "d2", "text": "b", "embedding": None, "metadata": {}},
        {"doc_id": "d3", "text": "c", "embedding": np.zeros(10), "metadata": {}},
        {"doc_id": "d4", "text": "d", "embedding": np.zeros(EMBEDDING_DIM), "metadata": {}},
    ]
    idx = TopicMemoryIndex(endpoint="x", region="us-west-2", client=mock_client)
    result = idx.build_index(docs)
    assert result["success_count"] == 2
    assert result["error_count"] == 2
    assert "d2" in result["failed_doc_ids"]
    assert "d3" in result["failed_doc_ids"]


def test_find_nearest_clusters_returns_k_results(mock_client):
    """KNN search returns k results with cluster_id, doc_id, similarity_score."""
    mock_client.search.return_value = {
        "hits": {
            "hits": [
                {"_score": 0.9, "_source": {"cluster_id": "c1", "doc_id": "d1"}, "_id": "d1"},
                {"_score": 0.8, "_source": {"cluster_id": "c2", "doc_id": "d2"}, "_id": "d2"},
            ]
        }
    }
    idx = TopicMemoryIndex(endpoint="x", region="us-west-2", client=mock_client)
    emb = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    results = idx.find_nearest_clusters(emb, k=5)
    assert len(results) == 2
    assert results[0]["cluster_id"] == "c1"
    assert results[0]["doc_id"] == "d1"
    assert results[0]["similarity_score"] == 0.9
    assert results[1]["similarity_score"] == 0.8


def test_find_nearest_clusters_threshold_filters(mock_client):
    """Threshold filters low-similarity results."""
    mock_client.search.return_value = {
        "hits": {
            "hits": [
                {"_score": 0.9, "_source": {"cluster_id": "c1", "doc_id": "d1"}, "_id": "d1"},
                {"_score": 0.4, "_source": {"cluster_id": "c2", "doc_id": "d2"}, "_id": "d2"},
                {"_score": 0.6, "_source": {"cluster_id": "c3", "doc_id": "d3"}, "_id": "d3"},
            ]
        }
    }
    idx = TopicMemoryIndex(endpoint="x", region="us-west-2", client=mock_client)
    emb = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    results = idx.find_nearest_clusters(emb, k=5, threshold=0.5)
    assert len(results) == 2
    assert results[0]["similarity_score"] == 0.9
    assert results[1]["similarity_score"] == 0.6


def test_persist_clusters_bulk_indexes(mock_client):
    """persist_clusters bulk-indexes cluster records with record_type=cluster."""
    clusters = [
        {
            "doc_id": "cluster-1",
            "cluster_id": "1",
            "centroid_embedding": [0.1] * 384,
            "p95_distance": 0.5,
            "label": "Topic 1",
            "member_count": 10,
            "cluster_version": "v1",
            "record_type": "cluster",
        },
        {
            "doc_id": "cluster-2",
            "cluster_id": "2",
            "centroid_embedding": [0.2] * 384,
            "p95_distance": 0.6,
            "label": "Topic 2",
            "member_count": 15,
            "cluster_version": "v1",
            "record_type": "cluster",
        },
    ]
    idx = TopicMemoryIndex(endpoint="x", region="us-west-2", client=mock_client)
    idx.persist_clusters(clusters)
    mock_client.bulk.assert_called_once()
    body = mock_client.bulk.call_args[1]["body"]
    assert len(body) >= 4
    assert body[1]["record_type"] == "cluster"
    assert body[1]["cluster_id"] == "1"
    assert body[3]["cluster_id"] == "2"


def test_get_cluster_returns_record(mock_client):
    """get_cluster returns cluster record by ID."""
    mock_client.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "cluster_id": "3",
                        "embedding": [0.1] * 384,
                        "metadata": {"p95_distance": 0.5, "label": "Test", "member_count": 20},
                    }
                }
            ]
        }
    }
    idx = TopicMemoryIndex(endpoint="x", region="us-west-2", client=mock_client)
    result = idx.get_cluster("3")
    assert result is not None
    assert result["cluster_id"] == 3
    assert result["p95_distance"] == 0.5
    assert result["label"] == "Test"
    assert result["member_count"] == 20


def test_get_all_clusters_returns_only_clusters(mock_client):
    """get_all_clusters returns cluster records, none with record_type=item."""
    mock_client.search.return_value = {
        "hits": {
            "hits": [
                {"_source": {"cluster_id": "1", "embedding": [], "metadata": {"p95_distance": 0.5, "label": "A", "member_count": 5}}},
                {"_source": {"cluster_id": "2", "embedding": [], "metadata": {"p95_distance": 0.6, "label": "B", "member_count": 10}}},
            ]
        }
    }
    idx = TopicMemoryIndex(endpoint="x", region="us-west-2", client=mock_client)
    results = idx.get_all_clusters()
    assert len(results) == 2
    assert results[0]["cluster_id"] == 1
    assert results[1]["cluster_id"] == 2
    mock_client.search.assert_called_once()
    query = mock_client.search.call_args[1]["body"]["query"]
    assert query["term"]["record_type"] == "cluster"


def test_find_nearest_clusters_empty_returns_empty(mock_client):
    """Empty index returns empty list."""
    mock_client.search.return_value = {"hits": {"hits": []}}
    idx = TopicMemoryIndex(endpoint="x", region="us-west-2", client=mock_client)
    emb = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    results = idx.find_nearest_clusters(emb, k=5)
    assert results == []
