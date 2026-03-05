"""Tests for EmbeddingCache and EmbeddingService."""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from plexus.analysis.embedding_cache import (
    EmbeddingCache,
    EmbeddingService,
    cache_key,
    normalize_text,
)


class TestNormalizeText:
    def test_collapses_whitespace(self):
        assert normalize_text("  hello   world  ") == "hello world"

    def test_lowercases(self):
        assert normalize_text("Hello World") == "hello world"

    def test_empty_string(self):
        assert normalize_text("") == ""

    def test_empty_after_strip(self):
        assert normalize_text("   ") == ""


class TestCacheKey:
    def test_deterministic(self):
        k1 = cache_key("hello", "model1", "v1")
        k2 = cache_key("hello", "model1", "v1")
        assert k1 == k2

    def test_different_text_different_key(self):
        k1 = cache_key("hello", "model1", "v1")
        k2 = cache_key("world", "model1", "v1")
        assert k1 != k2

    def test_different_model_different_key(self):
        k1 = cache_key("hello", "model1", "v1")
        k2 = cache_key("hello", "model2", "v1")
        assert k1 != k2

    def test_different_version_different_key(self):
        k1 = cache_key("hello", "model1", "v1")
        k2 = cache_key("hello", "model1", "v2")
        assert k1 != k2

    def test_normalization_affects_key(self):
        k1 = cache_key("  Hello   World  ", "m", "v")
        k2 = cache_key("hello world", "m", "v")
        assert k1 == k2

    def test_hex_format(self):
        k = cache_key("x", "m", "v")
        assert len(k) == 64
        assert all(c in "0123456789abcdef" for c in k)


class TestEmbeddingCache:
    def test_get_miss_returns_none(self):
        from botocore.exceptions import ClientError

        mock_s3 = MagicMock()
        error = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        mock_s3.get_object.side_effect = error
        cache = EmbeddingCache(bucket_name="test", s3_client=mock_s3)
        result = cache.get("model1", "abc123")
        assert result is None

    def test_get_hit_returns_vector(self):
        vec = [0.1, 0.2, 0.3]
        body = json.dumps({"embedding": vec}).encode("utf-8")
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: body)}
        cache = EmbeddingCache(bucket_name="test", s3_client=mock_s3)
        result = cache.get("model1", "abc123")
        assert result is not None
        np.testing.assert_array_almost_equal(result, np.array(vec, dtype=np.float32))

    def test_put_calls_s3(self):
        mock_s3 = MagicMock()
        cache = EmbeddingCache(bucket_name="test", s3_client=mock_s3)
        emb = np.array([0.1, 0.2], dtype=np.float32)
        cache.put("model1", "ab1234", emb)
        mock_s3.put_object.assert_called_once()
        call_kw = mock_s3.put_object.call_args[1]
        assert call_kw["Bucket"] == "test"
        assert "embeddings/model1/ab/ab1234.json" == call_kw["Key"]
        data = json.loads(call_kw["Body"].decode("utf-8"))
        np.testing.assert_array_almost_equal(data["embedding"], [0.1, 0.2])

    def test_s3_path_format(self):
        from plexus.analysis.embedding_cache import _s3_path

        assert _s3_path("m1", "abcdef") == "embeddings/m1/ab/abcdef.json"
        assert _s3_path("m1", "a") == "embeddings/m1/00/a.json"


class TestEmbeddingService:
    def test_batch_embed_all_cache_hits(self):
        mock_cache = MagicMock(spec=EmbeddingCache)
        vec = np.array([0.1, 0.2], dtype=np.float32)
        mock_cache.get.return_value = vec
        mock_cache.put = MagicMock()
        svc = EmbeddingService(cache=mock_cache, model_id="test-model")
        with patch.object(svc, "_get_model") as mock_get_model:
            result = svc.batch_embed(["hello", "world"])
            mock_get_model.assert_not_called()
        assert len(result) == 2
        np.testing.assert_array_almost_equal(result[0], vec)
        np.testing.assert_array_almost_equal(result[1], vec)
        assert mock_cache.put.call_count == 0

    def test_batch_embed_all_misses(self):
        mock_cache = MagicMock(spec=EmbeddingCache)
        mock_cache.get.return_value = None
        mock_cache.put = MagicMock()
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array(
            [[0.1] * 384, [0.2] * 384], dtype=np.float32
        )
        svc = EmbeddingService(cache=mock_cache, model_id="test-model")
        with patch.object(svc, "_get_model", return_value=mock_model):
            result = svc.batch_embed(["hello", "world"])
        assert len(result) == 2
        assert result[0].shape[0] == 384
        assert result[1].shape[0] == 384
        assert mock_cache.put.call_count == 2

    def test_batch_embed_preserves_order(self):
        mock_cache = MagicMock(spec=EmbeddingCache)
        vec_a = np.array([1.0] * 384, dtype=np.float32)
        vec_c = np.array([3.0] * 384, dtype=np.float32)
        mock_cache.get.side_effect = [vec_a, None, vec_c]
        mock_cache.put = MagicMock()
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[2.0] * 384], dtype=np.float32)
        svc = EmbeddingService(cache=mock_cache, model_id="test-model")
        with patch.object(svc, "_get_model", return_value=mock_model):
            result = svc.batch_embed(["first", "second", "third"])
        assert len(result) == 3
        np.testing.assert_array_almost_equal(result[0], vec_a)
        np.testing.assert_array_almost_equal(result[2], vec_c)
        assert result[1].shape[0] == 384

    def test_batch_embed_raises_when_model_returns_short_batch(self):
        mock_cache = MagicMock(spec=EmbeddingCache)
        mock_cache.get.return_value = None
        mock_cache.put = MagicMock()
        mock_model = MagicMock()
        # Simulate transient failure that only returns one embedding for two misses.
        mock_model.encode.return_value = np.array([[0.1] * 384], dtype=np.float32)
        svc = EmbeddingService(cache=mock_cache, model_id="test-model")

        with patch.object(svc, "_get_model", return_value=mock_model):
            with pytest.raises(RuntimeError, match="unexpected batch size"):
                svc.batch_embed(["hello", "world"])
