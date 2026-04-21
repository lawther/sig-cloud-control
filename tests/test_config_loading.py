import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

# Mock tomli_w before importing the app because it's missing in the environment
sys.modules["tomli_w"] = MagicMock()

from sig_cloud_control.cli_app import load_config  # noqa: E402
from sig_cloud_control.models import Config  # noqa: E402

ENV_STATION_ID = 12345
OVERRIDE_STATION_ID = 999


def test_load_config_env_vars_only() -> None:
    """Test loading config solely from environment variables."""
    env = {
        "SIGEN_USERNAME": "env@example.com",
        "SIGEN_PASSWORD": "envpassword",
        "SIGEN_STATION_ID": str(ENV_STATION_ID),
    }
    with patch.dict(os.environ, env):
        config = load_config(Path("nonexistent.toml"))
        assert config.username == "env@example.com"
        assert config.password == "envpassword"
        assert config.station_id == ENV_STATION_ID


def test_load_config_file_with_env_override() -> None:
    """Test that environment variables override file settings."""
    file_content = b'username = "file@example.com"\npassword_encoded = "YWFhYWFhYWFhYWFhYWFhYQ=="\nstation_id = 111'
    env = {"SIGEN_USERNAME": "override@example.com", "SIGEN_STATION_ID": str(OVERRIDE_STATION_ID)}

    with (
        patch("builtins.open", mock_open(read_data=file_content)),
        patch("pathlib.Path.exists", return_value=True),
        patch.dict(os.environ, env),
    ):
        config = load_config(Path("config.toml"))
        assert config.username == "override@example.com"
        assert config.station_id == OVERRIDE_STATION_ID
        # password_encoded should still be from file
        assert config.password_encoded == "YWFhYWFhYWFhYWFhYWFhYQ=="


def test_load_config_minimum_env_vars() -> None:
    """Test loading config with only the absolute minimum environment variables."""
    env = {
        "SIGEN_USERNAME": "min@example.com",
        "SIGEN_PASSWORD": "minpassword",
    }
    # Clear other SIGEN_ env vars to ensure we are testing the minimum
    with patch.dict(os.environ, env, clear=True):
        config = load_config(Path("nonexistent.toml"))
        assert config.username == "min@example.com"
        assert config.password == "minpassword"
        assert config.password_encoded is None
        assert config.station_id is None


def test_load_config_no_env_no_file_triggers_setup() -> None:
    """Test that setup is triggered if no env vars and no file exist."""
    config_path = Path("config.toml")
    with (
        patch("pathlib.Path.exists", return_value=False),
        patch("sig_cloud_control.cli_app.perform_setup") as mock_setup,
        patch.dict(os.environ, {}, clear=True),
    ):
        mock_setup.return_value = Config(username="setup@example.com", password="pw")
        config = load_config(config_path)
        mock_setup.assert_called_once_with(config_path)
        assert config.username == "setup@example.com"
