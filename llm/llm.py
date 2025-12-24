from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel

from config import USER_AGENT
from config.llm import ModelCapability

if TYPE_CHECKING:
    from config import LLMModel, LLMProvider


@dataclass(slots=True)
class LLM:
    chat_provider: BaseChatModel
    max_context_size: int
    capabilities: set[ModelCapability]
    _model_name: str
    _provider_type: str
    _thinking_enabled: bool = False

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_type(self) -> str:
        """The type of the LLM provider."""
        return self._provider_type

    @property
    def thinking_enabled(self) -> bool:
        """Whether thinking mode is enabled."""
        return self._thinking_enabled

    def set_thinking_enabled(self, enabled: bool) -> None:
        """Set thinking mode enabled/disabled."""
        self._thinking_enabled = enabled


def create_llm(
    provider: LLMProvider,
    model: LLMModel,
) -> LLM:
    chat_provider: BaseChatModel

    match provider.type:
        case "qwen":
            # Qwen uses Qwen API (DashScope)
            from langchain_qwq import ChatQwQ

            chat_provider = ChatQwQ(
                model=model.model,
                base_url=provider.base_url,
                api_key=provider.api_key,
                default_headers={
                    "User-Agent": USER_AGENT,
                    **(provider.custom_headers or {}),
                },
                streaming=True,
                stream_usage=True,
            )

        case "openai":
            # OpenAI official API
            from langchain_openai import ChatOpenAI

            chat_provider = ChatOpenAI(
                model=model.model,
                base_url=provider.base_url,
                api_key=provider.api_key,
                default_headers={
                    "User-Agent": USER_AGENT,
                    **(provider.custom_headers or {}),
                },
                stream_usage=True,
                streaming=True,
            )

        case "deepseek":
            from langchain_deepseek import ChatDeepSeek

            chat_provider = ChatDeepSeek(
                model=model.model,
                base_url=provider.base_url,
                api_key=provider.api_key,
                default_headers={
                    "User-Agent": USER_AGENT,
                    **(provider.custom_headers or {}),
                },
                stream_usage=True,
                streaming=True,
            )

        case "anthropic":
            # Anthropic Claude
            from langchain_anthropic import ChatAnthropic

            chat_provider = ChatAnthropic(
                model_name=model.model,
                api_key=provider.api_key,
                base_url=provider.base_url,
                default_headers={
                    "User-Agent": USER_AGENT,
                    **(provider.custom_headers or {}),
                },
                streaming=True,
                stream_usage=True,
                timeout=None,
                stop=None,
            )

        case "gemini":
            # Google Gemini
            from langchain_google_genai import ChatGoogleGenerativeAI

            chat_provider = ChatGoogleGenerativeAI(
                model=model.model,
                google_api_key=provider.api_key,
            )

        case "openai_compatible" | "openai_legacy" | "openai_responses":
            # OpenAI compatible API (third-party providers)
            from langchain_openai import ChatOpenAI

            chat_provider = ChatOpenAI(
                model=model.model,
                base_url=provider.base_url,
                api_key=provider.api_key,
                default_headers={
                    "User-Agent": USER_AGENT,
                    **(provider.custom_headers or {}),
                },
                stream_usage=True,
                streaming=True,
            )

        case _:
            raise ValueError(f"Unsupported LLM provider: {provider.type}")

    return LLM(
        chat_provider=chat_provider,
        max_context_size=model.max_context_size,
        capabilities=model.capabilities or set(),
        _model_name=model.model,
        _provider_type=provider.type,
    )
