"""
S3 Vectors client for Semantic Reinforcement Memory.

Thin adapter around boto3 s3vectors operations with helper methods used by
the VectorTopicMemory report block.
"""

import logging
from typing import Any, Dict, Iterable, List, Optional

import boto3
import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384
MAX_BATCH_SIZE = 500


def _chunked(items: List[Any], size: int) -> Iterable[List[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _to_float_list(vector: Any) -> List[float]:
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(v) for v in vector]


class TopicMemoryVectorStore:
    """
    S3 Vectors-backed topic memory store.

    Supports health check, full rebuild, cluster persistence, and cluster
    metadata updates used by Semantic Reinforcement Memory.
    """

    def __init__(
        self,
        bucket_name: str,
        index_name: str,
        region: str,
        index_arn: Optional[str] = None,
        client=None,
    ):
        self.bucket_name = bucket_name
        self.index_name = index_name
        self.index_arn = index_arn
        self.region = region
        self._client = client or boto3.client("s3vectors", region_name=region)

    def _vector_ref(self, index_name: Optional[str] = None) -> Dict[str, Any]:
        target_index_name = index_name or self.index_name

        # S3 Vectors API expects either indexArn OR vectorBucketName+indexName.
        # Do not send all three fields simultaneously.
        if self.index_arn and target_index_name == self.index_name:
            return {"indexArn": self.index_arn}

        return {
            "vectorBucketName": self.bucket_name,
            "indexName": target_index_name,
        }

    def health_check(self) -> bool:
        """Return True if the configured vector index is reachable."""
        try:
            self._client.get_index(**self._vector_ref())
            return True
        except Exception as e:
            logger.error("S3 Vectors health check failed: %s", e)
            return False

    def _list_all_keys(self, index_name: Optional[str] = None) -> List[str]:
        keys: List[str] = []
        next_token = None
        while True:
            params = {
                **self._vector_ref(index_name=index_name),
                "maxResults": MAX_BATCH_SIZE,
                "returnData": False,
                "returnMetadata": False,
            }
            if next_token:
                params["nextToken"] = next_token

            response = self._client.list_vectors(**params)
            for vector in response.get("vectors", []):
                key = vector.get("key")
                if key:
                    keys.append(key)

            next_token = response.get("nextToken")
            if not next_token:
                break
        return keys

    def clear_index(self, index_name: Optional[str] = None) -> int:
        """Delete all vectors in the index. Returns number of deleted vectors."""
        keys = self._list_all_keys(index_name=index_name)
        if not keys:
            return 0

        deleted = 0
        for batch in _chunked(keys, MAX_BATCH_SIZE):
            self._client.delete_vectors(**self._vector_ref(index_name=index_name), keys=batch)
            deleted += len(batch)
        return deleted

    def build_index(
        self,
        documents: List[Dict[str, Any]],
        old_index_for_swap: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Rebuild index contents by clearing existing vectors and writing new items.

        `old_index_for_swap` is accepted for API compatibility with the previous
        OpenSearch adapter and intentionally ignored.
        """
        _ = old_index_for_swap
        index_name = self.index_name
        self.clear_index(index_name=index_name)

        success_count = 0
        error_count = 0
        failed_doc_ids: List[str] = []
        vectors_to_put: List[Dict[str, Any]] = []

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

                vectors_to_put.append(
                    {
                        "key": f"item:{doc_id}",
                        "data": {"float32": emb_list},
                        "metadata": metadata,
                    }
                )
                success_count += 1
            except Exception as e:
                error_count += 1
                failed_doc_ids.append(doc_id)
                logger.warning("Malformed vector for doc_id=%s: %s", doc_id, e)

        for batch in _chunked(vectors_to_put, MAX_BATCH_SIZE):
            self._client.put_vectors(**self._vector_ref(index_name=index_name), vectors=batch)

        return {
            "success_count": success_count,
            "error_count": error_count,
            "failed_doc_ids": failed_doc_ids,
            "new_index_name": index_name,
        }

    def persist_clusters(
        self,
        clusters: List[Dict[str, Any]],
        index_name: Optional[str] = None,
    ) -> None:
        """Bulk-persist cluster vectors and metadata."""
        vectors_to_put: List[Dict[str, Any]] = []

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

            vectors_to_put.append(
                {
                    "key": f"cluster:{cluster_id}",
                    "data": {"float32": emb_list},
                    "metadata": metadata,
                }
            )

        for batch in _chunked(vectors_to_put, MAX_BATCH_SIZE):
            self._client.put_vectors(**self._vector_ref(index_name=index_name), vectors=batch)

    def _get_vectors_by_keys(
        self,
        keys: List[str],
        index_name: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        by_key: Dict[str, Dict[str, Any]] = {}
        for batch in _chunked(keys, MAX_BATCH_SIZE):
            resp = self._client.get_vectors(
                **self._vector_ref(index_name=index_name),
                keys=batch,
                returnData=True,
                returnMetadata=True,
            )
            for vector in resp.get("vectors", []):
                key = vector.get("key")
                if key:
                    by_key[key] = vector
        return by_key

    def bulk_update_cluster_weights(
        self,
        clusters: List[Dict[str, Any]],
        index_name: Optional[str] = None,
    ) -> None:
        """Update memory_weight and memory_tier on existing cluster vectors."""
        keys = [f"cluster:{c.get('cluster_id', '')}" for c in clusters]
        existing = self._get_vectors_by_keys(keys, index_name=index_name)

        updates: List[Dict[str, Any]] = []
        for cluster in clusters:
            cluster_id = str(cluster.get("cluster_id", ""))
            key = f"cluster:{cluster_id}"
            vector = existing.get(key)
            if not vector:
                logger.warning("Cluster vector not found for weight update: %s", key)
                continue

            data = vector.get("data", {}).get("float32", [])
            if len(data) != EMBEDDING_DIM:
                logger.warning("Skipping weight update for %s due to malformed data", key)
                continue

            metadata = dict(vector.get("metadata", {}) or {})
            metadata.update(dict(cluster.get("metadata", {}) or {}))
            metadata["memory_weight"] = cluster.get("memory_weight", 0.5)
            metadata["memory_tier"] = cluster.get("memory_tier", "warm")

            updates.append(
                {
                    "key": key,
                    "data": {"float32": data},
                    "metadata": metadata,
                }
            )

        for batch in _chunked(updates, MAX_BATCH_SIZE):
            self._client.put_vectors(**self._vector_ref(index_name=index_name), vectors=batch)

    def get_all_clusters(self) -> List[Dict[str, Any]]:
        """Retrieve all cluster vectors from the index."""
        results: List[Dict[str, Any]] = []
        next_token = None

        while True:
            params = {
                **self._vector_ref(),
                "maxResults": MAX_BATCH_SIZE,
                "returnData": True,
                "returnMetadata": True,
            }
            if next_token:
                params["nextToken"] = next_token

            resp = self._client.list_vectors(**params)
            for vector in resp.get("vectors", []):
                metadata = dict(vector.get("metadata", {}) or {})
                if metadata.get("record_type") != "cluster":
                    continue

                cluster_id = metadata.get("cluster_id", "")
                results.append(
                    {
                        "cluster_id": int(cluster_id)
                        if str(cluster_id).lstrip("-").isdigit()
                        else cluster_id,
                        "centroid_embedding": vector.get("data", {}).get("float32"),
                        "p95_distance": metadata.get("p95_distance", 0.0),
                        "label": metadata.get("label", ""),
                        "member_count": metadata.get("member_count", 0),
                    }
                )

            next_token = resp.get("nextToken")
            if not next_token:
                break

        return results

    def find_nearest_clusters(
        self,
        embedding: np.ndarray,
        k: int = 5,
        threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query nearest cluster vectors.

        Returns results ordered by ascending distance with compatibility fields.
        """
        emb_list = _to_float_list(embedding)
        if len(emb_list) != EMBEDDING_DIM:
            return []

        try:
            response = self._client.query_vectors(
                **self._vector_ref(),
                topK=k,
                queryVector={"float32": emb_list},
                returnMetadata=True,
                returnDistance=True,
            )
        except Exception as e:
            logger.error("S3 Vectors query failed: %s", e)
            return []

        results: List[Dict[str, Any]] = []
        for hit in response.get("vectors", []):
            metadata = dict(hit.get("metadata", {}) or {})
            if metadata.get("record_type") != "cluster":
                continue

            distance = hit.get("distance")
            if threshold is not None and distance is not None and distance > threshold:
                continue

            results.append(
                {
                    "cluster_id": metadata.get("cluster_id", ""),
                    "doc_id": hit.get("key", ""),
                    "similarity_score": None if distance is None else (1.0 - float(distance)),
                    "distance": distance,
                }
            )

        results.sort(
            key=lambda r: float("inf") if r.get("distance") is None else r["distance"]
        )
        return results
