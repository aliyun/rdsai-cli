"""LangGraph node implementations for the agent."""

from __future__ import annotations

import json
from typing import Any, Literal

from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.types import interrupt

from utils.logging import logger
from loop.state import AgentState, ApprovalInterrupt
from loop.toolset import (
    CustomToolset,
    ToolOk,
    ToolResult,
    current_tool_call,
)
from loop.types import ToolCall, FunctionBody, TextPart, ThinkPart
from events.message import ApprovalPending, ApprovalGranted, ApprovalRejected
from loop.agent import Agent
from llm.thinking import get_thinking_bind_params, extract_thinking_content
from utils.exceptions import LLMInvocationError

# Tools that require approval (can be extended)
TOOLS_REQUIRING_APPROVAL = {
    "DDLExecutor",  # DDL modifications require user approval
    "SysbenchPrepare",  # Creates test tables and data
    "SysbenchRun",  # Performance testing can put significant load on database
    "SysbenchCleanup",  # Removes test data
}


def needs_approval(tool_name: str, tool_args: dict[str, Any]) -> bool:
    """Check if a tool call requires user approval."""
    return tool_name in TOOLS_REQUIRING_APPROVAL


def get_tool_description(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Generate a human-readable description for a tool call."""
    if tool_args:
        # Try to find a descriptive parameter
        for key in ["description", "query", "sql", "sql_statement", "command", "path", "content"]:
            if key in tool_args:
                value = tool_args[key]
                if isinstance(value, str) and len(value) > 100:
                    return f"{tool_name}: {value[:97]}..."
                return f"{tool_name}: {value}"
        # Fallback to first argument
        first_key = next(iter(tool_args))
        return f"{tool_name}({first_key}=...)"
    return tool_name


async def agent_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """LLM invocation node.

    Calls the LLM with current messages and returns the response.

    Note: Context injection (Memory Bank, query results) is handled at the message
    level by neoloop.py using the layered context strategy, not in the system prompt.
    """
    # Get agent and LLM from config
    agent: Agent = config["configurable"]["agent"]
    llm = config["configurable"]["llm"]
    stream_send = config["configurable"].get("stream_send")
    thinking_enabled = config["configurable"].get("thinking_enabled", False)

    # Build messages with system prompt
    system_prompt = agent.system_prompt
    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])

    # Bind tools to LLM
    lc_tools = []
    for tool in agent.toolset.tools:
        lc_tools.append(
            StructuredTool(
                name=tool.name,
                description=tool.description,
                args_schema=tool.params,
                func=lambda **kwargs: None,  # Placeholder, we handle execution in tools_node
            )
        )

    if lc_tools:
        model = llm.chat_provider.bind_tools(lc_tools)
    else:
        model = llm.chat_provider

    # Enable thinking mode using provider-specific parameters
    logger.debug(f"Thinking enabled: {thinking_enabled}")
    model_service = model.bind(**get_thinking_bind_params(llm.provider_type)) if thinking_enabled else model

    # Stream the response
    final_chunk = None

    try:
        async for chunk in model_service.astream(messages):
            if final_chunk is None:
                final_chunk = chunk
            else:
                final_chunk += chunk
            # Extract and send thinking content using provider-specific adapter
            if stream_send and thinking_enabled:
                thinking_content = extract_thinking_content(chunk, llm.provider_type)
                if thinking_content:
                    stream_send(ThinkPart(think=thinking_content))

            # Stream text content to UI
            if stream_send and isinstance(chunk.content, str) and chunk.content:
                stream_send(TextPart(text=chunk.content))

    except Exception as e:
        # Wrap provider-specific errors into unified LLMInvocationError
        raise LLMInvocationError(
            str(e),
            provider=llm.provider_type,
            model=llm.model_name,
            original_error=e,
        ) from e

    if final_chunk is None:
        final_chunk = AIMessage(content="")

    # Get yolo state to check if approval is needed
    yolo = state.get("yolo", False)

    # Send tool calls to UI via message center
    # For tools requiring approval, send ToolCall first, then ApprovalPending
    # This ensures the tool appears in UI before the approval request
    for tc in final_chunk.tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_call_id = tc["id"]

        # Always send ToolCall first so it appears in UI
        tool_call = ToolCall(
            id=tool_call_id,
            type="function",
            function=FunctionBody(
                name=tool_name,
                arguments=json.dumps(tool_args, ensure_ascii=False) if tool_args else None,
            ),
        )
        if stream_send:
            stream_send(tool_call)

        # Check if this tool needs approval
        needs_approval_for_this_tool = not yolo and needs_approval(tool_name, tool_args)

        if needs_approval_for_this_tool:
            # For tools requiring approval, send ApprovalPending immediately after ToolCall
            # This will mark the tool as "Waiting for approval" in UI
            if stream_send:
                stream_send(ApprovalPending(tool_call_id=tool_call_id))

    # Calculate token usage
    new_token_count = state.get("token_count", 0)
    if final_chunk.usage_metadata:
        new_token_count = final_chunk.usage_metadata.get("total_tokens", new_token_count)

    return {
        "messages": [final_chunk],
        "token_count": new_token_count,
        "step_number": state.get("step_number", 0) + 1,
    }


async def tools_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Tool execution node.

    Executes tool calls from the last AI message.
    Supports human-in-the-loop approval via interrupt().
    """
    agent: Agent = config["configurable"]["agent"]
    stream_send = config["configurable"].get("stream_send")

    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    tool_calls = last_message.tool_calls
    yolo = state.get("yolo", False)

    results: list[ToolMessage] = []

    # Get auto-approved actions from config
    auto_approve_actions = config["configurable"].get("auto_approve_actions", set())

    for tc in tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_call_id = tc["id"]

        # Check if approval is needed
        # Skip approval if: yolo mode, already auto-approved for session, or doesn't need approval
        if not yolo and tool_name not in auto_approve_actions and needs_approval(tool_name, tool_args):
            # ToolCall and ApprovalPending were already sent in agent_node
            # Tool should now be showing "Waiting for approval" in UI

            # Human in the Loop: interrupt for approval
            approval_request: ApprovalInterrupt = {
                "type": "approval",
                "tool_name": tool_name,
                "tool_args": tool_args,
                "description": get_tool_description(tool_name, tool_args),
            }

            # This will pause the graph and return control to the caller
            # When resumed with Command(resume=response), interrupt() returns the response
            response = interrupt(approval_request)
            if response == "reject":
                # Send ApprovalRejected to UI to mark the tool as rejected
                if stream_send:
                    stream_send(ApprovalRejected(tool_call_id=tool_call_id))
                results.append(
                    ToolMessage(
                        tool_call_id=tool_call_id,
                        content="Tool execution rejected by user.",
                        name=tool_name,
                    )
                )
                continue

            # If approved, send ApprovalGranted to UI
            # This will change the tool status from "Waiting for approval" to "Using"
            if stream_send:
                stream_send(ApprovalGranted(tool_call_id=tool_call_id))

        # Execute the tool
        tool_result = await _execute_tool(agent.toolset, tool_call_id, tool_name, tool_args)

        # Notify UI of tool result
        stream_send(tool_result)

        # Convert to ToolMessage
        if isinstance(tool_result.result, ToolOk):
            content = tool_result.result.output
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
        else:
            content = f"Error: {tool_result.result.message}"
            if tool_result.result.output:
                content += f"\n{tool_result.result.output}"

        results.append(
            ToolMessage(
                tool_call_id=tool_call_id,
                content=content,
                name=tool_name,
            )
        )

    return {"messages": results}


async def _execute_tool(
    toolset: CustomToolset,
    tool_call_id: str,
    tool_name: str,
    tool_args: dict[str, Any],
) -> ToolResult:
    """Execute a single tool call."""
    # Create a ToolCall object for the toolset
    tool_call = ToolCall(
        id=tool_call_id,
        type="function",
        function=FunctionBody(
            name=tool_name,
            arguments=json.dumps(tool_args),
        ),
    )

    # Set current tool call context
    token = current_tool_call.set(tool_call)
    try:
        return await toolset.handle(tool_call)
    finally:
        current_tool_call.reset(token)


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Determine the next node based on current state.

    Returns:
        "tools" if there are tool calls to execute
        "end" if the conversation should end
    """
    last_message = state["messages"][-1]

    # Check if the last message has tool calls
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return "end"
