"""Tests for TopicClusterer."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from plexus.analysis.topic_clusterer import TopicClusterer, _cosine_distance


def test_cosine_distance():
    """Cosine distance between identical vectors is 0."""
    v = np.array([1.0, 0.0, 0.0])
    assert _cosine_distance(v, v) == pytest.approx(0.0, abs=1e-6)


def test_cosine_distance_orthogonal():
    """Cosine distance between orthogonal vectors is 1."""
    a = np.array([1.0, 0.0, 0.0])
    b = np.array([0.0, 1.0, 0.0])
    assert _cosine_distance(a, b) == pytest.approx(1.0, abs=1e-6)


def test_cluster_assigns_ids_and_version():
    """Clustering assigns cluster IDs and returns cluster_version."""
    np.random.seed(42)
    n = 100
    dim = 384
    embeddings = np.random.randn(n, dim).astype(np.float32) * 0.1
    docs = [f"doc {i}" for i in range(n)]
    clusterer = TopicClusterer(min_topic_size=5)
    topics, version = clusterer.cluster(embeddings, docs, min_topic_size=5)
    assert len(topics) == n
    assert all(isinstance(t, (int, np.integer)) for t in topics)
    assert version is not None
    assert len(version) >= 12


def test_cluster_centroids():
    """cluster_centroids returns mean of member embeddings per cluster."""
    np.random.seed(42)
    n = 50
    dim = 384
    embeddings = np.random.randn(n, dim).astype(np.float32) * 0.1
    docs = [f"doc {i}" for i in range(n)]
    clusterer = TopicClusterer(min_topic_size=3)
    clusterer.cluster(embeddings, docs, min_topic_size=3)
    centroids = clusterer.cluster_centroids()
    assert isinstance(centroids, dict)
    for tid, cent in centroids.items():
        assert tid != -1
        assert cent.shape == (dim,)
        mask = clusterer._topics == tid
        expected = np.mean(embeddings[mask], axis=0)
        np.testing.assert_array_almost_equal(cent, expected)


def test_cluster_boundaries():
    """cluster_boundaries returns p95 distance per cluster."""
    np.random.seed(42)
    n = 50
    dim = 384
    embeddings = np.random.randn(n, dim).astype(np.float32) * 0.1
    docs = [f"doc {i}" for i in range(n)]
    clusterer = TopicClusterer(min_topic_size=3)
    clusterer.cluster(embeddings, docs, min_topic_size=3)
    boundaries = clusterer.cluster_boundaries()
    assert isinstance(boundaries, dict)
    for tid, p95 in boundaries.items():
        assert p95 >= 0


def test_generate_labels_with_mock():
    """generate_labels uses label_generator when provided."""
    np.random.seed(42)
    n = 30
    dim = 384
    embeddings = np.random.randn(n, dim).astype(np.float32) * 0.1
    docs = [f"doc {i}" for i in range(n)]
    mock_llm = MagicMock(return_value="Mocked label")
    clusterer = TopicClusterer(min_topic_size=3, label_generator=mock_llm)
    clusterer.cluster(embeddings, docs, min_topic_size=3)
    labels = clusterer.generate_labels()
    assert isinstance(labels, dict)
    assert mock_llm.call_count >= 1


def test_get_cluster_records():
    """get_cluster_records returns list with record_type=cluster."""
    np.random.seed(42)
    n = 30
    dim = 384
    embeddings = np.random.randn(n, dim).astype(np.float32) * 0.1
    docs = [f"doc {i}" for i in range(n)]
    clusterer = TopicClusterer(min_topic_size=3)
    clusterer.cluster(embeddings, docs, min_topic_size=3)
    records = clusterer.get_cluster_records()
    assert isinstance(records, list)
    for r in records:
        assert r["record_type"] == "cluster"
        assert "cluster_id" in r
        assert "centroid_embedding" in r
        assert "p95_distance" in r
        assert "label" in r
        assert "member_count" in r
