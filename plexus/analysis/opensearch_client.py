"""
OpenSearch client for Vector Topic Memory.

Thin adapter wrapping opensearch-py with AWS SigV4 auth.
Supports health check, bulk indexing with blue/green alias swap,
and KNN search for nearest cluster assignment.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

LIVE_ALIAS = "topic-memory-live"
BUILD_ALIAS = "topic-memory-build"
INDEX_PREFIX = "topic-memory"
EMBEDDING_DIM = 384


def _topic_memory_mapping() -> Dict[str, Any]:
    """Index mapping for topic memory documents."""
    return {
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "text": {"type": "text"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": EMBEDDING_DIM,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "metadata": {"type": "object"},
                "cluster_id": {"type": "keyword"},
                "cluster_version": {"type": "keyword"},
                "record_type": {"type": "keyword"},
            }
        }
    }


class TopicMemoryIndex:
    """
    OpenSearch client for topic memory index.
    Wraps opensearch-py with SigV4 auth, health check, bulk indexing,
    blue/green alias swap, and KNN search.
    """

    def __init__(
        self,
        endpoint: str,
        region: str,
        client=None,
        service: str = "es",
    ):
        """
        Args:
            endpoint: OpenSearch domain endpoint (e.g. search-xxx.us-west-2.es.amazonaws.com)
            region: AWS region
            client: Optional pre-built OpenSearch client (for testing)
            service: AWS service name for SigV4 ('es' for OpenSearch)
        """
        self.endpoint = endpoint
        self.region = region
        self._client = client
        self._service = service
        if client is None:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize opensearch-py client with AWS SigV4 auth."""
        from urllib.parse import urlparse

        import boto3
        from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

        url = urlparse(
            self.endpoint if self.endpoint.startswith("http") else f"https://{self.endpoint}"
        )
        host = url.netloc or self.endpoint
        port = url.port or 443
        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, self.region, self._service)
        self._client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            pool_maxsize=20,
        )

    def health_check(self) -> bool:
        """Return True if cluster is healthy, False otherwise. Does not raise."""
        try:
            resp = self._client.cluster.health()
            status = resp.get("status", "")
            return status in ("green", "yellow")
        except Exception as e:
            logger.error("OpenSearch health check failed: %s", e)
            return False

    def _timestamped_index_name(self) -> str:
        return f"{INDEX_PREFIX}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    def build_index(
        self,
        documents: List[Dict[str, Any]],
        old_index_for_swap: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create timestamped index, bulk-index documents, swap live alias.
        Returns dict with success_count, error_count, failed_doc_ids, new_index_name.
        """
        index_name = self._timestamped_index_name()
        self._client.indices.create(index=index_name, body=_topic_memory_mapping())

        success_count = 0
        error_count = 0
        failed_doc_ids: List[str] = []

        bulk_body: List[Dict] = []
        for doc in documents:
            doc_id = doc.get("doc_id", "")
            try:
                emb = doc.get("embedding")
                if emb is None or (hasattr(emb, "shape") and emb.shape[0] != EMBEDDING_DIM):
                    error_count += 1
                    failed_doc_ids.append(doc_id)
                    logger.warning("Malformed embedding for doc_id=%s", doc_id)
                    continue
                if hasattr(emb, "tolist"):
                    emb = emb.tolist()
                bulk_body.append({"index": {"_index": index_name, "_id": doc_id}})
                bulk_body.append({
                    "doc_id": doc_id,
                    "text": doc.get("text", ""),
                    "embedding": emb,
                    "metadata": doc.get("metadata", {}),
                    "cluster_id": doc.get("cluster_id", ""),
                    "cluster_version": doc.get("cluster_version", ""),
                    "record_type": doc.get("record_type", "item"),
                })
                success_count += 1
            except Exception as e:
                error_count += 1
                failed_doc_ids.append(doc_id)
                logger.warning("Failed to prepare doc_id=%s: %s", doc_id, e)

        if bulk_body:
            resp = self._client.bulk(body=bulk_body, refresh=True)
            if resp.get("errors"):
                for item in resp.get("items", []):
                    idx = item.get("index", {})
                    if "error" in idx:
                        error_count += 1
                        failed_doc_ids.append(idx.get("_id", ""))

        old_idx = old_index_for_swap or self._get_alias_target(LIVE_ALIAS)
        if old_idx and old_idx != index_name:
            self.swap_alias(index_name, old_idx)

        return {
            "success_count": success_count,
            "error_count": error_count,
            "failed_doc_ids": failed_doc_ids,
            "new_index_name": index_name,
        }

    def _get_alias_target(self, alias_name: str) -> Optional[str]:
        """Return the index name that has the alias, or None."""
        try:
            resp = self._client.indices.get_alias(name=alias_name)
            return list(resp.keys())[0] if resp else None
        except Exception:
            return None

    def swap_alias(self, new_index_name: str, old_index_name: str) -> None:
        """Atomically swap topic-memory-live from old to new index, then delete old."""
        self._client.indices.update_aliases(
            body={
                "actions": [
                    {"remove": {"index": old_index_name, "alias": LIVE_ALIAS}},
                    {"add": {"index": new_index_name, "alias": LIVE_ALIAS}},
                ]
            }
        )
        self._client.indices.delete(index=old_index_name)

    def persist_clusters(
        self,
        clusters: List[Dict[str, Any]],
        index_name: Optional[str] = None,
    ) -> None:
        """Bulk-index cluster records. Uses live alias if index_name not provided."""
        target = index_name or LIVE_ALIAS
        bulk_body: List[Dict] = []
        for c in clusters:
            doc_id = c.get("doc_id", c.get("cluster_id", ""))
            bulk_body.append({"index": {"_index": target, "_id": doc_id}})
            bulk_body.append({
                "doc_id": doc_id,
                "text": c.get("text", ""),
                "embedding": c.get("embedding", c.get("centroid_embedding", [])),
                "metadata": c.get("metadata", {}),
                "cluster_id": str(c.get("cluster_id", "")),
                "cluster_version": c.get("cluster_version", ""),
                "record_type": "cluster",
            })
        if bulk_body:
            self._client.bulk(body=bulk_body, refresh=True)

    def get_cluster(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single cluster record by cluster_id."""
        try:
            resp = self._client.search(
                index=LIVE_ALIAS,
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"record_type": "cluster"}},
                                {"term": {"cluster_id": str(cluster_id)}},
                            ]
                        }
                    },
                    "size": 1,
                },
            )
            hits = resp.get("hits", {}).get("hits", [])
            if not hits:
                return None
            src = hits[0].get("_source", {})
            return {
                "cluster_id": int(cluster_id) if cluster_id.lstrip("-").isdigit() else cluster_id,
                "centroid_embedding": src.get("embedding", src.get("centroid_embedding")),
                "p95_distance": src.get("metadata", {}).get("p95_distance", src.get("p95_distance", 0.0)),
                "label": src.get("metadata", {}).get("label", src.get("label", "")),
                "member_count": src.get("metadata", {}).get("member_count", src.get("member_count", 0)),
            }
        except Exception as e:
            logger.error("get_cluster failed: %s", e)
            return None

    def bulk_update_cluster_weights(
        self,
        clusters: List[Dict[str, Any]],
        index_name: Optional[str] = None,
    ) -> None:
        """Bulk update memory_weight and memory_tier on cluster records."""
        target = index_name or LIVE_ALIAS
        for c in clusters:
            cid = c.get("cluster_id", "")
            doc_id = f"cluster-{cid}"
            try:
                self._client.update(
                    index=target,
                    id=doc_id,
                    body={
                        "doc": {
                            "memory_weight": c.get("memory_weight", 0.5),
                            "memory_tier": c.get("memory_tier", "warm"),
                            "metadata": {
                                **c.get("metadata", {}),
                                "memory_weight": c.get("memory_weight", 0.5),
                                "memory_tier": c.get("memory_tier", "warm"),
                            },
                        }
                    },
                )
            except Exception as e:
                logger.warning("Failed to update cluster %s: %s", doc_id, e)

    def unassign_items_from_cluster(self, cluster_id: str, index_name: Optional[str] = None) -> int:
        """Set cluster_id=-1 for all items in cluster. Returns count updated."""
        target = index_name or LIVE_ALIAS
        try:
            resp = self._client.update_by_query(
                index=target,
                body={
                    "script": {"source": "ctx._source.cluster_id = '-1'", "lang": "painless"},
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"record_type": "item"}},
                                {"term": {"cluster_id": str(cluster_id)}},
                            ]
                        }
                    },
                },
            )
            return int(resp.get("updated", 0))
        except Exception as e:
            logger.error("unassign_items_from_cluster failed: %s", e)
            return 0

    def delete_cluster_record(self, cluster_id: str, index_name: Optional[str] = None) -> bool:
        """Delete a cluster record from the index."""
        target = index_name or LIVE_ALIAS
        try:
            self._client.delete(index=target, id=f"cluster-{cluster_id}")
            return True
        except Exception as e:
            logger.warning("Failed to delete cluster %s: %s", cluster_id, e)
            return False

    def get_all_clusters(self) -> List[Dict[str, Any]]:
        """Retrieve all cluster records (record_type=cluster)."""
        try:
            resp = self._client.search(
                index=LIVE_ALIAS,
                body={
                    "query": {"term": {"record_type": "cluster"}},
                    "size": 10000,
                },
            )
            hits = resp.get("hits", {}).get("hits", [])
            results: List[Dict[str, Any]] = []
            for h in hits:
                src = h.get("_source", {})
                cid = src.get("cluster_id", "")
                results.append({
                    "cluster_id": int(cid) if str(cid).lstrip("-").isdigit() else cid,
                    "centroid_embedding": src.get("embedding", src.get("centroid_embedding")),
                    "p95_distance": src.get("metadata", {}).get("p95_distance", src.get("p95_distance", 0.0)),
                    "label": src.get("metadata", {}).get("label", src.get("label", "")),
                    "member_count": src.get("metadata", {}).get("member_count", src.get("member_count", 0)),
                })
            return results
        except Exception as e:
            logger.error("get_all_clusters failed: %s", e)
            return []

    def find_nearest_clusters(
        self,
        embedding: np.ndarray,
        k: int = 5,
        threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        KNN search for nearest cluster centroids.
        Returns list of {cluster_id, doc_id, similarity_score} ordered by descending similarity.
        """
        emb_list = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
        query: Dict[str, Any] = {
            "size": k,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": emb_list,
                        "k": k,
                    }
                }
            },
            "_source": ["cluster_id", "doc_id"],
        }
        try:
            resp = self._client.search(index=LIVE_ALIAS, body=query)
        except Exception as e:
            logger.error("KNN search failed: %s", e)
            return []

        hits = resp.get("hits", {}).get("hits", [])
        results: List[Dict[str, Any]] = []
        for h in hits:
            score = h.get("_score")
            if threshold is not None and score is not None and score < threshold:
                continue
            src = h.get("_source", {})
            results.append({
                "cluster_id": src.get("cluster_id", ""),
                "doc_id": src.get("doc_id", h.get("_id", "")),
                "similarity_score": score,
            })
        return results
