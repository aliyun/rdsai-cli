"""Configuration package.

This module provides unified access to all configuration-related classes and functions.
"""

# Base configuration (constants, paths, session)
from config.base import (
    get_config_file,
    get_share_dir,
    Session,
    USER_AGENT,
    VERSION,
)

# LLM configuration
from config.llm import (
    ALL_MODEL_CAPABILITIES,
    LLMModel,
    LLMProvider,
    ModelCapability,
    ProviderType,
)

# Application configuration
from config.app import (
    Config,
    get_default_config,
    load_config,
    LoopControl,
    save_config,
    Services,
)


__all__ = [
    # Base
    "get_config_file",
    "get_share_dir",
    "Session",
    "USER_AGENT",
    "VERSION",
    # LLM
    "ALL_MODEL_CAPABILITIES",
    "LLMModel",
    "LLMProvider",
    "ModelCapability",
    "ProviderType",
    # App
    "Config",
    "get_default_config",
    "load_config",
    "LoopControl",
    "save_config",
    "Services",
]
