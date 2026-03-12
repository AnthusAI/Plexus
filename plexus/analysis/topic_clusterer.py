"""
TopicClusterer: clusters pre-computed embeddings via BERTopic (UMAP + HDBSCAN).

Decouples embedding from clustering. Computes centroids, p95 boundaries,
and LLM-generated labels. Used by VectorTopicMemory ReportBlock.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine distance = 1 - cosine_similarity."""
    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm == 0 or b_norm == 0:
        return 1.0
    sim = np.dot(a, b) / (a_norm * b_norm)
    return float(1.0 - np.clip(sim, -1.0, 1.0))


class TopicClusterer:
    """
    Clusters pre-computed embeddings via BERTopic (UMAP + HDBSCAN).
    Computes centroids, p95 distance boundaries, and labels.
    """

    def __init__(
        self,
        min_topic_size: int = 10,
        umap_n_components: int = 5,
        umap_min_dist: float = 0.0,
        umap_metric: str = "cosine",
        label_generator: Optional[Callable[[List[str]], str]] = None,
    ):
        self.min_topic_size = min_topic_size
        self.umap_n_components = umap_n_components
        self.umap_min_dist = umap_min_dist
        self.umap_metric = umap_metric
        self._label_generator = label_generator
        self._topics: Optional[np.ndarray] = None
        self._embeddings: Optional[np.ndarray] = None
        self._documents: Optional[List[str]] = None
        self._cluster_version: Optional[str] = None
        self._topic_model = None

    def cluster(
        self,
        embeddings: np.ndarray,
        documents: List[str],
        min_topic_size: Optional[int] = None,
        min_samples: Optional[int] = None,
        cluster_selection_method: str = "leaf",
        cluster_selection_epsilon: float = 0.5,
    ) -> Tuple[np.ndarray, str]:
        """
        Cluster embeddings via BERTopic. Returns (topic_ids, cluster_version).
        topic_ids: -1 for outliers.
        """
        from umap import UMAP
        from bertopic import BERTopic
        from hdbscan import HDBSCAN

        n = len(embeddings)
        
        if n < 15:
            # Bypass UMAP/HDBSCAN/BERTopic entirely for very small datasets
            # UMAP and BERTopic's c-TF-IDF can crash with "zero-size array to reduction operation maximum"
            # or sparse matrix errors when n is too small.
            from sklearn.cluster import KMeans
            
            k = max(1, min(3, n // 3))
            if k <= 1 or n < 2:
                topics = np.zeros(n, dtype=int)
            else:
                kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                topics = kmeans.fit_predict(embeddings)
                
            self._topics = np.array(topics)
            self._embeddings = np.asarray(embeddings, dtype=np.float32)
            self._documents = documents
            self._topic_model = None
            self._cluster_version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            return self._topics, self._cluster_version

        mt = min(min_topic_size or self.min_topic_size, max(2, n))
        ms = min_samples if min_samples is not None else min(2, mt)
        n_neighbors = min(15, max(2, n - 1))
        n_components = min(self.umap_n_components, max(2, n - 2))
        
        # UMAP's default spectral init fails with "k >= N" on small or disconnected graphs.
        init_method = "spectral" if n >= 15 else "random"

        umap_model = UMAP(
            n_neighbors=n_neighbors,
            n_components=n_components,
            min_dist=self.umap_min_dist,
            metric=self.umap_metric,
            init=init_method,
            random_state=42,
            n_jobs=1,
        )
        hdbscan_model = HDBSCAN(
            min_cluster_size=mt,
            min_samples=ms,
            cluster_selection_method=cluster_selection_method,
            cluster_selection_epsilon=cluster_selection_epsilon,
            metric="euclidean",
            prediction_data=True,
        )
        topic_model = BERTopic(
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            verbose=False,
        )
        topics, _ = topic_model.fit_transform(documents, embeddings)
        topics = np.array(topics)

        # Fallback: if HDBSCAN marks everything as outliers, use KMeans on raw embeddings
        if np.all(topics == -1) and n >= mt:
            logger.warning(
                "HDBSCAN returned all outliers; falling back to KMeans on raw embeddings"
            )
            from sklearn.cluster import KMeans

            k = min(max(2, n // 10), 20)
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            topics = kmeans.fit_predict(embeddings)

        self._topics = np.array(topics)
        self._embeddings = np.asarray(embeddings, dtype=np.float32)
        self._documents = documents
        self._topic_model = topic_model
        self._cluster_version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

        return self._topics, self._cluster_version

    def cluster_centroids(self) -> Dict[int, np.ndarray]:
        """Return centroid (mean of member embeddings) per non-outlier cluster."""
        if self._topics is None or self._embeddings is None:
            return {}
        centroids: Dict[int, np.ndarray] = {}
        for tid in np.unique(self._topics):
            if tid == -1:
                continue
            mask = self._topics == tid
            members = self._embeddings[mask]
            centroids[int(tid)] = np.mean(members, axis=0).astype(np.float32)
        return centroids

    def cluster_boundaries(self) -> Dict[int, float]:
        """Return p95 cosine distance from members to centroid per cluster."""
        centroids = self.cluster_centroids()
        if not centroids:
            return {}
        boundaries: Dict[int, float] = {}
        for tid, centroid in centroids.items():
            mask = self._topics == tid
            members = self._embeddings[mask]
            distances = [_cosine_distance(m, centroid) for m in members]
            p95 = float(np.percentile(distances, 95))
            boundaries[tid] = p95
        return boundaries

    def generate_labels(
        self,
        clusters: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> Dict[int, str]:
        """Generate human-readable labels per cluster via LLM (or mock)."""
        centroids = self.cluster_centroids()
        if not centroids:
            return {}
        labels: Dict[int, str] = {}
        for tid in centroids:
            docs = self._get_representative_docs(tid)
            if self._label_generator:
                labels[tid] = self._label_generator(docs)
            else:
                labels[tid] = f"Topic {tid}"
        return labels

    def get_representative_exemplars(
        self, topic_id: int, n: int = 5
    ) -> List[Tuple[int, str]]:
        """Return (original_index, text) pairs for the n docs closest to the centroid.

        The original_index is the position in the list passed to cluster(), allowing
        callers to map back to doc_ids, item IDs, or other per-document metadata.
        """
        if self._documents is None or self._embeddings is None:
            return []
        mask = self._topics == topic_id
        indices = np.where(mask)[0]
        centroid = self.cluster_centroids().get(topic_id)
        if centroid is None:
            return []
        distances = [
            (_cosine_distance(self._embeddings[i], centroid), int(i)) for i in indices
        ]
        distances.sort(key=lambda x: x[0])
        return [(idx, self._documents[idx]) for _, idx in distances[:n]]

    def _get_representative_docs(self, topic_id: int, n: int = 5) -> List[str]:
        """Get representative documents for a cluster (closest to centroid)."""
        return [doc for _, doc in self.get_representative_exemplars(topic_id, n=n)]

    def get_keywords(self, topic_id: int, n: int = 8) -> List[str]:
        """Extract top keywords for a cluster via TF-IDF on cluster documents."""
        if self._documents is None:
            return []
        mask = self._topics == topic_id
        indices = np.where(mask)[0]
        if len(indices) < 2:
            return []
        docs = [self._documents[i] for i in indices]
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            vectorizer = TfidfVectorizer(
                max_features=500,
                ngram_range=(1, 2),
                stop_words="english",
                min_df=1,
            )
            X = vectorizer.fit_transform(docs)
            feature_names = vectorizer.get_feature_names_out()
            scores = np.asarray(X.sum(axis=0)).flatten()
            top_indices = scores.argsort()[-n:][::-1]
            return [
                feature_names[i]
                for i in top_indices
                if scores[i] > 0 and feature_names[i]
            ]
        except Exception as e:
            logger.warning(f"Failed to extract keywords for topic {topic_id}: {e}")
            return []

    def get_cluster_records(self) -> List[Dict[str, Any]]:
        """Build cluster records for vector store persistence."""
        centroids = self.cluster_centroids()
        boundaries = self.cluster_boundaries()
        labels = self.generate_labels()
        records: List[Dict[str, Any]] = []
        for tid in centroids:
            mask = self._topics == tid
            member_count = int(np.sum(mask))
            label = labels.get(tid, f"Topic {tid}")
            p95 = boundaries.get(tid, 0.0)
            centroid_list = centroids[tid].tolist()
            records.append({
                "doc_id": f"cluster-{tid}",
                "text": label,
                "embedding": centroid_list,
                "metadata": {"p95_distance": p95, "label": label, "member_count": member_count},
                "cluster_id": str(tid),
                "cluster_version": self._cluster_version or "",
                "record_type": "cluster",
                "centroid_embedding": centroid_list,
                "p95_distance": p95,
                "label": label,
                "member_count": member_count,
            })
        return records
