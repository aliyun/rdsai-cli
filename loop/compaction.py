"""Context compaction for managing conversation history."""

from __future__ import annotations

from collections.abc import Sequence
from string import Template

import tiktoken
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

import prompts as prompts
from llm.llm import LLM
from utils.logging import logger

# Use cl100k_base encoding which works for most modern models (Qwen, GPT-4, etc.)
_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(messages: Sequence[BaseMessage]) -> int:
    """Count tokens in messages using tiktoken.

    Args:
        messages: The messages to count tokens for.

    Returns:
        Token count.
    """
    total_tokens = 0
    for msg in messages:
        # Add overhead per message (role, separators, etc.)
        total_tokens += 4
        total_tokens += len(_ENCODING.encode(_message_to_string(msg)))

        # Count tool call tokens if present
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                total_tokens += len(_ENCODING.encode(tc.get("name", "")))
                total_tokens += len(_ENCODING.encode(str(tc.get("args", {}))))

    logger.debug("Token count: {tokens}", tokens=total_tokens)
    return total_tokens


def _message_to_string(msg: BaseMessage) -> str:
    """Convert a LangChain message to string."""
    if isinstance(msg.content, str):
        return msg.content
    elif isinstance(msg.content, list):
        parts = []
        for part in msg.content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
        return " ".join(parts)
    return str(msg.content)


class ChainCompaction:
    """Compaction strategy that works directly with LangChain messages."""

    MAX_PRESERVED_MESSAGES = 2

    async def compact(self, messages: Sequence[BaseMessage], llm: LLM) -> tuple[list[BaseMessage], int]:
        """Compact a sequence of LangChain messages.

        Args:
            messages: The messages to compact.
            llm: The LLM to use for compaction.

        Returns:
            A tuple of (compacted messages, estimated token count).
        """
        history = list(messages)
        if not history:
            return history, 0

        # Find the index to start preserving messages
        preserve_start_index = len(history)
        n_preserved = 0
        for index in range(len(history) - 1, -1, -1):
            msg = history[index]
            if isinstance(msg, (HumanMessage, AIMessage)):
                n_preserved += 1
                if n_preserved == self.MAX_PRESERVED_MESSAGES:
                    preserve_start_index = index
                    break

        if n_preserved < self.MAX_PRESERVED_MESSAGES:
            # Not enough messages to compact
            token_count = count_tokens(history)
            return history, token_count

        to_compact = history[:preserve_start_index]
        to_preserve = history[preserve_start_index:]

        if not to_compact:
            token_count = count_tokens(to_preserve)
            return to_preserve, token_count

        # Convert history to string for the compact prompt
        history_text = "\n\n".join(
            f"## Message {i + 1}\nRole: {type(msg).__name__}\nContent: {_message_to_string(msg)}"
            for i, msg in enumerate(to_compact)
        )

        # Build the compact prompt using string template
        compact_template = Template(prompts.COMPACT)
        compact_prompt = compact_template.substitute(CONTEXT=history_text)

        # Call LLM directly for compaction
        logger.debug("Compacting context...")

        lc_messages = [
            SystemMessage(content="You are a helpful assistant that compacts conversation context."),
            HumanMessage(content=compact_prompt),
        ]

        # Stream the response
        final_chunk = None
        async for chunk in llm.chat_provider.astream(lc_messages):
            if final_chunk is None:
                final_chunk = chunk
            else:
                final_chunk += chunk

        if final_chunk is None:
            final_chunk = AIMessage(content="")

        if final_chunk.usage_metadata:
            logger.debug(
                "Compaction used {input} input tokens and {output} output tokens",
                input=final_chunk.usage_metadata.get("input_tokens", 0),
                output=final_chunk.usage_metadata.get("output_tokens", 0),
            )

        compacted_content = final_chunk.content if isinstance(final_chunk.content, str) else ""

        # Create the compacted message
        compacted_message = AIMessage(content=f"[Previous context has been compacted]\n\n{compacted_content}")

        # Build final message list
        compacted_messages: list[BaseMessage] = [compacted_message]
        compacted_messages.extend(to_preserve)

        # Calculate token count
        token_count = count_tokens(compacted_messages)

        return compacted_messages, token_count
