"""Embedding wrapper for memory system."""

from __future__ import annotations

from config import Config
from llm.embedding import EmbeddingService
from utils.logging import logger


class MemoryEmbedding:
    """High-level embedding interface for the memory system."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._service: EmbeddingService | None = EmbeddingService.from_config(config)
        if self._service is None:
            logger.warning(
                "No embedding model configured. Memory semantic search will be disabled. "
                "Configure embedding_models in ~/.rdsai-cli/config.json."
            )

    @property
    def is_available(self) -> bool:
        """Whether embedding service is configured and available."""
        return self._service is not None

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        if self._service is None:
            logger.debug("Embedding service not available, returning empty embedding")
            return []
        return await self._service.generate_embedding(text)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if self._service is None:
            return []
        return await self._service.generate_embeddings_batch(texts)
