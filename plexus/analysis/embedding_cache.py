"""
S3-backed embedding cache and embedding service.

Maps hash(normalized_text + model_id + preprocessing_version) to embedding
vectors stored in S3. Re-indexing OpenSearch does not require re-embedding.
"""

import hashlib
import json
import logging
import os
import re
from typing import List, Optional

import boto3
import numpy as np
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_BUCKET = "plexus-embeddings"
DEFAULT_MODEL_ID = "all-MiniLM-L6-v2"
DEFAULT_PREPROCESSING_VERSION = "1"


def normalize_text(text: str) -> str:
    """Collapse whitespace and lowercase for deterministic cache keys."""
    if not text or not isinstance(text, str):
        return ""
    collapsed = re.sub(r"\s+", " ", text.strip())
    return collapsed.lower()


def cache_key(text: str, model_id: str, preprocessing_version: str) -> str:
    """
    Deterministic cache key: SHA-256(normalize(text) + "|" + model_id + "|" + preprocessing_version).
    """
    normalized = normalize_text(text)
    payload = f"{normalized}|{model_id}|{preprocessing_version}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _s3_path(model_id: str, key: str) -> str:
    """S3 key: embeddings/{model_id}/{key_prefix}/{key}.json"""
    key_prefix = key[:2] if len(key) >= 2 else "00"
    return f"embeddings/{model_id}/{key_prefix}/{key}.json"


class EmbeddingCache:
    """
    S3-backed cache for embedding vectors.
    Cache key = SHA-256(normalize(text) + "|" + model_id + "|" + preprocessing_version).
    S3 path = embeddings/{model_id}/{key_prefix}/{key}.json
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        s3_client=None,
    ):
        self.bucket_name = bucket_name or os.environ.get(
            "EMBEDDING_CACHE_BUCKET", DEFAULT_EMBEDDING_BUCKET
        )
        self._s3 = s3_client or boto3.client("s3")

    def get(self, model_id: str, key: str) -> Optional[np.ndarray]:
        """
        Retrieve embedding from S3. Returns None on cache miss or error.
        """
        s3_key = _s3_path(model_id, key)
        try:
            response = self._s3.get_object(Bucket=self.bucket_name, Key=s3_key)
            body = response["Body"].read().decode("utf-8")
            data = json.loads(body)
            vec = data.get("embedding")
            if vec is None:
                return None
            return np.array(vec, dtype=np.float32)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code == "NoSuchKey":
                return None
            logger.warning("S3 get_object failed for %s: %s", s3_key, e)
            return None
        except Exception as e:
            logger.warning("Unexpected error reading cache %s: %s", s3_key, e)
            return None

    def put(self, model_id: str, key: str, embedding: np.ndarray) -> None:
        """
        Write embedding to S3. Non-fatal on failure (embedding was computed in memory).
        """
        s3_key = _s3_path(model_id, key)
        try:
            vec_list = embedding.tolist()
            body = json.dumps({"embedding": vec_list}).encode("utf-8")
            self._s3.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=body,
                ContentType="application/json",
            )
        except Exception as e:
            logger.warning("S3 put_object failed for %s (non-fatal): %s", s3_key, e)


class EmbeddingService:
    """
    Batch embedding with cache-first strategy.
    Checks cache for each text, computes misses via sentence-transformers, writes through.
    """

    def __init__(
        self,
        cache: Optional[EmbeddingCache] = None,
        model_id: str = DEFAULT_MODEL_ID,
        preprocessing_version: str = DEFAULT_PREPROCESSING_VERSION,
    ):
        self.cache = cache or EmbeddingCache()
        self.model_id = model_id
        self.preprocessing_version = preprocessing_version
        self._model = None

    def _get_model(self):
        """Lazy-load sentence-transformers model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_id)
        return self._model

    def batch_embed(
        self,
        texts: List[str],
        model_id: Optional[str] = None,
        preprocessing_version: Optional[str] = None,
    ) -> List[np.ndarray]:
        """
        Embed texts, using cache for hits and model for misses.
        Preserves original ordering.
        """
        mid = model_id or self.model_id
        ver = preprocessing_version or self.preprocessing_version

        keys = [cache_key(t, mid, ver) for t in texts]
        result: List[Optional[np.ndarray]] = [None] * len(texts)
        miss_indices: List[int] = []
        miss_texts: List[str] = []

        for i, (text, key) in enumerate(zip(texts, keys)):
            cached = self.cache.get(mid, key)
            if cached is not None:
                result[i] = cached
            else:
                miss_indices.append(i)
                miss_texts.append(text)

        if miss_texts:
            model = self._get_model()
            embeddings = model.encode(miss_texts, convert_to_numpy=True)
            for idx, emb in zip(miss_indices, embeddings):
                result[idx] = emb
                key = keys[idx]
                self.cache.put(mid, key, emb)

        return [r for r in result if r is not None]
