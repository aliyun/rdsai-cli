"""Thinking mode adapter for different LLM providers.

This module provides a unified interface for enabling thinking mode
and extracting thinking content across different model providers.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessageChunk


# Thinking enable parameters for each provider
# Key: provider_type, Value: bind() parameters to enable thinking
THINKING_BIND_PARAMS: dict[str, dict[str, Any]] = {
    # Qwen/DashScope uses enable_thinking in extra_body
    "qwen": {"extra_body": {"enable_thinking": True}},
    # DeepSeek uses the same format as Qwen
    "deepseek": {"extra_body": {"thinking": {"type": "enabled"}}},
    # Anthropic Claude uses thinking parameter with budget
    "anthropic": {"thinking": {"type": "enabled", "budget_tokens": 10000}},
    # OpenAI - o1/o3 series has built-in reasoning, no extra params needed
    "openai": {},
    "openai_compatible": {},
    "openai_legacy": {},
    "openai_responses": {},
    # Gemini thinking models have built-in thinking
    "gemini": {},
}


def get_thinking_bind_params(provider_type: str) -> dict[str, Any]:
    """Get the bind parameters to enable thinking mode for a provider.

    Args:
        provider_type: The type of the LLM provider.

    Returns:
        Dictionary of parameters to pass to model.bind().
        Empty dict if no special parameters needed.
    """
    return THINKING_BIND_PARAMS.get(provider_type, {})


def extract_thinking_content(chunk: AIMessageChunk, provider_type: str) -> str | None:
    """Extract thinking/reasoning content from a message chunk.

    Different providers return thinking content in different formats:
    - Qwen/DeepSeek: additional_kwargs['reasoning_content']
    - Anthropic: content blocks with type='thinking'
    - Gemini: additional_kwargs['thought']

    Args:
        chunk: The AI message chunk from streaming.
        provider_type: The type of the LLM provider.

    Returns:
        The thinking content string, or None if not present.
    """
    match provider_type:
        case "qwen" | "deepseek":
            # Qwen and DeepSeek use reasoning_content in additional_kwargs
            return chunk.additional_kwargs.get("reasoning_content")

        case "anthropic":
            # Anthropic returns thinking in content blocks
            if isinstance(chunk.content, list):
                for block in chunk.content:
                    if isinstance(block, dict) and block.get("type") == "thinking":
                        return block.get("thinking")
            # Also check additional_kwargs for some LangChain versions
            return chunk.additional_kwargs.get("thinking")

        case "gemini":
            # Gemini uses thought field
            return chunk.additional_kwargs.get("thought")

        case _:
            # Fallback: try common field names for unknown providers
            return (
                chunk.additional_kwargs.get("reasoning_content")
                or chunk.additional_kwargs.get("thinking")
                or chunk.additional_kwargs.get("thought")
                or chunk.additional_kwargs.get("reasoning")
            )
