"""LLM provider exceptions and error types."""

from __future__ import annotations
from typing import Any
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.messages import AIMessage


# --- Chat Provider Errors ---
class ChatProviderError(Exception):
    """Base exception for chat provider errors."""

    pass


class LLMInvocationError(ChatProviderError):
    """Error during LLM model invocation.

    This exception wraps provider-specific errors into a unified type,
    making it easier to handle errors from different LLM providers.

    Attributes:
        provider: The provider type (e.g., "gemini", "anthropic", "openai").
        model: The model name.
        original_error: The original exception from the provider.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        model: str,
        original_error: BaseException | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.original_error = original_error

    def __str__(self) -> str:
        return f"[{self.provider}/{self.model}] {super().__str__()}"


class APIConnectionError(ChatProviderError):
    """Error connecting to the API."""

    pass


class APIEmptyResponseError(ChatProviderError):
    """API returned empty response."""

    pass


class APIStatusError(ChatProviderError):
    """API returned error status code."""

    def __init__(self, message, *, status_code: int, request: Any):
        super().__init__(message)
        self.status_code = status_code


class APITimeoutError(ChatProviderError):
    """API request timed out."""

    pass


# --- Mock Provider (for testing) ---
class MockChatProvider(BaseChatModel):
    """Mock chat provider for testing purposes."""

    responses: list = []
    model_name: str = "mock"

    def __init__(self, responses: list | None = None, **kwargs):
        super().__init__(**kwargs)
        self.responses = responses or []

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Mock response"))])

    @property
    def _llm_type(self):
        return "mock"
