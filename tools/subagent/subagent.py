"""Delegate task to specialized subagent."""

import asyncio
import time
from pathlib import Path
from typing import Any, override

from loop.runtime import Runtime
from loop.toolset import BaseTool, ToolError, ToolOk, ToolReturnType, ToolResult
from loop import RunCancelled, run_loop, get_stream_or_none
from pydantic import BaseModel, Field
from loop.neoloop import NeoLoop

from tools.subagent.registry import get_registry
from tools.utils import load_desc
from utils.logging import logger


# --- Exception Types ---
class SubagentError(Exception):
    """Base exception for subagent errors."""

    pass


class SubagentConfigurationError(SubagentError):
    """Configuration error (e.g., missing required configuration, invalid settings)."""

    def __init__(self, message: str, original_error: str | None = None):
        self.original_error = original_error
        super().__init__(message)


class SubagentToolError(SubagentError):
    """Tool execution error within subagent."""

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        tool_errors: list[dict[str, Any]] | None = None,
        original_error: str | None = None,
    ):
        self.tool_name = tool_name
        self.tool_errors = tool_errors or []
        self.original_error = original_error
        super().__init__(message)


class SubagentExecutionError(SubagentError):
    """General execution error in subagent."""

    def __init__(self, message: str, original_error: str | None = None):
        self.original_error = original_error
        super().__init__(message)


class Params(BaseModel):
    """Parameters for Subagent tool."""

    subagent: str = Field(
        description=(
            "The subagent to delegate the task to. Available subagents are "
            "automatically discovered from the prompts directory."
        )
    )
    task_description: str = Field(description="Detailed description of the task to be performed by the subagent.")
    parameters: dict[str, Any] | None = Field(
        default=None, description="Optional parameters for the subagent (specific to each subagent type)."
    )

    @classmethod
    def model_json_schema(cls, **kwargs):
        """Override to dynamically include available subagents in description."""
        schema = super().model_json_schema(**kwargs)
        # Try to get registry and list available subagents
        try:
            registry = get_registry()
            available = registry.list_all()
            if available:
                subagent_desc = schema["properties"]["subagent"]["description"]
                schema["properties"]["subagent"]["description"] = (
                    f"{subagent_desc} Available subagents: {', '.join(available)}"
                )
        except Exception:
            pass  # If registry not available, use default description
        return schema


class Subagent(BaseTool[Params]):
    """subagent task to specialized subagent for execution.

    This tool allows the main agent to delegate complex tasks to specialized subagents
    that have dedicated system prompts and tool sets for specific domains.

    Subagents are automatically discovered from the prompts directory. To add a new
    subagent, simply create a new agent YAML file (e.g., `my_agent.yaml`) in the
    prompts directory and optionally create a custom executor if special handling
    is needed.
    """

    name: str = "Subagent"
    description: str = load_desc(Path(__file__).parent / "subagent.md")
    params: type[Params] = Params

    def __init__(self, runtime: Runtime, **kwargs: Any) -> None:
        """Initialize the subagent tool.

        Args:
            runtime: The runtime configuration (includes LLM, config, etc.).
        """
        super().__init__(**kwargs)
        self._runtime = runtime
        self._registry = get_registry()

    def _format_subagent_error(
        self,
        executor_name: str,
        error_type: str,
        original_message: str,
        tool_errors: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Format subagent error message with context.

        Args:
            executor_name: Name of the subagent executor.
            error_type: Type of error ('configuration', 'tool', 'execution').
            original_message: Original error message.
            tool_errors: List of tool error dictionaries with 'tool_name', 'error_message', 'brief'.
            context: Additional context information.

        Returns:
            Formatted error message.
        """
        parts = [f"{executor_name.capitalize()} execution failed"]

        # Add error type header
        if error_type == "configuration":
            parts.append("Configuration Error:")
        elif error_type == "tool":
            parts.append("Tool Execution Error:")
        else:
            parts.append("Error:")

        # Add original error message
        parts.append(original_message)

        # Add tool errors if available
        if tool_errors:
            parts.append("\nFailed Tools:")
            for err in tool_errors:
                tool_name = err.get("tool_name", "Unknown")
                error_msg = err.get("error_message", "Unknown error")
                brief = err.get("brief")
                if brief and brief != error_msg:
                    parts.append(f"  - {tool_name}: {error_msg} ({brief})")
                else:
                    parts.append(f"  - {tool_name}: {error_msg}")

        # Add context information if available
        if context:
            context_parts = []
            if "task_description" in context:
                context_parts.append(f"Task: {context['task_description']}")
            if "parameters" in context and context["parameters"]:
                params_str = ", ".join(f"{k}={v}" for k, v in context["parameters"].items())
                context_parts.append(f"Parameters: {params_str}")
            if context_parts:
                parts.append(f"\nContext: {'; '.join(context_parts)}")

        return "\n".join(parts)

    def _raise_if_tool_errors(
        self,
        executor_name: str,
        tool_errors: list[dict[str, Any]],
        task_description: str,
        parameters: dict[str, Any] | None,
        original_error: str | None = None,
    ) -> None:
        """Check for tool errors and raise SubagentToolError if any exist.

        Args:
            executor_name: Name of the subagent executor.
            tool_errors: List of tool error dictionaries.
            task_description: Task description from user.
            parameters: Optional parameters for the subagent.
            original_error: Optional original error message (for exception cases).

        Raises:
            SubagentToolError: If tool_errors is not empty.
        """
        if not tool_errors:
            return

        # Extract error messages from tool errors
        error_messages = [err["error_message"] for err in tool_errors]
        primary_error = error_messages[0] if error_messages else (original_error or "Unknown error")

        # Build comprehensive error message
        error_msg = self._format_subagent_error(
            executor_name=executor_name,
            error_type="tool",
            original_message=primary_error,
            tool_errors=tool_errors,
            context={
                "task_description": task_description,
                "parameters": parameters,
            },
        )

        raise SubagentToolError(
            message=error_msg,
            tool_errors=tool_errors,
            original_error=original_error,
        )

    async def _execute_subagent(
        self,
        executor_name: str,
        task_description: str,
        parameters: dict[str, Any] | None,
    ) -> str:
        """Execute a subagent using its executor.

        Args:
            executor_name: Name of the subagent executor.
            task_description: Task description from user.
            parameters: Optional parameters for the subagent.

        Returns:
            Execution result summary.
        """
        # Get executor from registry
        executor = self._registry.get(executor_name)
        if executor is None:
            available = ", ".join(self._registry.list_all())
            raise ValueError(
                f"Unknown subagent: {executor_name}. Available subagents: {available if available else 'none'}"
            )

        # Load agent
        agent = await executor.load_agent(self._runtime)

        # Build prompt
        prompt = await executor.build_prompt(task_description, parameters, self._runtime)

        # Create loop
        loop = NeoLoop(agent)

        # Get main agent's stream (if available) to forward subagent events
        main_stream = get_stream_or_none()

        # Collect results from subagent execution
        result_messages: list[str] = []
        tool_errors: list[dict[str, Any]] = []
        cancel_event = asyncio.Event()

        async def collect_results(stream):
            """Collect results and errors from subagent execution, and forward events to main agent.

            Collects:
            - Text output from TextPart messages
            - Tool errors from ToolResult messages

            Forwards:
            - All event messages to main agent's stream (if available)
            """
            from loop.types import TextPart

            try:
                while True:
                    msg = await stream.receive()

                    # Forward all events to main agent's stream
                    if main_stream is not None:
                        try:
                            main_stream.loop_side.send(msg)
                        except Exception:
                            # Log but don't fail if forwarding fails
                            # Main stream may be shut down or unavailable
                            logger.debug("Failed to forward subagent event to main stream")

                    # Collect text content from TextPart messages
                    if isinstance(msg, TextPart) and msg.text:
                        result_messages.append(msg.text)

                    # Collect tool errors from ToolResult messages
                    if isinstance(msg, ToolResult):
                        if isinstance(msg.result, ToolError):
                            tool_errors.append(
                                {
                                    "tool_name": msg.name or "Unknown",
                                    "error_message": msg.result.message,
                                    "brief": msg.result.brief,
                                    "output": msg.result.output,
                                }
                            )
            except Exception:
                pass  # Stream closed or queue shutdown

        try:
            await run_loop(
                loop,
                prompt,
                collect_results,
                cancel_event,
            )
        except RunCancelled:
            return f"{executor_name.capitalize()} task was cancelled."
        except Exception as e:
            logger.exception("{name} subagent execution failed", name=executor_name)
            # Check if we have tool errors - prioritize them
            self._raise_if_tool_errors(
                executor_name=executor_name,
                tool_errors=tool_errors,
                task_description=task_description,
                parameters=parameters,
                original_error=str(e),
            )

            # General execution error (only reached if no tool errors)
            raise SubagentExecutionError(
                message=f"{executor_name.capitalize()} execution failed: {e}",
                original_error=str(e),
            ) from e

        # Check if we have tool errors even though execution completed
        # (This can happen if tools failed but LLM continued)
        self._raise_if_tool_errors(
            executor_name=executor_name,
            tool_errors=tool_errors,
            task_description=task_description,
            parameters=parameters,
        )

        # Return collected results
        if result_messages:
            return "\n".join(result_messages)
        return f"{executor_name.capitalize()} task completed successfully."

    @override
    async def __call__(self, params: Params) -> ToolReturnType:
        """Execute the delegate tool."""
        start_time = time.time()

        try:
            result_summary = await self._execute_subagent(
                params.subagent,
                params.task_description,
                params.parameters,
            )

            execution_time = time.time() - start_time

            # Format output
            output = f"""Subagent: {params.subagent}
Task: {params.task_description}
Execution Time: {execution_time:.2f} seconds

Result:
{result_summary}
"""

            return ToolOk(
                output=output,
                message=f"Successfully task to {params.subagent} subagent",
                brief=f"{params.subagent} completed in {execution_time:.1f}s",
            )

        except SubagentConfigurationError as e:
            # Configuration errors - provide clear, actionable message
            return ToolError(
                message=str(e),
                brief=e.original_error or str(e),
            )
        except SubagentToolError as e:
            # Tool errors - include tool details
            return ToolError(
                message=str(e),
                brief=e.tool_errors[0]["brief"] if e.tool_errors else str(e),
            )
        except SubagentExecutionError as e:
            # General execution errors
            return ToolError(
                message=str(e),
                brief=e.original_error or f"{params.subagent} failed",
            )
        except ValueError as e:
            # Legacy ValueError support (for backward compatibility)
            return ToolError(
                message=str(e),
                brief=str(e),
            )
        except Exception as e:
            logger.exception("Subagent execution failed")
            return ToolError(
                message=f"Failed to execute subagent task to {params.subagent}: {e}",
                brief=f"{params.subagent} failed",
            )
