"""Subagent executor interface and base implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from loop.agent import Agent, load_agent
from loop.runtime import Runtime


class SubagentExecutor(ABC):
    """Base class for subagent executors.

    Each subagent executor handles the specific logic for preparing and executing
    a subagent task, including prompt building, context preparation, etc.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Subagent name (must match the agent file name without extension)."""
        pass

    @property
    @abstractmethod
    def agent_file(self) -> Path:
        """Path to the agent configuration file."""
        pass

    @abstractmethod
    async def build_prompt(
        self,
        task_description: str,
        parameters: dict[str, Any] | None,
        runtime: Runtime,
    ) -> str:
        """Build the prompt for the subagent.

        Args:
            task_description: Task description from user.
            parameters: Optional parameters for the subagent.
            runtime: Runtime configuration.

        Returns:
            Formatted prompt string for the subagent.
        """
        pass

    async def get_yolo_mode(self, runtime: Runtime) -> bool:
        """Get yolo mode for the subagent.

        Args:
            runtime: Runtime configuration.

        Returns:
            Whether to auto-approve all actions.
        """
        return runtime.yolo if runtime.yolo else False

    async def load_agent(self, runtime: Runtime) -> Agent:
        """Load the subagent.

        Args:
            runtime: Runtime configuration.

        Returns:
            Loaded Agent instance.
        """
        agent_file = self.agent_file
        if not agent_file.exists():
            raise ValueError(f"Subagent '{self.name}' configuration not found: {agent_file}")

        return await load_agent(agent_file, runtime)


class SysBenchSubagentExecutor(SubagentExecutor):
    """Sysbench executor that just passes task description to the subagent.

    Suitable for most subagents that don't need special context preparation.
    """

    def __init__(
        self,
        name: str,
        agent_file: Path,
        yolo: bool | None = None,
    ):
        """Initialize simple executor.

        Args:
            name: Subagent name.
            agent_file: Path to agent configuration file.
            yolo: Override yolo mode (None to use runtime default).
        """
        self._name = name
        self._agent_file = agent_file
        self._yolo_override = yolo

    @property
    def name(self) -> str:
        return self._name

    @property
    def agent_file(self) -> Path:
        return self._agent_file

    async def build_prompt(
        self,
        task_description: str,
        parameters: dict[str, Any] | None,
        runtime: Runtime,
    ) -> str:
        """Build prompt by combining task description and parameters."""
        prompt_parts = [task_description]

        if parameters:
            param_parts = []
            for key, value in parameters.items():
                if value is not None:
                    if isinstance(value, (int, float)) and value >= 1000:
                        value_str = f"{value:,}"
                    else:
                        value_str = str(value)
                    param_parts.append(f"{key}: {value_str}")

            if param_parts:
                prompt_parts.append("\nSpecified parameters:")
                prompt_parts.extend(f"- {p}" for p in param_parts)

        return "\n".join(prompt_parts)

    async def get_yolo_mode(self, runtime: Runtime) -> bool:
        """Get yolo mode with override support."""
        if self._yolo_override is not None:
            return self._yolo_override
        return await super().get_yolo_mode(runtime)
