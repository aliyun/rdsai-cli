"""Tests for memory embedding wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory.embedding import MemoryEmbedding


def test_not_available():
    config = MagicMock(default_embedding_model="", embedding_models={}, embedding_providers={})
    with patch("memory.embedding.EmbeddingService.from_config", return_value=None):
        embedding = MemoryEmbedding(config)
    assert embedding.is_available is False


@pytest.mark.asyncio
async def test_embed_text_not_available():
    config = MagicMock(default_embedding_model="", embedding_models={}, embedding_providers={})
    with patch("memory.embedding.EmbeddingService.from_config", return_value=None):
        embedding = MemoryEmbedding(config)
        assert await embedding.embed_text("hello") == []


@pytest.mark.asyncio
async def test_embed_text_available():
    config = MagicMock(default_embedding_model="text-embedding-v3")
    service = AsyncMock()
    service.generate_embedding = AsyncMock(return_value=[0.1, 0.2])
    with patch("memory.embedding.EmbeddingService.from_config", return_value=service):
        embedding = MemoryEmbedding(config)
        assert await embedding.embed_text("hello") == [0.1, 0.2]
    service.generate_embedding.assert_called_once_with("hello")


@pytest.mark.asyncio
async def test_embed_texts_available():
    config = MagicMock(default_embedding_model="text-embedding-v3")
    service = AsyncMock()
    service.generate_embeddings_batch = AsyncMock(return_value=[[0.1], [0.2]])
    with patch("memory.embedding.EmbeddingService.from_config", return_value=service):
        embedding = MemoryEmbedding(config)
        assert await embedding.embed_texts(["a", "b"]) == [[0.1], [0.2]]
