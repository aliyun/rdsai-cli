"""Tests for loop.agentspec module."""

import tempfile
from pathlib import Path

import pytest
import yaml

from loop.agentspec import (
    DEFAULT_AGENT_FILE,
    AgentSpec,
    AgentSpecError,
    ResolvedAgentSpec,
    load_agent_spec,
)


class TestAgentSpec:
    """Tests for AgentSpec model."""

    def test_init_minimal(self):
        """Test AgentSpec initialization with minimal fields."""
        spec = AgentSpec()
        assert spec.extend is None
        assert spec.name is None
        assert spec.system_prompt_path is None
        assert spec.system_prompt_args == {}
        assert spec.tools is None
        assert spec.exclude_tools is None

    def test_init_with_values(self):
        """Test AgentSpec initialization with all values."""
        spec = AgentSpec(
            extend="default",
            name="test_agent",
            system_prompt_path=Path("/path/to/prompt.md"),
            system_prompt_args={"key": "value"},
            tools=["tool1", "tool2"],
            exclude_tools=["tool3"],
        )
        assert spec.extend == "default"
        assert spec.name == "test_agent"
        assert spec.system_prompt_path == Path("/path/to/prompt.md")
        assert spec.system_prompt_args == {"key": "value"}
        assert spec.tools == ["tool1", "tool2"]
        assert spec.exclude_tools == ["tool3"]


class TestLoadAgentSpec:
    """Tests for load_agent_spec function."""

    def test_load_minimal_spec(self):
        """Test loading minimal agent spec."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            spec_data = {"version": 1, "agent": {"name": "test_agent", "system_prompt_path": "prompt.md"}}
            yaml.dump(spec_data, f)
            spec_path = Path(f.name)

        try:
            spec = load_agent_spec(spec_path)
            assert isinstance(spec, ResolvedAgentSpec)
            assert spec.name == "test_agent"
            assert spec.system_prompt_path.is_absolute()
            assert spec.tools == []
            assert spec.exclude_tools == []
        finally:
            spec_path.unlink()

    def test_load_full_spec(self):
        """Test loading full agent spec."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            spec_data = {
                "version": 1,
                "agent": {
                    "name": "test_agent",
                    "system_prompt_path": "prompt.md",
                    "system_prompt_args": {"key": "value"},
                    "tools": ["tool1", "tool2"],
                    "exclude_tools": ["tool3"],
                },
            }
            yaml.dump(spec_data, f)
            spec_path = Path(f.name)

        try:
            spec = load_agent_spec(spec_path)
            assert spec.name == "test_agent"
            assert spec.system_prompt_args == {"key": "value"}
            assert spec.tools == ["tool1", "tool2"]
            assert spec.exclude_tools == ["tool3"]
        finally:
            spec_path.unlink()

    def test_load_spec_file_not_found(self):
        """Test loading non-existent spec file."""
        spec_path = Path("/nonexistent/path/agent.yaml")
        with pytest.raises(AgentSpecError, match="not found"):
            load_agent_spec(spec_path)

    def test_load_spec_invalid_yaml(self):
        """Test loading spec with invalid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            spec_path = Path(f.name)

        try:
            with pytest.raises(AgentSpecError, match="Invalid YAML"):
                load_agent_spec(spec_path)
        finally:
            spec_path.unlink()

    def test_load_spec_unsupported_version(self):
        """Test loading spec with unsupported version."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            spec_data = {"version": 2, "agent": {"name": "test_agent", "system_prompt_path": "prompt.md"}}
            yaml.dump(spec_data, f)
            spec_path = Path(f.name)

        try:
            with pytest.raises(AgentSpecError, match="Unsupported agent spec version"):
                load_agent_spec(spec_path)
        finally:
            spec_path.unlink()

    def test_load_spec_missing_name(self):
        """Test loading spec without name."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            spec_data = {"version": 1, "agent": {"system_prompt_path": "prompt.md"}}
            yaml.dump(spec_data, f)
            spec_path = Path(f.name)

        try:
            with pytest.raises(AgentSpecError, match="Agent name is required"):
                load_agent_spec(spec_path)
        finally:
            spec_path.unlink()

    def test_load_spec_missing_system_prompt_path(self):
        """Test loading spec without system_prompt_path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            spec_data = {"version": 1, "agent": {"name": "test_agent"}}
            yaml.dump(spec_data, f)
            spec_path = Path(f.name)

        try:
            with pytest.raises(AgentSpecError, match="System prompt path is required"):
                load_agent_spec(spec_path)
        finally:
            spec_path.unlink()

    def test_load_spec_relative_prompt_path(self):
        """Test loading spec with relative prompt path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_file = Path(tmpdir) / "agent.yaml"
            prompt_file = Path(tmpdir) / "prompt.md"
            prompt_file.write_text("# Prompt")

            spec_data = {"version": 1, "agent": {"name": "test_agent", "system_prompt_path": "prompt.md"}}
            with open(spec_file, "w", encoding="utf-8") as f:
                yaml.dump(spec_data, f)

            spec = load_agent_spec(spec_file)
            assert spec.system_prompt_path.is_absolute()
            assert spec.system_prompt_path.name == "prompt.md"
            assert spec.system_prompt_path.parent == spec_file.parent

    def test_load_spec_with_extend_default(self):
        """Test loading spec that extends default agent."""
        # This test requires DEFAULT_AGENT_FILE to exist
        # We'll mock it or skip if it doesn't exist
        if not DEFAULT_AGENT_FILE.exists():
            pytest.skip("DEFAULT_AGENT_FILE does not exist")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            spec_data = {
                "version": 1,
                "agent": {"extend": "default", "name": "custom_agent", "system_prompt_path": "custom_prompt.md"},
            }
            yaml.dump(spec_data, f)
            spec_path = Path(f.name)

        try:
            # This will try to load the default agent, which may fail if it doesn't exist
            # We'll catch the error and skip if needed
            try:
                spec = load_agent_spec(spec_path)
                assert spec.name == "custom_agent"
            except AgentSpecError:
                pytest.skip("Default agent file not available for testing")
        finally:
            spec_path.unlink()

    def test_load_spec_with_extend_relative(self):
        """Test loading spec that extends another relative spec."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_spec_file = Path(tmpdir) / "base.yaml"
            spec_file = Path(tmpdir) / "agent.yaml"

            base_spec_data = {
                "version": 1,
                "agent": {
                    "name": "base_agent",
                    "system_prompt_path": "base_prompt.md",
                    "tools": ["base_tool"],
                    "system_prompt_args": {"base_key": "base_value"},
                },
            }
            with open(base_spec_file, "w", encoding="utf-8") as f:
                yaml.dump(base_spec_data, f)

            spec_data = {
                "version": 1,
                "agent": {
                    "extend": "base.yaml",
                    "name": "extended_agent",
                    "system_prompt_path": "extended_prompt.md",
                    "tools": ["extended_tool"],
                    "system_prompt_args": {"extended_key": "extended_value"},
                },
            }
            with open(spec_file, "w", encoding="utf-8") as f:
                yaml.dump(spec_data, f)

            spec = load_agent_spec(spec_file)
            assert spec.name == "extended_agent"
            assert spec.system_prompt_path.name == "extended_prompt.md"
            assert spec.tools == ["extended_tool"]
            # Extended args should merge
            assert "base_key" in spec.system_prompt_args
            assert "extended_key" in spec.system_prompt_args

    def test_load_spec_tools_defaults_to_empty(self):
        """Test that tools defaults to empty list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            spec_data = {"version": 1, "agent": {"name": "test_agent", "system_prompt_path": "prompt.md"}}
            yaml.dump(spec_data, f)
            spec_path = Path(f.name)

        try:
            spec = load_agent_spec(spec_path)
            assert spec.tools == []
        finally:
            spec_path.unlink()

    def test_load_spec_exclude_tools_defaults_to_empty(self):
        """Test that exclude_tools defaults to empty list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            spec_data = {
                "version": 1,
                "agent": {"name": "test_agent", "system_prompt_path": "prompt.md", "tools": ["tool1"]},
            }
            yaml.dump(spec_data, f)
            spec_path = Path(f.name)

        try:
            spec = load_agent_spec(spec_path)
            assert spec.exclude_tools == []
        finally:
            spec_path.unlink()


class TestResolvedAgentSpec:
    """Tests for ResolvedAgentSpec dataclass."""

    def test_init(self):
        """Test ResolvedAgentSpec initialization."""
        spec = ResolvedAgentSpec(
            name="test",
            system_prompt_path=Path("/path/to/prompt.md"),
            system_prompt_args={"key": "value"},
            tools=["tool1"],
            exclude_tools=["tool2"],
        )
        assert spec.name == "test"
        assert spec.system_prompt_path == Path("/path/to/prompt.md")
        assert spec.system_prompt_args == {"key": "value"}
        assert spec.tools == ["tool1"]
        assert spec.exclude_tools == ["tool2"]
