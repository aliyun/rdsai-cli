"""LLM provider and model configuration.

This module contains configuration classes for LLM providers and models,
including type definitions for provider types and model capabilities.
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, SecretStr, field_serializer


# Type definitions moved here to avoid circular imports with llm/llm.py
type ProviderType = Literal[
    "qwen",
    "openai",
    "openai_compatible",
    "openai_legacy",
    "openai_responses",
    "deepseek",
    "anthropic",
    "gemini",
    "_chaos",
]
"""Supported LLM provider types."""

type ModelCapability = Literal["image_in"]
"""Model capabilities (e.g., image input support)."""

ALL_MODEL_CAPABILITIES: set[ModelCapability] = set(get_args(ModelCapability))
"""Set of all supported model capabilities."""


class LLMProvider(BaseModel):
    """LLM provider configuration."""

    type: ProviderType
    """Provider type"""
    base_url: str
    """API base URL"""
    api_key: SecretStr
    """API key"""
    custom_headers: dict[str, str] | None = None
    """Custom headers to include in API requests"""

    @field_serializer("api_key", when_used="json")
    def dump_secret(self, v: SecretStr):
        return v.get_secret_value()


class LLMModel(BaseModel):
    """LLM model configuration."""

    provider: str
    """Provider name"""
    model: str
    """Model name"""
    max_context_size: int
    """Maximum context size (unit: tokens)"""
    max_output_tokens: int | None = None
    """Maximum output tokens (required for some providers like Anthropic)"""
    capabilities: set[ModelCapability] | None = None
    """Model capabilities"""
