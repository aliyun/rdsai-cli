"""NeoLoop - The main agent implementation using LangGraph."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from llm.llm import LLM

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langgraph.types import Command
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from loop.nodes import agent_node, should_continue, tools_node
from loop.state import AgentState

from config import ModelCapability
from loop import (
    LLMNotSet,
    Loop,
    StatusSnapshot,
    stream_send,
    get_stream_or_none,
)
from loop.agent import Agent
from loop.compaction import ChainCompaction
from loop.context import ContextManager
from loop.types import ContentPart
from loop.runtime import Runtime
from database import format_query_context_for_agent
from database.service import get_service
from utils.logging import logger
from events.message import (
    ApprovalRequest,
    ApprovalResponse,
    StepBegin,
    StepInterrupted,
    StatusUpdate,
)

COMPACT_THRESHOLD = 0.92  # Auto-compact when context usage reaches 92%


def create_agent_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Create and compile the agent graph.

    Args:
        checkpointer: Optional checkpointer for state persistence.
                     If None, uses MemorySaver for in-memory checkpointing.

    Returns:
        Compiled LangGraph ready for execution.
    """
    # Use MemorySaver as default if no checkpointer provided
    if checkpointer is None:
        checkpointer = MemorySaver()

    # Build the graph
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tools_node)

    # Define edges
    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        },
    )
    builder.add_edge("tools", "agent")

    # Compile with checkpointer for state persistence and human-in-the-loop
    # Note: We use interrupt() function inside tools_node for dynamic approval,
    # not interrupt_before/interrupt_after which are for static interruption.
    return builder.compile(
        checkpointer=checkpointer,
    )


class NeoLoop(Loop):
    """The loop of RDSAI CLI using LangGraph."""

    def __init__(
        self,
        agent: Agent,
        *,
        checkpointer: BaseCheckpointSaver | None = None,
    ):
        """Initialize the loop.

        Args:
            agent: The agent configuration (tools, system prompt).
            checkpointer: Optional LangGraph checkpointer for state persistence.
        """
        self._agent = agent
        self._runtime = agent.runtime

        # Create the LangGraph
        self._graph: CompiledStateGraph = create_agent_graph(checkpointer)

        # Thread ID for this session (used for checkpointing)
        self._thread_id = str(uuid.uuid4())

        # Token tracking
        self._token_count = 0

        # Auto-approved actions for this session
        self._auto_approve_actions: set[str] = set()

        # Context manager for session-aware context injection
        self._context_manager = ContextManager()

    @property
    def name(self) -> str:
        return self._agent.name

    @property
    def model_name(self) -> str:
        return self._runtime.llm.model_name if self._runtime.llm else ""

    @property
    def model_capabilities(self) -> set[ModelCapability] | None:
        if self._runtime.llm is None:
            return None
        return self._runtime.llm.capabilities

    @property
    def runtime(self) -> Runtime:
        return self._runtime

    @property
    def status(self) -> StatusSnapshot:
        return StatusSnapshot(context_usage=self._context_usage, yolo=self._runtime.yolo)

    @property
    def _context_usage(self) -> float:
        if self._runtime.llm is not None and self._runtime.llm.max_context_size > 0:
            return self._token_count / self._runtime.llm.max_context_size
        return -1.0  # -1 indicates unknown/invalid

    @property
    def thread_id(self) -> str:
        """Get the current thread ID for checkpointing."""
        return self._thread_id

    @property
    def toolset(self):
        """Get the dynamic toolset for runtime tool management.

        Use this property to add or remove tools at runtime:
            loop.toolset.add_tool(my_tool)
            loop.toolset.remove_tools_by(lambda t: t.name.startswith("mcp_"))
        """
        return self._agent.toolset

    def set_yolo(self, yolo: bool) -> None:
        """Set the yolo mode (auto-approve all actions)."""
        self._runtime.yolo = yolo

    def switch_model(self, llm: LLM) -> None:
        """Switch to a different model at runtime.

        Args:
            llm: The new LLM instance to use.
        """
        self._runtime.set_llm(llm)

    async def run(self, user_input: str | list[ContentPart]):
        """Run the agent with the given user input.

        Args:
            user_input: The user input to the agent.

        Raises:
            LLMNotSet: When the LLM is not set.
            LLMNotSupported: When the LLM does not have required capabilities.
            MaxStepsReached: When the maximum number of steps is reached.
            asyncio.CancelledError: When the run is cancelled by user.
        """
        if self._runtime.llm is None:
            raise LLMNotSet()

        # Build layered context injection
        # Layer 2: Context Injection (Memory Bank + Query Context)
        # Uses ContextManager for session-aware injection (avoids redundant Memory Bank injection)
        db_svc = get_service()
        query_context = db_svc.consume_last_query_context() if db_svc else None

        # Set query context if available (database context is auto-loaded by ContextManager)
        if query_context:
            query_context_str = format_query_context_for_agent(query_context)
            self._context_manager.set_query_context(query_context_str)

        # Build context and wrap user input
        if isinstance(user_input, str):
            content = self._context_manager.wrap_user_input(user_input)
            human_message = HumanMessage(content=content)
        else:
            # Convert ContentPart list to string for now
            text_content = "".join(p.text for p in user_input if hasattr(p, "text"))
            content = self._context_manager.wrap_user_input(text_content)
            human_message = HumanMessage(content=content)

        # Prepare config with agent and LLM
        config = {
            "configurable": {
                "thread_id": self._thread_id,
                "agent": self._agent,
                "llm": self._runtime.llm,
                "stream_send": stream_send,
                "thinking_enabled": self._runtime.llm.thinking_enabled if self._runtime.llm else False,
                "auto_approve_actions": self._auto_approve_actions,
            },
            "recursion_limit": 100,
        }

        # Initial state
        input_state: dict[str, Any] | Command = {
            "messages": [human_message],
            "token_count": self._token_count,
            "step_number": 0,
            "yolo": self._runtime.yolo,
        }

        step_no = 0

        while True:
            step_no += 1
            stream_send(StepBegin(n=step_no))

            logger.debug("Running graph step {step_no}", step_no=step_no)

            # Update config to ensure auto_approve_actions always references the latest set
            # This is important because LangGraph may copy the config when invoking nodes
            config["configurable"]["auto_approve_actions"] = self._auto_approve_actions

            try:
                # Run the graph (may pause at interrupt())
                result = await self._graph.ainvoke(input_state, config)

                # Update token count from result
                self._token_count = result.get("token_count", self._token_count)
                stream_send(StatusUpdate(status=self.status))

                # Auto-compact if context usage exceeds threshold
                if self._should_auto_compact():
                    logger.info("Context usage at {usage:.1%}, triggering auto-compaction", usage=self._context_usage)
                    await self.compact()

                # Check current state for interrupts
                state = self._graph.get_state(config)

                if state.next:
                    # Graph is paused - check if there's an interrupt
                    if state.tasks and state.tasks[0].interrupts:
                        interrupt_value = state.tasks[0].interrupts[0].value
                        logger.debug("Interrupt value: {value}", value=interrupt_value)

                        if isinstance(interrupt_value, dict) and interrupt_value.get("type") == "approval":
                            # Handle approval request
                            response = await self._handle_approval(interrupt_value)

                            if response == "approve_for_session":
                                # Add to auto-approve list
                                self._auto_approve_actions.add(interrupt_value["tool_name"])
                                response = "approve"

                            # Resume with the response
                            input_state = Command(resume=response)
                            continue
                        else:
                            # Unknown interrupt type, try to continue
                            logger.warning("Unknown interrupt type: {value}", value=interrupt_value)
                            input_state = Command(resume=None)
                            continue
                    else:
                        # Graph paused but no interrupt - shouldn't happen normally
                        logger.warning("Graph paused without interrupt, next={next}", next=state.next)
                        break
                else:
                    # Graph completed normally
                    logger.debug("Graph completed at step {step_no}", step_no=step_no)
                    break

            except asyncio.CancelledError:
                stream_send(StepInterrupted())
                # User canceled the run - clean incomplete tool calls in conversation history
                await self._cleanup_incomplete_messages(config)
                raise

            except Exception as e:
                stream_send(StepInterrupted())
                raise

    async def _handle_approval(self, interrupt_value: dict[str, Any]) -> str:
        """Handle an approval request from the graph.

        Args:
            interrupt_value: The interrupt payload containing tool info.

        Returns:
            "approve", "approve_for_session", or "reject"
        """
        tool_name = interrupt_value.get("tool_name", "")

        # Check if already auto-approved
        if tool_name in self._auto_approve_actions:
            logger.debug("Tool {tool_name} is auto-approved", tool_name=tool_name)
            return "approve"

        if self._runtime.yolo:
            logger.debug("YOLO mode, auto-approving {tool_name}", tool_name=tool_name)
            return "approve"

        # Send approval request to UI and wait for response
        request = ApprovalRequest(
            tool_call_id=str(uuid.uuid4()),
            sender=self.name,
            action=tool_name,
            description=interrupt_value.get("description", ""),
            tool_args=interrupt_value.get("tool_args"),
        )

        stream_send(request)
        response = await request.wait()

        logger.debug("Received approval response: {response}", response=response)

        match response:
            case ApprovalResponse.APPROVE:
                return "approve"
            case ApprovalResponse.APPROVE_FOR_SESSION:
                return "approve_for_session"
            case ApprovalResponse.REJECT:
                return "reject"
        return "reject"

    async def _cleanup_incomplete_messages(self, config: dict[str, Any]) -> None:
        """Cleanup incomplete messages in conversation history after cancellation.

        When user cancels during tool execution, the conversation history may have
        AIMessage with tool_calls but no corresponding ToolMessage responses.
        This causes LLM API errors on the next request.

        This method removes the incomplete AIMessage from conversation history.
        """
        state = self._graph.get_state(config)
        messages = state.values.get("messages", [])

        if not messages:
            return
        logger.debug("Cleaning up incomplete messages")
        # Find AIMessages with tool_calls that have incomplete responses
        tool_call_ids_with_response: set[str] = set()
        messages_to_remove: list[RemoveMessage] = []

        # First pass: collect all tool_call_ids that have responses
        for msg in messages:
            if isinstance(msg, ToolMessage):
                tool_call_ids_with_response.add(msg.tool_call_id)

        # Second pass: find AIMessages with incomplete tool_calls
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                # Check if any tool_call is missing a response
                has_incomplete = any(tc["id"] not in tool_call_ids_with_response for tc in msg.tool_calls)
                if has_incomplete and hasattr(msg, "id") and msg.id:
                    messages_to_remove.append(RemoveMessage(id=msg.id))

        if not messages_to_remove:
            return

        logger.info("Removing {n} incomplete AIMessage(s) after cancellation", n=len(messages_to_remove))

        # Remove incomplete messages from state
        self._graph.update_state(config, {"messages": messages_to_remove})

    def reset_context(self) -> None:
        """Reset the conversation context by generating a new thread ID.

        This effectively starts a fresh conversation while preserving
        all other configurations (agent, runtime, yolo mode, etc.).
        """
        self._thread_id = str(uuid.uuid4())
        self._token_count = 0
        self._auto_approve_actions.clear()
        self._context_manager.reset_session()
        logger.info("Context reset, new thread_id: {thread_id}", thread_id=self._thread_id)

    async def compact(self) -> bool:
        """Compact the conversation context to reduce token usage.

        This method compresses older messages while preserving recent ones,
        helping to stay within context limits for long conversations.

        Returns:
            True if compaction was performed, False if not needed or failed.
        """
        if self._runtime.llm is None:
            logger.warning("Cannot compact: LLM not set")
            return False

        # Get current state
        config = {"configurable": {"thread_id": self._thread_id}}
        state = self._graph.get_state(config)

        messages = state.values.get("messages", [])
        if not messages:
            logger.debug("No messages to compact")
            return False

        logger.info("Starting context compaction with {n} messages", n=len(messages))

        # Perform compaction
        compactor = ChainCompaction()
        compacted_messages, estimated_tokens = await compactor.compact(messages, self._runtime.llm)

        if len(compacted_messages) >= len(messages):
            logger.debug("Compaction not needed: message count unchanged")
            return False

        # Build update: remove old messages, add compacted ones
        # We need to remove all existing messages and add the compacted ones
        remove_ops = [RemoveMessage(id=msg.id) for msg in messages if hasattr(msg, "id") and msg.id]

        # Update state with compacted messages
        self._graph.update_state(config, {"messages": remove_ops + compacted_messages, "token_count": estimated_tokens})

        # Update local token count
        self._token_count = estimated_tokens

        logger.info(
            "Context compacted: {old} -> {new} messages, estimated {tokens} tokens",
            old=len(messages),
            new=len(compacted_messages),
            tokens=estimated_tokens,
        )

        # Notify UI of status update (only if stream is available, i.e. inside agent loop)
        if (stream := get_stream_or_none()) is not None:
            stream.loop_side.send(StatusUpdate(status=self.status))

        return True

    def _should_auto_compact(self) -> bool:
        """Check if auto-compaction should be triggered.

        Returns:
            True if context usage exceeds the threshold.
        """
        return (
            self._runtime.llm is not None
            and self._runtime.llm.max_context_size > 0
            and self._context_usage >= COMPACT_THRESHOLD
        )

    def get_state_history(self):
        """Get the state history for this session.

        Returns:
            Iterator of state snapshots.
        """
        config = {"configurable": {"thread_id": self._thread_id}}
        return self._graph.get_state_history(config)
