"""
Qdrant-backed vector store adapter for semantic reinforcement memory.

Implements the topic-memory vector operations used by VectorTopicMemory while
preserving the same high-level method contract as the S3 Vectors adapter.
"""

from __future__ import annotations

import uuid
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384
MAX_BATCH_SIZE = 500
POINT_ID_NAMESPACE = uuid.UUID("935f57cc-c304-4f28-9132-e2d3a8ff93f3")


def _chunked(items: List[Any], size: int) -> Iterable[List[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _to_float_list(vector: Any) -> List[float]:
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(v) for v in vector]


def _extract_vector_payload(point: Any) -> Tuple[Optional[List[float]], Dict[str, Any]]:
    if isinstance(point, dict):
        return point.get("vector"), dict(point.get("payload") or {})
    return getattr(point, "vector", None), dict(getattr(point, "payload", {}) or {})


def _extract_point_id(point: Any) -> str:
    if isinstance(point, dict):
        return str(point.get("id", ""))
    return str(getattr(point, "id", ""))


def _to_qdrant_point_id(key: str) -> str:
    """Map string keys deterministically to UUID point IDs accepted by Qdrant."""
    return str(uuid.uuid5(POINT_ID_NAMESPACE, key))


class QdrantTopicMemoryVectorStore:
    """
    Qdrant-backed topic memory store.

    Supports health check, full rebuild, cluster persistence, and metadata
    updates used by Semantic Reinforcement Memory.
    """

    def __init__(
        self,
        url: str,
        collection_name: str,
        client: Any = None,
    ):
        self.url = url
        self.collection_name = collection_name
        self._client = client or self._create_client(url)

    @staticmethod
    def _create_client(url: str) -> Any:
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise ImportError(
                "qdrant-client is required for Qdrant vector store support. "
                "Install dependencies with Poetry to continue."
            ) from exc

        return QdrantClient(url=url, check_compatibility=False)

    def _create_collection(self, collection_name: str) -> None:
        self._client.create_collection(
            collection_name=collection_name,
            vectors_config={"size": EMBEDDING_DIM, "distance": "Cosine"},
        )

    def _collection_exists(self, collection_name: str) -> bool:
        try:
            self._client.get_collection(collection_name=collection_name)
            return True
        except Exception:
            return False

    def _ensure_collection(self, collection_name: str) -> None:
        if not self._collection_exists(collection_name):
            self._create_collection(collection_name)

    def health_check(self) -> bool:
        """Return True if the configured collection is reachable."""
        try:
            self._ensure_collection(self.collection_name)
            return True
        except Exception as exc:
            logger.error("Qdrant health check failed: %s", exc)
            return False

    def _scroll_points(
        self,
        collection_name: str,
        *,
        with_vectors: bool,
    ) -> List[Any]:
        points: List[Any] = []
        offset = None
        while True:
            response = self._client.scroll(
                collection_name=collection_name,
                limit=MAX_BATCH_SIZE,
                offset=offset,
                with_payload=True,
                with_vectors=with_vectors,
            )
            if isinstance(response, tuple):
                batch, offset = response
            else:
                batch = getattr(response, "points", [])
                offset = getattr(response, "next_page_offset", None)

            points.extend(batch or [])
            if offset is None:
                break

        return points

    def clear_index(self, index_name: Optional[str] = None) -> int:
        """Delete all vectors in the collection. Returns number of deleted vectors."""
        collection_name = index_name or self.collection_name
        if not self._collection_exists(collection_name):
            self._create_collection(collection_name)
            return 0

        count_response = self._client.count(collection_name=collection_name, exact=True)
        if isinstance(count_response, dict):
            count = int(count_response.get("count", 0))
        else:
            count = int(getattr(count_response, "count", 0))

        self._client.delete_collection(collection_name=collection_name)
        self._create_collection(collection_name)
        return count

    def build_index(
        self,
        documents: List[Dict[str, Any]],
        old_index_for_swap: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Rebuild collection contents by clearing existing points and writing new items.

        `old_index_for_swap` is accepted for API compatibility and ignored.
        """
        _ = old_index_for_swap
        collection_name = self.collection_name
        self.clear_index(index_name=collection_name)

        success_count = 0
        error_count = 0
        failed_doc_ids: List[str] = []
        points_to_put: List[Dict[str, Any]] = []

        for doc in documents:
            doc_id = str(doc.get("doc_id", ""))
            try:
                emb = doc.get("embedding")
                if emb is None:
                    raise ValueError("missing embedding")

                emb_list = _to_float_list(emb)
                if len(emb_list) != EMBEDDING_DIM:
                    raise ValueError(
                        f"expected {EMBEDDING_DIM} dimensions, got {len(emb_list)}"
                    )

                metadata = dict(doc.get("metadata", {}) or {})
                metadata.update(
                    {
                        "record_type": doc.get("record_type", "item"),
                        "doc_id": doc_id,
                        "cluster_id": str(doc.get("cluster_id", "")),
                        "cluster_version": str(doc.get("cluster_version", "")),
                    }
                )

                key = f"item:{doc_id}"
                points_to_put.append(
                    {
                        "id": _to_qdrant_point_id(key),
                        "vector": emb_list,
                        "payload": {
                            "key": key,
                            "metadata": metadata,
                        },
                    }
                )
                success_count += 1
            except Exception as exc:
                error_count += 1
                failed_doc_ids.append(doc_id)
                logger.warning("Malformed vector for doc_id=%s: %s", doc_id, exc)

        for batch in _chunked(points_to_put, MAX_BATCH_SIZE):
            self._client.upsert(
                collection_name=collection_name,
                points=batch,
                wait=True,
            )

        return {
            "success_count": success_count,
            "error_count": error_count,
            "failed_doc_ids": failed_doc_ids,
            "new_index_name": collection_name,
        }

    def persist_clusters(
        self,
        clusters: List[Dict[str, Any]],
        index_name: Optional[str] = None,
    ) -> None:
        """Bulk-persist cluster vectors and metadata."""
        collection_name = index_name or self.collection_name
        self._ensure_collection(collection_name)

        points_to_put: List[Dict[str, Any]] = []
        for cluster in clusters:
            cluster_id = str(cluster.get("cluster_id", ""))
            embedding = cluster.get("embedding", cluster.get("centroid_embedding", []))
            emb_list = _to_float_list(embedding)
            if len(emb_list) != EMBEDDING_DIM:
                logger.warning(
                    "Skipping cluster %s due to invalid embedding size: %s",
                    cluster_id,
                    len(emb_list),
                )
                continue

            metadata = dict(cluster.get("metadata", {}) or {})
            metadata.update(
                {
                    "record_type": "cluster",
                    "cluster_id": cluster_id,
                    "cluster_version": str(cluster.get("cluster_version", "")),
                    "label": cluster.get("label", ""),
                    "member_count": cluster.get("member_count", 0),
                    "p95_distance": cluster.get("p95_distance", 0.0),
                }
            )
            key = f"cluster:{cluster_id}"
            points_to_put.append(
                {
                    "id": _to_qdrant_point_id(key),
                    "vector": emb_list,
                    "payload": {
                        "key": key,
                        "metadata": metadata,
                    },
                }
            )

        for batch in _chunked(points_to_put, MAX_BATCH_SIZE):
            self._client.upsert(
                collection_name=collection_name,
                points=batch,
                wait=True,
            )

    def _get_points_by_ids(
        self,
        keys: List[str],
        index_name: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        collection_name = index_name or self.collection_name
        by_key: Dict[str, Dict[str, Any]] = {}
        key_by_point_id = { _to_qdrant_point_id(key): key for key in keys }

        for batch in _chunked(keys, MAX_BATCH_SIZE):
            point_ids = [_to_qdrant_point_id(key) for key in batch]
            points = self._client.retrieve(
                collection_name=collection_name,
                ids=point_ids,
                with_payload=True,
                with_vectors=True,
            )
            for point in points or []:
                point_id = _extract_point_id(point)
                vector, payload = _extract_vector_payload(point)
                key = str(payload.get("key") or key_by_point_id.get(point_id) or "")
                if not key:
                    continue
                by_key[key] = {
                    "key": key,
                    "vector": vector,
                    "metadata": payload.get("metadata", {}),
                }

        return by_key

    def bulk_update_cluster_weights(
        self,
        clusters: List[Dict[str, Any]],
        index_name: Optional[str] = None,
    ) -> None:
        """Update memory_weight and memory_tier on existing cluster vectors."""
        collection_name = index_name or self.collection_name
        keys = [f"cluster:{c.get('cluster_id', '')}" for c in clusters]
        existing = self._get_points_by_ids(keys, index_name=collection_name)

        updates: List[Dict[str, Any]] = []
        for cluster in clusters:
            cluster_id = str(cluster.get("cluster_id", ""))
            key = f"cluster:{cluster_id}"
            point = existing.get(key)
            if not point:
                logger.warning("Cluster vector not found for weight update: %s", key)
                continue

            vector = point.get("vector") or []
            emb_list = _to_float_list(vector)
            if len(emb_list) != EMBEDDING_DIM:
                logger.warning("Skipping weight update for %s due to malformed data", key)
                continue

            metadata = dict(point.get("metadata", {}) or {})
            metadata.update(dict(cluster.get("metadata", {}) or {}))
            metadata["memory_weight"] = cluster.get("memory_weight", 0.5)
            metadata["memory_tier"] = cluster.get("memory_tier", "warm")

            updates.append(
                {
                    "id": _to_qdrant_point_id(key),
                    "vector": emb_list,
                    "payload": {
                        "key": key,
                        "metadata": metadata,
                    },
                }
            )

        for batch in _chunked(updates, MAX_BATCH_SIZE):
            self._client.upsert(
                collection_name=collection_name,
                points=batch,
                wait=True,
            )

    def get_all_clusters(self) -> List[Dict[str, Any]]:
        """Retrieve all cluster vectors from the collection."""
        results: List[Dict[str, Any]] = []
        for point in self._scroll_points(self.collection_name, with_vectors=True):
            vector, payload = _extract_vector_payload(point)
            metadata = dict(payload.get("metadata", {}) or {})
            if metadata.get("record_type") != "cluster":
                continue

            cluster_id = metadata.get("cluster_id", "")
            results.append(
                {
                    "cluster_id": int(cluster_id)
                    if str(cluster_id).lstrip("-").isdigit()
                    else cluster_id,
                    "centroid_embedding": vector,
                    "p95_distance": metadata.get("p95_distance", 0.0),
                    "label": metadata.get("label", ""),
                    "member_count": metadata.get("member_count", 0),
                }
            )
        return results

    def find_nearest_clusters(
        self,
        embedding: np.ndarray,
        k: int = 5,
        threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query nearest cluster points.

        Returns results ordered by descending similarity, matching previous
        topic-memory adapter behavior.
        """
        emb_list = _to_float_list(embedding)
        if len(emb_list) != EMBEDDING_DIM:
            return []

        try:
            kwargs: Dict[str, Any] = {}
            if threshold is not None:
                kwargs["score_threshold"] = float(threshold)

            hits = self._client.search(
                collection_name=self.collection_name,
                query_vector=emb_list,
                limit=k,
                with_payload=True,
                **kwargs,
            )
        except Exception as exc:
            logger.error("Qdrant query failed: %s", exc)
            return []

        results: List[Dict[str, Any]] = []
        for hit in hits or []:
            payload = dict(getattr(hit, "payload", {}) or {})
            metadata = dict(payload.get("metadata", {}) or {})
            if metadata.get("record_type") != "cluster":
                continue

            similarity = getattr(hit, "score", None)
            distance = None if similarity is None else (1.0 - float(similarity))
            if threshold is not None and similarity is not None and similarity < threshold:
                continue

            results.append(
                {
                    "cluster_id": metadata.get("cluster_id", ""),
                    "doc_id": payload.get("key", ""),
                    "similarity_score": similarity,
                    "distance": distance,
                }
            )

        results.sort(
            key=lambda r: float("-inf")
            if r.get("similarity_score") is None
            else r["similarity_score"],
            reverse=True,
        )
        return results
