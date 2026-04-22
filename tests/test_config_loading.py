import os
from pathlib import Path
from unittest.mock import mock_open, patch

from sig_cloud_control.cli_app import load_config
from sig_cloud_control.models import Region

ENV_STATION_ID = 12345
OVERRIDE_STATION_ID = 999


def test_load_config_env_vars_only() -> None:
    """Test loading config solely from environment variables."""
    env = {
        "SIGEN_USERNAME": "env@example.com",
        "SIGEN_PASSWORD": "envpassword",
        "SIGEN_STATION_ID": str(ENV_STATION_ID),
        "SIGEN_REGION": "aus",
    }
    with patch.dict(os.environ, env):
        config = load_config(Path("nonexistent.toml"))
        assert config.username == "env@example.com"
        assert config.password == "envpassword"
        assert config.station_id == ENV_STATION_ID
        assert config.region == Region.AUS


def test_load_config_file_with_env_override() -> None:
    """Test that environment variables override file settings."""
    file_content = (
        b'username = "file@example.com"\n'
        b'password_encoded = "YWFhYWFhYWFhYWFhYWFhYQ=="\n'
        b"station_id = 111\n"
        b'region = "aus"\n'
    )
    env = {
        "SIGEN_USERNAME": "override@example.com",
        "SIGEN_STATION_ID": str(OVERRIDE_STATION_ID),
        "SIGEN_REGION": "eu",
    }

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
        # region env var should override file value
        assert config.region == Region.EU


def test_load_config_minimum_env_vars() -> None:
    """Test loading config with only the absolute minimum environment variables."""
    env = {
        "SIGEN_USERNAME": "min@example.com",
        "SIGEN_PASSWORD": "minpassword",
        "SIGEN_REGION": "us",
    }
    # Clear other SIGEN_ env vars to ensure we are testing the minimum
    with patch.dict(os.environ, env, clear=True):
        config = load_config(Path("nonexistent.toml"))
        assert config.username == "min@example.com"
        assert config.password == "minpassword"
        assert config.password_encoded is None
        assert config.station_id is None
        assert config.region == Region.US


def test_load_config_no_env_no_file_triggers_setup() -> None:
    """Test that setup is triggered if no env vars and no file exist.

    After setup writes the file, load_config re-attempts _try_load_config.
    We simulate this by having Path.exists return False (no file yet) on the
    first check, then True (file written by setup) on the second check, and
    providing a matching mock_open for the subsequent file read.
    """
    config_path = Path("config.toml")
    file_content = b'username = "setup@example.com"\npassword = "pw"\nregion = "aus"\n'
    with (
        patch("pathlib.Path.exists", side_effect=[False, True]),
        patch("sig_cloud_control.cli_app.perform_setup") as mock_setup,
        patch("builtins.open", mock_open(read_data=file_content)),
        patch.dict(os.environ, {}, clear=True),
    ):
        mock_setup.return_value = None
        config = load_config(config_path)
        mock_setup.assert_called_once_with(config_path)
        assert config.username == "setup@example.com"
