"""Tests for memory tool loading."""

from config import Config, Session
from loop.agent import _load_tool
from loop.agentspec import ResolvedAgentSpec
from loop.runtime import BuiltinSystemPromptArgs, Runtime
from memory.manager import MemoryManager
from tools.memory.delete import MemoryDelete
from tools.memory.save import MemorySave
from tools.memory.search import MemorySearch


def test_memory_tools_load_with_none_manager():
    runtime = Runtime(
        config=Config(),
        llm=None,
        session=Session.create_empty(),
        builtin_args=BuiltinSystemPromptArgs(CLI_NOW="now", CLI_LANGUAGE="en"),
        memory_manager=None,
    )
    deps = {
        ResolvedAgentSpec: ResolvedAgentSpec(
            name="test",
            system_prompt_path=__file__,
            system_prompt_args={},
            tools=[],
            exclude_tools=[],
        ),
        Runtime: runtime,
        Config: runtime.config,
        BuiltinSystemPromptArgs: runtime.builtin_args,
        Session: runtime.session,
        MemoryManager: runtime.memory_manager,
    }

    assert isinstance(_load_tool("tools.memory.save:MemorySave", deps), MemorySave)
    assert isinstance(_load_tool("tools.memory.search:MemorySearch", deps), MemorySearch)
    assert isinstance(_load_tool("tools.memory.delete:MemoryDelete", deps), MemoryDelete)
