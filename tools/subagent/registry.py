"""Subagent registry for managing available subagents."""

from __future__ import annotations

from pathlib import Path
from loop.agentspec import get_agents_dir

from tools.subagent.executor import SubagentExecutor, SysBenchSubagentExecutor
from utils.logging import logger


class SubagentRegistry:
    """Registry for managing subagent executors."""

    def __init__(self):
        """Initialize the registry."""
        self._executors: dict[str, SubagentExecutor] = {}
        self._prompts_dir = Path(__file__).parent.parent.parent / "prompts"

    def register(self, executor: SubagentExecutor) -> None:
        """Register a subagent executor.

        Args:
            executor: Subagent executor instance.
        """
        self._executors[executor.name] = executor
        logger.info("Registered subagent executor: {name}", name=executor.name)

    def get(self, name: str) -> SubagentExecutor | None:
        """Get a subagent executor by name.

        Args:
            name: Subagent name.

        Returns:
            Subagent executor or None if not found.
        """
        return self._executors.get(name)

    def list_all(self) -> list[str]:
        """List all registered subagent names.

        Returns:
            List of subagent names.
        """
        return list(self._executors.keys())

    def register_defaults(self) -> None:
        """Register default subagents)."""
        prompts_dir = get_agents_dir()
        # Register sysbench
        sysbench_file = prompts_dir / "sysbench_agent.yaml"
        if sysbench_file.exists():
            self.register(SysBenchSubagentExecutor("sysbench", sysbench_file))


# Global registry instance
_registry: SubagentRegistry | None = None


def get_registry() -> SubagentRegistry:
    """Get the global subagent registry instance.

    Returns:
        Global SubagentRegistry instance.
    """
    global _registry
    if _registry is None:
        _registry = SubagentRegistry()
        _registry.register_defaults()
    return _registry
