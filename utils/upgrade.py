"""Version upgrade checking and management utilities."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import NamedTuple

import aiohttp
from packaging.version import Version

from config import get_share_dir
from utils.aiohttp import new_client_session
from utils.logging import logger

# PyPI API endpoint for rdsai-cli
PYPI_API_URL = "https://pypi.org/pypi/rdsai-cli/json"
# Default check interval in seconds (24 hours)
DEFAULT_CHECK_INTERVAL = 24 * 60 * 60


class UpgradeInfo(NamedTuple):
    """Upgrade information."""

    current_version: str
    latest_version: str
    has_update: bool
    upgrade_command: str


class UpgradeConfig:
    """Manage upgrade check configuration."""

    def __init__(self, config_file: Path | None = None):
        """Initialize upgrade configuration.

        Args:
            config_file: Path to the upgrade config file. Defaults to ~/.rdsai-cli/upgrade.json
        """
        if config_file is None:
            config_file = get_share_dir() / "upgrade.json"
        self.config_file = config_file
        self._last_check_time: float | None
        self._auto_check: bool
        self._last_check_time, self._auto_check = self._load_config()

    def _load_config(self) -> tuple[float | None, bool]:
        """Load configuration from file.

        Returns:
            Tuple of (last_check_time, auto_check)
        """
        if not self.config_file.exists():
            return None, True  # Default: auto check enabled

        try:
            with open(self.config_file, encoding="utf-8") as f:
                config = json.load(f)
                return (
                    config.get("last_check_time"),
                    config.get("auto_check", True),  # Default: auto check enabled
                )
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("Failed to load upgrade config: {error}", error=e)
            return None, True  # Default: auto check enabled

    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "last_check_time": self._last_check_time,
                        "auto_check": self._auto_check,
                    },
                    f,
                )
        except OSError as e:
            logger.debug("Failed to save upgrade config: {error}", error=e)

    @property
    def last_check_time(self) -> float | None:
        """Last check timestamp."""
        return self._last_check_time

    @last_check_time.setter
    def last_check_time(self, value: float | None) -> None:
        """Set last check timestamp."""
        self._last_check_time = value
        self._save_config()

    @property
    def auto_check(self) -> bool:
        """Whether to automatically check for updates."""
        return self._auto_check

    @auto_check.setter
    def auto_check(self, value: bool) -> None:
        """Set auto check preference."""
        self._auto_check = value
        self._save_config()

    def should_check(self) -> bool:
        """Check if an update check should be performed."""
        # If auto check is disabled, don't check
        if not self._auto_check:
            return False

        # If never checked before, should check
        if self._last_check_time is None:
            return True

        # Check if enough time has passed since last check
        return time.time() - self._last_check_time >= DEFAULT_CHECK_INTERVAL


async def fetch_latest_version(timeout: float = 3.0) -> str | None:
    """Fetch the latest version from PyPI.

    Args:
        timeout: Request timeout in seconds. Defaults to 3.0.

    Returns:
        Latest version string (without 'v' prefix) or None if failed.
    """
    try:
        async with (
            new_client_session() as session,
            session.get(PYPI_API_URL, timeout=aiohttp.ClientTimeout(total=timeout)) as response,
        ):
            if response.status == 200:
                data = await response.json()
                version = data.get("info", {}).get("version")
                if version:
                    # Remove 'v' prefix if present
                    return version.lstrip("v")
                logger.warning("PyPI API response missing version info")
                return None
            else:
                logger.debug("PyPI API returned status {status}", status=response.status)
                return None
    except asyncio.TimeoutError:
        logger.debug("Timeout while fetching latest version from PyPI")
        return None
    except Exception as e:
        logger.debug("Failed to fetch latest version: {error}", error=e)
        return None


def normalize_version(version: str) -> str:
    """Normalize version string by removing 'v' prefix.

    Args:
        version: Version string (e.g., "v0.1.5" or "0.1.5")

    Returns:
        Normalized version string without 'v' prefix
    """
    return version.lstrip("v")


def compare_versions(current: str, latest: str) -> bool:
    """Compare versions to determine if an update is available.

    Args:
        current: Current version string
        latest: Latest version string

    Returns:
        True if latest > current, False otherwise
    """
    try:
        current_normalized = normalize_version(current)
        latest_normalized = normalize_version(latest)
        return Version(latest_normalized) > Version(current_normalized)
    except Exception as e:
        logger.warning(
            "Failed to compare versions '{current}' and '{latest}': {error}", current=current, latest=latest, error=e
        )
        return False


def get_upgrade_command() -> str:
    """Get the upgrade command based on available package managers.

    Returns:
        Upgrade command string
    """
    # Try to detect if uv is available, otherwise use pip
    import shutil

    if shutil.which("uv"):
        return "uv tool upgrade rdsai-cli"
    return "pip install --upgrade rdsai-cli"


async def check_for_updates(current_version: str, force: bool = False) -> UpgradeInfo | None:
    """Check for available updates.

    Args:
        current_version: Current version string
        force: Force check even if within check interval

    Returns:
        UpgradeInfo if update available, None otherwise
    """
    config = UpgradeConfig()

    # Check if we should skip this check
    if not force and not config.should_check():
        return None

    # Fetch latest version
    latest_version = await fetch_latest_version()
    if latest_version is None:
        # Update check time even on failure to avoid repeated failures
        if force:
            config.last_check_time = time.time()
        return None

    # Update last check time
    config.last_check_time = time.time()

    # Normalize versions for comparison
    current_normalized = normalize_version(current_version)
    latest_normalized = normalize_version(latest_version)

    # Check if update is available
    has_update = compare_versions(current_normalized, latest_normalized)

    if has_update:
        upgrade_command = get_upgrade_command()
        return UpgradeInfo(
            current_version=current_version,
            latest_version=f"v{latest_normalized}" if not latest_normalized.startswith("v") else latest_normalized,
            has_update=True,
            upgrade_command=upgrade_command,
        )

    return None
