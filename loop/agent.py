"""Agent loading and configuration."""

from __future__ import annotations

import importlib
import inspect
import string
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from config import Config, Session
from loop.agentspec import ResolvedAgentSpec, load_agent_spec
from loop.runtime import BuiltinSystemPromptArgs, Runtime
from loop.toolset import BaseTool, DynamicToolset
from utils.logging import logger


@dataclass(frozen=True, slots=True, kw_only=True)
class Agent:
    """The loaded agent configuration.

    Attributes:
        name: The name of the agent.
        system_prompt: The system prompt for the agent.
        toolset: The toolset available to the agent (supports dynamic modification).
    """

    name: str
    system_prompt: str
    toolset: DynamicToolset
    runtime: Runtime


async def load_agent(
    agent_file: Path,
    runtime: Runtime,
) -> Agent:
    """Load agent from specification file.

    Args:
        agent_file: Path to the agent specification file.
        runtime: The runtime configuration (includes MCP config).

    Returns:
        Loaded Agent instance.

    Raises:
        FileNotFoundError: If the agent spec file does not exist.
        AgentSpecError: If the agent spec is not valid.
    """
    logger.info("Loading agent: {agent_file}", agent_file=agent_file)
    agent_spec = load_agent_spec(agent_file)

    system_prompt = _load_system_prompt(
        agent_spec.system_prompt_path,
        agent_spec.system_prompt_args,
        runtime.builtin_args,
    )

    tool_deps = {
        ResolvedAgentSpec: agent_spec,
        Runtime: runtime,
        Config: runtime.config,
        BuiltinSystemPromptArgs: runtime.builtin_args,
        Session: runtime.session,
    }
    tools = agent_spec.tools
    if agent_spec.exclude_tools:
        logger.debug("Excluding tools: {tools}", tools=agent_spec.exclude_tools)
        tools = [tool for tool in tools if tool not in agent_spec.exclude_tools]
    toolset = DynamicToolset()
    bad_tools = _load_tools(toolset, tools, tool_deps)
    if bad_tools:
        raise ValueError(f"Invalid tools: {bad_tools}")

    # MCP tools are loaded asynchronously in the background via /mcp commands
    # or can be connected manually using /mcp connect <server>
    return Agent(
        name=agent_spec.name,
        system_prompt=system_prompt,
        toolset=toolset,
        runtime=runtime,
    )


def _load_system_prompt(path: Path, args: dict[str, str], builtin_args: BuiltinSystemPromptArgs) -> str:
    """Load and substitute the system prompt."""
    logger.info("Loading system prompt: {path}", path=path)
    system_prompt = path.read_text(encoding="utf-8").strip()
    logger.debug(
        "Substituting system prompt with builtin args: {builtin_args}, spec args: {spec_args}",
        builtin_args=builtin_args,
        spec_args=args,
    )
    return string.Template(system_prompt).substitute(asdict(builtin_args), **args)


type ToolType = BaseTool[Any]


def _load_tools(
    toolset: DynamicToolset,
    tool_paths: list[str],
    dependencies: dict[type[Any], Any],
) -> list[str]:
    """Load tools into the toolset.

    Args:
        toolset: The toolset to load tools into.
        tool_paths: List of tool module paths.
        dependencies: Dependencies to inject into tools.

    Returns:
        List of tool paths that failed to load.
    """
    bad_tools: list[str] = []
    for tool_path in tool_paths:
        try:
            tool = _load_tool(tool_path, dependencies)
        except SkipThisTool:
            logger.info("Skipping tool: {tool_path}", tool_path=tool_path)
            continue
        if tool:
            toolset += tool
        else:
            bad_tools.append(tool_path)
    logger.info("Loaded tools: {tools}", tools=[tool.name for tool in toolset.tools])
    if bad_tools:
        logger.error("Bad tools: {bad_tools}", bad_tools=bad_tools)
    return bad_tools


def _load_tool(tool_path: str, dependencies: dict[type[Any], Any]) -> ToolType | None:
    """Load a single tool from a module path."""
    logger.debug("Loading tool: {tool_path}", tool_path=tool_path)
    module_name, class_name = tool_path.rsplit(":", 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return None
    cls = getattr(module, class_name, None)
    if cls is None:
        return None
    args: list[type[Any]] = []
    for param in inspect.signature(cls).parameters.values():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            # once we encounter a keyword-only parameter, we stop injecting dependencies
            break
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            # Skip *args and **kwargs
            continue
        # all positional parameters should be dependencies to be injected
        if param.annotation not in dependencies:
            raise ValueError(f"Tool dependency not found: {param.annotation}")
        args.append(dependencies[param.annotation])
    return cls(*args)


class SkipThisTool(Exception):
    """Raised when a tool decides to skip itself from the loading process."""

    pass
