"""Tests for utils.upgrade module."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.upgrade import (
    DEFAULT_CHECK_INTERVAL,
    UpgradeConfig,
    UpgradeInfo,
    check_for_updates,
    compare_versions,
    fetch_latest_version,
    get_upgrade_command,
    normalize_version,
)


class TestNormalizeVersion:
    """Tests for normalize_version function."""

    def test_remove_v_prefix(self):
        """Test removing 'v' prefix from version."""
        assert normalize_version("v0.1.5") == "0.1.5"
        assert normalize_version("v1.2.3") == "1.2.3"

    def test_no_prefix(self):
        """Test version without prefix."""
        assert normalize_version("0.1.5") == "0.1.5"
        assert normalize_version("1.2.3") == "1.2.3"

    def test_multiple_v_prefix(self):
        """Test version with multiple 'v' prefixes."""
        # lstrip removes all leading 'v' characters
        assert normalize_version("vv0.1.5") == "0.1.5"
        assert normalize_version("vvv0.1.5") == "0.1.5"

    def test_empty_string(self):
        """Test empty version string."""
        assert normalize_version("") == ""


class TestCompareVersions:
    """Tests for compare_versions function."""

    def test_latest_greater_than_current(self):
        """Test when latest version is greater."""
        assert compare_versions("0.1.4", "0.1.5") is True
        assert compare_versions("0.1.5", "0.2.0") is True
        assert compare_versions("0.2.0", "1.0.0") is True

    def test_current_greater_than_latest(self):
        """Test when current version is greater."""
        assert compare_versions("0.1.5", "0.1.4") is False
        assert compare_versions("0.2.0", "0.1.5") is False

    def test_versions_equal(self):
        """Test when versions are equal."""
        assert compare_versions("0.1.5", "0.1.5") is False
        assert compare_versions("1.0.0", "1.0.0") is False

    def test_with_v_prefix(self):
        """Test comparison with 'v' prefix."""
        assert compare_versions("v0.1.4", "v0.1.5") is True
        assert compare_versions("v0.1.5", "0.1.4") is False
        assert compare_versions("0.1.5", "v0.1.4") is False

    def test_invalid_version(self):
        """Test with invalid version strings."""
        # Should return False for invalid versions
        assert compare_versions("invalid", "0.1.5") is False
        assert compare_versions("0.1.5", "invalid") is False


class TestGetUpgradeCommand:
    """Tests for get_upgrade_command function."""

    @patch("shutil.which")
    def test_with_uv_available(self, mock_which):
        """Test when uv is available."""
        mock_which.return_value = "/usr/bin/uv"
        assert get_upgrade_command() == "uv tool upgrade rdsai-cli"

    @patch("shutil.which")
    def test_without_uv(self, mock_which):
        """Test when uv is not available."""
        mock_which.return_value = None
        assert get_upgrade_command() == "pip install --upgrade rdsai-cli"

    @patch("shutil.which")
    def test_uv_not_found(self, mock_which):
        """Test when uv command is not found."""
        mock_which.side_effect = lambda cmd: "/usr/bin/uv" if cmd == "uv" else None
        assert get_upgrade_command() == "uv tool upgrade rdsai-cli"


class TestUpgradeConfig:
    """Tests for UpgradeConfig class."""

    @pytest.fixture
    def temp_config_file(self, tmp_path):
        """Create a temporary config file."""
        config_file = tmp_path / "upgrade.json"
        return config_file

    def test_default_config(self, temp_config_file):
        """Test default configuration when file doesn't exist."""
        config = UpgradeConfig(config_file=temp_config_file)
        assert config.last_check_time is None
        assert config.auto_check is True

    def test_load_existing_config(self, temp_config_file):
        """Test loading existing configuration."""
        config_data = {
            "last_check_time": 1234567890.0,
            "auto_check": False,
        }
        temp_config_file.write_text(json.dumps(config_data), encoding="utf-8")

        config = UpgradeConfig(config_file=temp_config_file)
        assert config.last_check_time == 1234567890.0
        assert config.auto_check is False

    def test_load_config_with_defaults(self, temp_config_file):
        """Test loading config with missing fields uses defaults."""
        config_data = {"last_check_time": 1234567890.0}
        temp_config_file.write_text(json.dumps(config_data), encoding="utf-8")

        config = UpgradeConfig(config_file=temp_config_file)
        assert config.last_check_time == 1234567890.0
        assert config.auto_check is True  # Default value

    def test_save_config(self, temp_config_file):
        """Test saving configuration."""
        config = UpgradeConfig(config_file=temp_config_file)
        config.last_check_time = 1234567890.0
        config.auto_check = False

        assert temp_config_file.exists()
        loaded = json.loads(temp_config_file.read_text(encoding="utf-8"))
        assert loaded["last_check_time"] == 1234567890.0
        assert loaded["auto_check"] is False

    def test_should_check_auto_disabled(self, temp_config_file):
        """Test should_check when auto_check is disabled."""
        config = UpgradeConfig(config_file=temp_config_file)
        config.auto_check = False
        assert config.should_check() is False

    def test_should_check_never_checked(self, temp_config_file):
        """Test should_check when never checked before."""
        config = UpgradeConfig(config_file=temp_config_file)
        config.auto_check = True
        config.last_check_time = None
        assert config.should_check() is True

    def test_should_check_within_interval(self, temp_config_file):
        """Test should_check when within check interval."""
        config = UpgradeConfig(config_file=temp_config_file)
        config.auto_check = True
        config.last_check_time = time.time() - 100  # 100 seconds ago
        assert config.should_check() is False

    def test_should_check_after_interval(self, temp_config_file):
        """Test should_check after check interval."""
        config = UpgradeConfig(config_file=temp_config_file)
        config.auto_check = True
        config.last_check_time = time.time() - DEFAULT_CHECK_INTERVAL - 1  # Just past interval
        assert config.should_check() is True

    def test_invalid_json_handling(self, temp_config_file):
        """Test handling of invalid JSON."""
        temp_config_file.write_text("invalid json", encoding="utf-8")

        config = UpgradeConfig(config_file=temp_config_file)
        # Should fall back to defaults
        assert config.last_check_time is None
        assert config.auto_check is True


class TestFetchLatestVersion:
    """Tests for fetch_latest_version function."""

    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        """Test successful version fetch."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"info": {"version": "0.1.6"}})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("utils.upgrade.new_client_session", return_value=mock_session):
            result = await fetch_latest_version()
            assert result == "0.1.6"

    @pytest.mark.asyncio
    async def test_fetch_with_v_prefix(self):
        """Test fetching version with 'v' prefix."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"info": {"version": "v0.1.6"}})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("utils.upgrade.new_client_session", return_value=mock_session):
            result = await fetch_latest_version()
            assert result == "0.1.6"  # 'v' prefix removed

    @pytest.mark.asyncio
    async def test_fetch_non_200_status(self):
        """Test handling of non-200 status code."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("utils.upgrade.new_client_session", return_value=mock_session):
            result = await fetch_latest_version()
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_missing_version_info(self):
        """Test handling of missing version in response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"info": {}})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("utils.upgrade.new_client_session", return_value=mock_session):
            result = await fetch_latest_version()
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_timeout(self):
        """Test handling of timeout."""
        with patch("utils.upgrade.new_client_session") as mock_session:
            mock_session.side_effect = asyncio.TimeoutError()
            result = await fetch_latest_version()
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_exception(self):
        """Test handling of general exceptions."""
        with patch("utils.upgrade.new_client_session") as mock_session:
            mock_session.side_effect = Exception("Network error")
            result = await fetch_latest_version()
            assert result is None


class TestCheckForUpdates:
    """Tests for check_for_updates function."""

    @pytest.fixture
    def temp_config_file(self, tmp_path):
        """Create a temporary config file."""
        config_file = tmp_path / "upgrade.json"
        return config_file

    @pytest.mark.asyncio
    async def test_update_available(self, temp_config_file):
        """Test when update is available."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"info": {"version": "0.1.6"}})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("utils.upgrade.new_client_session", return_value=mock_session),
            patch("utils.upgrade.UpgradeConfig") as mock_config_class,
            patch("utils.upgrade.get_upgrade_command", return_value="pip install --upgrade rdsai-cli"),
        ):
            mock_config = MagicMock()
            mock_config.should_check.return_value = True
            mock_config.last_check_time = None
            mock_config_class.return_value = mock_config

            result = await check_for_updates("0.1.5", force=True)

            assert result is not None
            assert isinstance(result, UpgradeInfo)
            assert result.current_version == "0.1.5"
            assert result.latest_version == "v0.1.6"
            assert result.has_update is True
            assert result.upgrade_command == "pip install --upgrade rdsai-cli"

    @pytest.mark.asyncio
    async def test_no_update_available(self, temp_config_file):
        """Test when no update is available."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"info": {"version": "0.1.5"}})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("utils.upgrade.new_client_session", return_value=mock_session),
            patch("utils.upgrade.UpgradeConfig") as mock_config_class,
        ):
            mock_config = MagicMock()
            mock_config.should_check.return_value = True
            mock_config.last_check_time = None
            mock_config_class.return_value = mock_config

            result = await check_for_updates("0.1.5", force=True)

            assert result is None

    @pytest.mark.asyncio
    async def test_skip_check_within_interval(self, temp_config_file):
        """Test skipping check when within interval."""
        with patch("utils.upgrade.UpgradeConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.should_check.return_value = False
            mock_config_class.return_value = mock_config

            result = await check_for_updates("0.1.5", force=False)

            assert result is None

    @pytest.mark.asyncio
    async def test_force_check_within_interval(self, temp_config_file):
        """Test force check even when within interval."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"info": {"version": "0.1.6"}})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("utils.upgrade.new_client_session", return_value=mock_session),
            patch("utils.upgrade.UpgradeConfig") as mock_config_class,
            patch("utils.upgrade.get_upgrade_command", return_value="pip install --upgrade rdsai-cli"),
        ):
            mock_config = MagicMock()
            mock_config.should_check.return_value = False  # Within interval
            mock_config.last_check_time = None
            mock_config_class.return_value = mock_config

            result = await check_for_updates("0.1.5", force=True)

            assert result is not None  # Force check bypasses interval

    @pytest.mark.asyncio
    async def test_fetch_failure(self, temp_config_file):
        """Test handling of fetch failure."""
        with (
            patch("utils.upgrade.new_client_session") as mock_session,
            patch("utils.upgrade.UpgradeConfig") as mock_config_class,
        ):
            mock_session.side_effect = Exception("Network error")
            mock_config = MagicMock()
            mock_config.should_check.return_value = True
            mock_config.last_check_time = None
            mock_config_class.return_value = mock_config

            result = await check_for_updates("0.1.5", force=True)

            assert result is None

    @pytest.mark.asyncio
    async def test_version_comparison_edge_cases(self, temp_config_file):
        """Test version comparison edge cases."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"info": {"version": "0.1.4"}})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("utils.upgrade.new_client_session", return_value=mock_session),
            patch("utils.upgrade.UpgradeConfig") as mock_config_class,
        ):
            mock_config = MagicMock()
            mock_config.should_check.return_value = True
            mock_config.last_check_time = None
            mock_config_class.return_value = mock_config

            # Current version is newer than latest
            result = await check_for_updates("0.1.5", force=True)
            assert result is None
